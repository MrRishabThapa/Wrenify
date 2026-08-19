"""
Wrenify — Fuzzy word matching for karaoke scoring.

Matches recognized speech words against expected lyric words using:
- Levenshtein edit distance
- Optional phonetic similarity (via metaphone or CMU)
- Time-window constraints from Timeline
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import Levenshtein
from loguru import logger

from wrenify.karaoke.timeline import Timeline, TrackedWord
from wrenify.speech.recognizer import Word


@dataclass
class MatchResult:
    """Result of matching a recognized word against a tracked word."""

    tracked_word: TrackedWord
    recognized:   str
    score:        float          # 0.0 to 1.0
    is_correct:   bool           # Score above CORRECT_THRESHOLD


class WordMatcher:
    """
    Matches recognized speech to expected lyrics.

    Thresholds:
        score >= 0.65 -> CORRECT (green)
        score <  0.65 -> WRONG (red)
    """

    CORRECT_THRESHOLD: float = 0.65

    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline

    def match_recognized_words(
        self,
        recognized_words: list[Word],
    ) -> list[MatchResult]:
        """
        Match a batch of recognized words against the timeline.

        Called from streaming recognizer callback. Each recognized
        word is compared to the ACTIVE and nearby PENDING words.

        NOTE: recognized word timestamps arrive song-relative
        (the StreamingRecognizer converts chunk-relative Whisper
        timestamps before invoking the callback).
        """
        results: list[MatchResult] = []

        current_song_time = self.timeline.now()
        logger.info(
            f"MATCHER: got {len(recognized_words)} recognized words "
            f"at song time {current_song_time:.2f}s"
        )

        for rec in recognized_words:
            # Song-relative already (converted by StreamingRecognizer)
            rec_song_time = rec.start

            logger.info(
                f"  Word '{rec.text}' at song-time {rec_song_time:.2f}s "
                f"(chunk-rel {rec.start:.2f}s, song now {current_song_time:.2f}s)"
            )

            candidates = self.timeline.find_matchable_words(rec_song_time)

            if not candidates:
                logger.warning(
                    f"    No candidates within "
                    f"{self.timeline.MATCH_WINDOW_SEC}s of song time "
                    f"{rec_song_time:.2f}s"
                )
                # Show what words ARE nearby for debugging
                nearby = [
                    w for w in self.timeline.words
                    if abs(w.start - rec_song_time) <= 5.0
                ]
                if nearby:
                    logger.info(
                        f"    Nearby words: "
                        f"{[(w.text, w.start) for w in nearby[:5]]}"
                    )
                continue

            logger.info(
                f"    Candidates: "
                f"{[(w.text, w.start, w.state.value) for w in candidates]}"
            )

            # Find best match among candidates
            best: MatchResult | None = None
            for candidate in candidates:
                score = self._similarity(rec.text, candidate.text)
                logger.debug(
                    f"      '{rec.text}' vs '{candidate.text}' = {score:.2f}"
                )
                if best is None or score > best.score:
                    best = MatchResult(
                        tracked_word=candidate,
                        recognized=rec.text,
                        score=score,
                        is_correct=score >= self.CORRECT_THRESHOLD,
                    )

            if best is None:
                continue

            # Apply state change
            if best.is_correct:
                self.timeline.mark_word_correct(best.tracked_word, best.score)
                logger.success(
                    f"  CORRECT: '{best.recognized}' -> "
                    f"'{best.tracked_word.text}' ({best.score:.2f})"
                )
            else:
                # Only mark WRONG if we're sure it's not just a partial
                if best.score > 0.3:
                    self.timeline.mark_word_wrong(best.tracked_word, best.score)
                    logger.warning(
                        f"  WRONG: '{best.recognized}' vs "
                        f"'{best.tracked_word.text}' ({best.score:.2f})"
                    )
                else:
                    logger.info(
                        f"  NO MATCH: '{best.recognized}' best was "
                        f"'{best.tracked_word.text}' ({best.score:.2f})"
                    )

            results.append(best)

        return results

    def _similarity(self, recognized: str, expected: str) -> float:
        """
        Compute similarity between two words (0.0 to 1.0).

        Uses normalized Levenshtein ratio + light phonetic bonus.
        """
        a = self._normalize(recognized)
        b = self._normalize(expected)

        if not a or not b:
            return 0.0

        if a == b:
            return 1.0

        # Levenshtein ratio (already normalized 0-1)
        ratio = Levenshtein.ratio(a, b)

        # BONUS: matching first two chars (helps with mumbled starts)
        if len(a) >= 2 and len(b) >= 2 and a[:2] == b[:2]:
            ratio = min(1.0, ratio + 0.1)
        elif a[0] == b[0]:
            ratio = min(1.0, ratio + 0.05)

        # BONUS: if 'expected' word is contained in 'recognized' (or vice
        # versa). Helps when Whisper hears "dandelions" and lyric says
        # "dandelion".
        if len(a) >= 4 and len(b) >= 4:
            if a in b or b in a:
                ratio = min(1.0, ratio + 0.15)

        return ratio

    @staticmethod
    def _normalize(word: str) -> str:
        """Lowercase, strip punctuation, remove filler chars."""
        cleaned = re.sub(r"[^\w']", "", word.lower())
        return cleaned.strip()
