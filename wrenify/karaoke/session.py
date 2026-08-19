"""
Wrenify — Karaoke session orchestrator.

Wires together all the pieces:
- AudioPlayer (song playback through speakers)
- AudioCapture (mic input)
- StreamingRecognizer (speech-to-text)
- WebcamCapture (video)
- Timeline (state tracking, synced to the player)
- WordMatcher (scoring logic)

Emits Qt signals for UI updates.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from wrenify.audio.capture import AudioCapture
from wrenify.audio.player import AudioPlayer
from wrenify.karaoke.matcher import WordMatcher
from wrenify.karaoke.scorer import Scorer, ScoreReport
from wrenify.karaoke.timeline import Timeline
from wrenify.lyrics.parser import LRCParser
from wrenify.songs.song import Song
from wrenify.speech.recognizer import Word
from wrenify.speech.streaming import StreamingRecognizer
from wrenify.video.camera import WebcamCapture


class KaraokeSession(QObject):
    """
    Runs a full karaoke session end-to-end.

    The instrumental track plays through the speakers while the
    timeline syncs to the actual audio position, so lyrics highlight
    in sync with the music.

    Emits:
        tick_signal(float)        — every UI update tick (song time)
        finished_signal(ScoreReport) — when session ends
    """

    tick_signal     = pyqtSignal(float)
    finished_signal = pyqtSignal(ScoreReport)
    audio_level_signal = pyqtSignal(float)  # RMS 0.0 to 1.0

    UI_UPDATE_INTERVAL_MS: int = 33  # ~30fps

    @property
    def duration(self) -> float:
        """Song duration in seconds (from the loaded audio)."""
        return self._effective_duration

    def __init__(self, song: Song, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.song = song

        # Parse lyrics from the song's .lrc file
        parser = LRCParser()
        self.lyrics = parser.parse_file(song.lyrics_path)

        # Load the instrumental and let the timeline sync to it
        self.player = AudioPlayer()
        self.player.load(song.instrumental_path)

        self.timeline = Timeline(self.lyrics, player=self.player)
        self.matcher  = WordMatcher(self.timeline)
        self.scorer   = Scorer()

        # Auto-stop point: prefer audio duration, fall back to the
        # last word's end time (some LRCs lack timing metadata).
        self._effective_duration = self.player.duration_sec() or (
            max((w.end for w in self.timeline.words), default=0.0) + 3.0
        )

        self.audio_capture: Optional[AudioCapture] = None
        self.streamer:      Optional[StreamingRecognizer] = None
        self.webcam:        Optional[WebcamCapture] = None
        self._audio_forwarder: Optional[QTimer] = None

        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(self.UI_UPDATE_INTERVAL_MS)
        self._ui_timer.timeout.connect(self._on_tick)

        self._running = False
        self._song_started = False

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

        # Start the music (before Whisper warm-up so audio plays ASAP)
        self.player.play(start_position_sec=0.0)
        self._song_started = True

        # Start streaming recognizer with matcher as callback
        self.streamer = StreamingRecognizer(
            on_words_callback=self._on_words_recognized
        )

        # NEW: Give streamer access to current song time so Whisper's
        # chunk-relative timestamps can be converted to song-relative.
        self.streamer.set_song_time_provider(self.timeline.now)

        self.streamer.start()

        # Forward audio chunks to streamer (only if both are alive)
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
        """Stop the session and emit final score."""
        if not self._running:
            return
        logger.info("Stopping karaoke session")

        self._running = False
        self._ui_timer.stop()
        if self._audio_forwarder is not None:
            self._audio_forwarder.stop()
            self._audio_forwarder = None

        # Stop the song
        self.player.stop()

        if self.streamer is not None:
            self.streamer.stop()
            self.streamer = None
        if self.audio_capture is not None:
            self.audio_capture.stop()
            self.audio_capture = None
        if self.webcam is not None:
            self.webcam.stop()
            self.webcam = None

        report = self.scorer.compute(self.timeline)
        logger.info(f"Session finished: {report.summary}")
        self.finished_signal.emit(report)

    def pause(self) -> None:
        """Pause the song; the timeline follows the player."""
        self.player.pause()

    def resume(self) -> None:
        """Resume the song; the timeline follows the player."""
        self.player.resume()

    def _on_tick(self) -> None:
        """Called ~30 times per second from UI timer."""
        current_time = self.timeline.now()
        self.timeline.update_word_states(current_time)
        self.tick_signal.emit(current_time)

        # Auto-stop when the song finishes playing
        if self._song_started and self.player.is_finished():
            logger.info("Song finished, stopping session")
            self.stop()

    def _forward_audio(self) -> None:
        """Pull audio chunks from capture and forward to streamer."""
        if self.audio_capture is None:
            return

        chunk = self.audio_capture.get_chunk(timeout=0.001)
        if chunk is None:
            return

        # Emit level for UI visualizer
        import numpy as np
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        self.audio_level_signal.emit(rms)

        # Forward to Whisper
        if self.streamer is not None:
            self.streamer.push_audio(chunk)

    def _on_words_recognized(self, words: list[Word]) -> None:
        """Called from streaming recognizer thread."""
        try:
            self.matcher.match_recognized_words(words)
        except Exception as e:
            logger.error(f"Match error: {e}")
