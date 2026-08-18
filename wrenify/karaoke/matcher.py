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
        score >= 0.75 -> CORRECT (green)
        score <  0.75 -> WRONG (red)
    """

    CORRECT_THRESHOLD: float = 0.75

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
        """
        results: list[MatchResult] = []

        for rec in recognized_words:
            rec_time = rec.start
            candidates = self.timeline.find_matchable_words(rec_time)
            if not candidates:
                continue

            # Find best match among candidates
            best: MatchResult | None = None
            for candidate in candidates:
                score = self._similarity(rec.text, candidate.text)
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
                logger.debug(
                    f"CORRECT: heard '{best.recognized}' -> "
                    f"'{best.tracked_word.text}' ({best.score:.2f})"
                )
            else:
                # Only mark WRONG if we're sure it's not just a partial
                if best.score > 0.3:
                    self.timeline.mark_word_wrong(best.tracked_word, best.score)
                    logger.debug(
                        f"WRONG: heard '{best.recognized}' vs "
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

        # Bonus for matching first character (helps with mumbles)
        if a[0] == b[0]:
            ratio = min(1.0, ratio + 0.05)

        return ratio

    @staticmethod
    def _normalize(word: str) -> str:
        """Lowercase, strip punctuation, remove filler chars."""
        cleaned = re.sub(r"[^\w']", "", word.lower())
        return cleaned.strip()
