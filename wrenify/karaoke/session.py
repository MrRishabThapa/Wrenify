"""
Wrenify — Karaoke session orchestrator.

Wires together all the pieces:
- AudioPlayer (song playback through speakers)
- AudioCapture (mic input)
- WebcamCapture (video)
- Timeline (playback position, synced to the player)
- LyricTracker (current line highlighting)

Emits Qt signals for UI updates.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from loguru import logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from wrenify.audio.capture import AudioCapture
from wrenify.audio.player import AudioPlayer
from wrenify.core.config import CONFIG
from wrenify.karaoke.matcher import LyricTracker
from wrenify.karaoke.timeline import Timeline
from wrenify.lyrics.parser import LRCParser
from wrenify.songs.song import Song
from wrenify.video.camera import WebcamCapture


class KaraokeSession(QObject):
    """
    Runs a full karaoke session end-to-end.

    The instrumental track plays through the speakers while the
    timeline syncs to the actual audio position, so lyrics highlight
    in sync with the music.

    Emits:
        tick_signal(float)      — every UI update tick (song time)
        finished_signal         — when session ends
    """

    tick_signal     = pyqtSignal(float)
    finished_signal = pyqtSignal()  # No arguments — no score to report
    audio_level_signal = pyqtSignal(float)  # RMS 0.0 to 1.0
    recording_toggled  = pyqtSignal(bool)   # True = recording, False = not
    autotune_toggled   = pyqtSignal(bool)   # True = autotune on save

    UI_UPDATE_INTERVAL_MS: int = 33  # ~30fps

    @property
    def duration(self) -> float:
        """Song duration in seconds (from the loaded audio)."""
        return self._effective_duration

    def __init__(
        self,
        song: Song,
        lyrics_offset_sec: float = 0.0,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.song = song

        # Parse lyrics from the song's .lrc file
        parser = LRCParser()
        self.lyrics = parser.parse_file(song.lyrics_path)

        # Load the instrumental and let the timeline sync to it
        self.player = AudioPlayer()
        self.player.load(song.instrumental_path)

        self.timeline = Timeline(
            self.lyrics,
            player=self.player,
            offset_sec=lyrics_offset_sec,
        )
        self.lyric_tracker = LyricTracker(self.timeline)

        # Auto-stop point: prefer audio duration, fall back to the
        # last word's end time (some LRCs lack timing metadata).
        self._effective_duration = self.player.duration_sec() or (
            max((w.end for w in self.timeline.words), default=0.0) + 3.0
        )

        self.audio_capture: Optional[AudioCapture] = None
        self.webcam:        Optional[WebcamCapture] = None
        self._audio_forwarder: Optional[QTimer] = None

        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(self.UI_UPDATE_INTERVAL_MS)
        self._ui_timer.timeout.connect(self._on_tick)

        self._running = False
        self._song_started = False

        # Optional performance recording (opt-in via R key)
        self._is_recording = False
        self._recorded_audio: list[np.ndarray] = []
        self._recorded_frames: list = []  # Frame objects from webcam

        # Post-processing toggle: apply auto-tune on save
        self._autotune_enabled: bool = False

        # Song-time when recording started/stopped (for music mixing)
        self._recording_start_song_time: float = 0.0
        self._recording_end_song_time: float = 0.0

    def start(self) -> None:
        """Start the karaoke session."""
        if self._running:
            return

        logger.info(f"Starting karaoke: {self.song.display_name}")

        # Start webcam (optional — view falls back to dark background)
        try:
            self.webcam = WebcamCapture()
            self.webcam.start()
        except Exception as e:
            logger.warning(f"Webcam unavailable: {e}")
            self.webcam = None

        # Start audio capture (optional — session runs without scoring)
        try:
            self.audio_capture = AudioCapture()
            self.audio_capture.start()
        except Exception as e:
            logger.warning(f"Mic unavailable: {e}")
            self.audio_capture = None

        # Start the music
        self.player.play(start_position_sec=0.0)
        self._song_started = True

        # Forward audio chunks for the mic visualizer + recording
        if self.audio_capture is not None:
            self._audio_forwarder = QTimer(self)
            self._audio_forwarder.setInterval(10)  # 100Hz polling
            self._audio_forwarder.timeout.connect(self._forward_audio)
            self._audio_forwarder.start()

        # Start UI ticker
        self._ui_timer.start()
        self._running = True
        logger.info("Karaoke session running with music")

    def stop(self) -> None:
        """Stop the session, save any recording, and emit final score."""
        if not self._running:
            return

        # If still recording when session ends, capture end time
        if self._is_recording:
            self._recording_end_song_time = self.timeline.now()
            self._is_recording = False
            logger.info(
                f"Recording STOPPED at song time "
                f"{self._recording_end_song_time:.2f}s (session end)"
            )

        logger.info("Stopping karaoke session")

        self._running = False
        self._ui_timer.stop()
        if self._audio_forwarder is not None:
            self._audio_forwarder.stop()
            self._audio_forwarder = None

        # Capture sample rate BEFORE closing capture
        sample_rate = (
            self.audio_capture.cfg.sample_rate
            if self.audio_capture is not None
            else 44100
        )

        # Stop the song
        self.player.stop()

        if self.audio_capture is not None:
            self.audio_capture.stop()
            self.audio_capture = None
        if self.webcam is not None:
            self.webcam.stop()
            self.webcam = None

        logger.info("Session finished")

        # Save recording to library if we recorded anything
        if self._recorded_audio:
            try:
                self._save_recording(sample_rate)
            except Exception as e:
                logger.error(f"Failed to save recording: {e}")
                import traceback

                traceback.print_exc()

        self.finished_signal.emit()  # No args

    def end_early(self) -> None:
        """User-triggered early stop. Same as stop() but logged distinctly."""
        logger.info("User ended karaoke early")
        self.stop()

    def _save_recording(self, sample_rate: int) -> None:
        """Save recording with music mix and optional auto-tune."""
        from wrenify.audio.mixer import AudioMixer
        from wrenify.recordings.manager import RecordingsManager

        manager = RecordingsManager()
        voice_samples = np.concatenate(self._recorded_audio)

        # Load matching instrumental slice
        instrumental_samples = None
        try:
            mixer = AudioMixer()
            recording_duration = len(voice_samples) / sample_rate
            instrumental_samples, inst_sr = mixer.load_instrumental_slice(
                instrumental_path=self.song.instrumental_path,
                start_sec=self._recording_start_song_time,
                duration_sec=recording_duration,
            )

            # Resample instrumental if sample rates differ
            if inst_sr != sample_rate:
                import librosa

                instrumental_samples = librosa.resample(
                    instrumental_samples,
                    orig_sr=inst_sr,
                    target_sr=sample_rate,
                )

            logger.success("Loaded instrumental slice for mixing")
        except Exception as e:
            logger.error(f"Could not load instrumental for mixing: {e}")
            # Continue without mixing — will save voice-only versions

        # Auto-tune voice if enabled
        voice_autotuned = None
        if self._autotune_enabled:
            try:
                voice_autotuned = self._process_autotune(
                    voice_samples, sample_rate
                )
                logger.success("Auto-tune applied to voice")
            except Exception as e:
                logger.error(f"Auto-tune failed: {e}")

        saved = manager.save(
            song_title=self.song.title,
            song_artist=self.song.artist,
            sample_rate=sample_rate,
            voice_samples=voice_samples,
            voice_autotuned=voice_autotuned,
            instrumental_samples=instrumental_samples,
            video_frames=self._recorded_frames or None,
        )
        logger.success(f"Recording saved: {saved.folder.name}")

    def _process_autotune(
        self, audio: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """Apply auto-tune to the recorded audio (post-processing)."""
        from wrenify.audio.autotune import AutoTuneEngine

        # Determine key from song metadata if available
        song_key = getattr(self.song, "key", None) or CONFIG.autotune.key
        song_scale = getattr(self.song, "scale", None) or CONFIG.autotune.scale

        logger.info(f"Auto-tuning recording in {song_key} {song_scale}")

        # Temporarily override config for this song
        original_key = CONFIG.autotune.key
        original_scale = CONFIG.autotune.scale
        CONFIG.autotune.key = song_key
        CONFIG.autotune.scale = song_scale

        try:
            engine = AutoTuneEngine()
            return engine.process_full(audio, sample_rate)
        finally:
            # Restore original config
            CONFIG.autotune.key = original_key
            CONFIG.autotune.scale = original_scale

    def toggle_autotune(self) -> None:
        """Toggle whether recording will be auto-tuned on save."""
        self._autotune_enabled = not self._autotune_enabled
        self.autotune_toggled.emit(self._autotune_enabled)
        logger.info(
            f"Auto-tune {'ENABLED' if self._autotune_enabled else 'DISABLED'} "
            "for recording"
        )

    def is_autotune_enabled(self) -> bool:
        return self._autotune_enabled

    def pause(self) -> None:
        """Pause the song; the timeline follows the player."""
        self.player.pause()

    def resume(self) -> None:
        """Resume the song; the timeline follows the player."""
        self.player.resume()

    def _on_tick(self) -> None:
        """Called ~30 times per second from UI timer."""
        current_time = self.timeline.now()
        self.tick_signal.emit(current_time)

        # Record webcam frame if recording
        if self._is_recording and self.webcam is not None:
            frame = self.webcam.get_latest_frame()
            if frame is not None:
                self._recorded_frames.append(frame)

        # Auto-stop when the song finishes playing
        if self._song_started and self.player.is_finished():
            logger.info("Song finished, stopping session")
            self.stop()

    def toggle_recording(self) -> None:
        """Toggle recording on/off during session."""
        self._is_recording = not self._is_recording
        self.recording_toggled.emit(self._is_recording)

        if self._is_recording:
            # Capture WHERE in song we started recording
            self._recording_start_song_time = self.timeline.now()
            logger.info(
                f"Recording STARTED at song time "
                f"{self._recording_start_song_time:.2f}s"
            )
            self._recorded_audio.clear()
            self._recorded_frames.clear()
        else:
            # Capture WHERE in song we stopped recording
            self._recording_end_song_time = self.timeline.now()
            duration = (
                self._recording_end_song_time
                - self._recording_start_song_time
            )
            logger.info(
                f"Recording STOPPED at song time "
                f"{self._recording_end_song_time:.2f}s "
                f"(duration: {duration:.2f}s)"
            )

    def is_recording(self) -> bool:
        return self._is_recording

    def _forward_audio(self) -> None:
        """Pull audio chunks from capture; emit level and record."""
        if self.audio_capture is None:
            return

        chunk = self.audio_capture.get_chunk(timeout=0.001)
        if chunk is None:
            return

        # Emit level for UI visualizer
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        self.audio_level_signal.emit(rms)

        # Record if enabled
        if self._is_recording:
            self._recorded_audio.append(chunk.copy())
