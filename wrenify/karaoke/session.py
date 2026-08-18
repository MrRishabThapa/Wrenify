"""
Wrenify — Karaoke session orchestrator.

Wires together all the pieces:
- AudioCapture (mic input)
- StreamingRecognizer (speech-to-text)
- WebcamCapture (video)
- Timeline (state tracking)
- WordMatcher (scoring logic)

Emits Qt signals for UI updates.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from wrenify.audio.capture import AudioCapture
from wrenify.karaoke.matcher import WordMatcher
from wrenify.karaoke.scorer import Scorer, ScoreReport
from wrenify.karaoke.timeline import Timeline
from wrenify.lyrics.parser import ParsedLyrics
from wrenify.speech.recognizer import Word
from wrenify.speech.streaming import StreamingRecognizer
from wrenify.video.camera import WebcamCapture


class KaraokeSession(QObject):
    """
    Runs a full karaoke session end-to-end.

    Emits:
        tick_signal(float)        — every UI update tick (song time)
        finished_signal(ScoreReport) — when session ends
    """

    tick_signal     = pyqtSignal(float)
    finished_signal = pyqtSignal(ScoreReport)

    UI_UPDATE_INTERVAL_MS: int = 33  # ~30fps

    @property
    def duration(self) -> float:
        """Effective song duration in seconds (used for auto-stop)."""
        return self._effective_duration

    def __init__(self, lyrics: ParsedLyrics, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.lyrics = lyrics

        self.timeline = Timeline(lyrics)
        self.matcher  = WordMatcher(self.timeline)
        self.scorer   = Scorer()

        # Auto-stop point: prefer [length:] metadata, fall back to
        # the last word's end time (most fetched LRCs lack duration).
        if lyrics.duration:
            self._effective_duration = lyrics.duration
        elif self.timeline.words:
            self._effective_duration = (
                max(w.end for w in self.timeline.words) + 3.0
            )
        else:
            self._effective_duration = 0.0

        self.audio_capture: Optional[AudioCapture] = None
        self.streamer:      Optional[StreamingRecognizer] = None
        self.webcam:        Optional[WebcamCapture] = None
        self._audio_forwarder: Optional[QTimer] = None

        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(self.UI_UPDATE_INTERVAL_MS)
        self._ui_timer.timeout.connect(self._on_tick)

        self._running = False

    def start(self) -> None:
        """Start the karaoke session."""
        if self._running:
            return

        logger.info("Starting karaoke session")

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

        # Start streaming recognizer with matcher as callback
        self.streamer = StreamingRecognizer(
            on_words_callback=self._on_words_recognized
        )
        self.streamer.start()

        # Start timeline clock
        self.timeline.start()

        # Forward audio chunks to streamer (only if both are alive)
        if self.audio_capture is not None:
            self._audio_forwarder = QTimer(self)
            self._audio_forwarder.setInterval(10)  # 100Hz polling
            self._audio_forwarder.timeout.connect(self._forward_audio)
            self._audio_forwarder.start()

        # Start UI ticker
        self._ui_timer.start()
        self._running = True
        logger.info("Karaoke session running")

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

        self.timeline.stop()

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
        """Pause the session clock."""
        self.timeline.pause()

    def resume(self) -> None:
        """Resume the session clock."""
        self.timeline.resume()

    def _on_tick(self) -> None:
        """Called ~30 times per second from UI timer."""
        current_time = self.timeline.now()
        self.timeline.update_word_states(current_time)
        self.tick_signal.emit(current_time)

        # Auto-stop if past the song end
        if current_time > self._effective_duration + 2.0:
            self.stop()

    def _forward_audio(self) -> None:
        """Pull audio chunks from capture and forward to streamer."""
        if self.audio_capture is None or self.streamer is None:
            return
        chunk = self.audio_capture.get_chunk(timeout=0.001)
        if chunk is not None:
            self.streamer.push_audio(chunk)

    def _on_words_recognized(self, words: list[Word]) -> None:
        """Called from streaming recognizer thread."""
        try:
            self.matcher.match_recognized_words(words)
        except Exception as e:
            logger.error(f"Match error: {e}")
