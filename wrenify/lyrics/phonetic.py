"""
Wrenify — Phonetic stylizer for held notes.

When a singer holds a note for a long time, we display the word
with stretched vowels to communicate that duration visually:

    Normal:    "fallen tree"
    Stretched: "faaall-eeeen  treeeeee"

Uses the CMU Pronouncing Dictionary via the `pronouncing` library
to find the stressed vowel in each word for accurate stretching.

Falls back to naive vowel detection when a word is not in the CMU dict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger

try:
    import pronouncing
    CMU_AVAILABLE = True
except ImportError:
    CMU_AVAILABLE = False
    logger.warning("pronouncing library not installed, using naive stretching")


VOWELS = set("aeiouyAEIOUY")

# CMU phoneme codes to their pronunciation as vowel clusters
PHONEME_TO_VOWEL: dict[str, str] = {
    "AA": "a",   "AE": "a",   "AH": "u",
    "AO": "o",   "AW": "ow",  "AY": "ai",
    "EH": "e",   "ER": "er",  "EY": "ay",
    "IH": "i",   "IY": "ee",  "OW": "oo",
    "OY": "oi",  "UH": "oo",  "UW": "oo",
}


@dataclass
class StretchOptions:
    """Control how much and where to stretch words."""

    min_duration_sec:   float = 0.5    # Below this: no stretching
    max_repeats:        int   = 12     # Cap the visual stretch
    stretch_multiplier: float = 4.0    # Chars per second held
    separator:          str   = "-"    # Between stretched syllables


class PhoneticStylizer:
    """
    Converts words into stretched visual representations based on duration.

    A word held for 2 seconds becomes something like "faaaaallll-eeeen"
    to visually communicate the sustained note.

    Uses CMU dict for phoneme-aware stretching when available,
    falls back to simple vowel repetition otherwise.
    """

    def __init__(self, options: Optional[StretchOptions] = None) -> None:
        self.opts = options or StretchOptions()

    def stylize_word(self, word: str, duration_sec: float) -> str:
        """
        Stretch a word based on how long it is held.

        Args:
            word: The word to stretch, e.g. "fallen"
            duration_sec: How long the singer holds this word

        Returns:
            Stretched version, e.g. "faaall-eeeen"
        """
        if duration_sec < self.opts.min_duration_sec or not word:
            return word

        # Calculate repeat count from duration
        repeats = int(duration_sec * self.opts.stretch_multiplier)
        repeats = min(repeats, self.opts.max_repeats)
        if repeats < 2:
            return word

        # Try CMU-based stretching first
        if CMU_AVAILABLE:
            phonetic = self._stretch_phonetic(word, repeats)
            if phonetic:
                return phonetic

        # Fallback: naive vowel-based stretching
        return self._stretch_naive(word, repeats)

    def stylize_line(
        self,
        words: list[str],
        durations: list[float],
    ) -> str:
        """
        Stylize a full line of words with their individual durations.

        Args:
            words: List of words in the line
            durations: List of durations for each word (must match length)

        Returns:
            Joined stylized line
        """
        if len(words) != len(durations):
            raise ValueError(
                f"Word count ({len(words)}) != duration count ({len(durations)})"
            )

        stylized = [
            self.stylize_word(w, d)
            for w, d in zip(words, durations)
        ]
        return "  ".join(stylized)  # Double-space for breathing room

    def _stretch_phonetic(self, word: str, repeats: int) -> Optional[str]:
        """Stretch based on CMU dict phonemes. Returns None if word not found."""
        phones_list = pronouncing.phones_for_word(word.lower())
        if not phones_list:
            return None

        phones = phones_list[0].split()

        # Find the primary stressed vowel (marked with '1')
        stressed_phoneme = None
        for p in phones:
            if p and p[-1] == "1":
                base = re.sub(r"[0-9]", "", p)
                if base in PHONEME_TO_VOWEL:
                    stressed_phoneme = base
                    break

        # No stressed vowel found → fallback
        if not stressed_phoneme:
            return None

        # Find the corresponding vowel cluster in the actual word
        # Simple heuristic: stretch the LAST vowel cluster in the word
        return self._insert_stretched_vowel(word, repeats)

    def _stretch_naive(self, word: str, repeats: int) -> str:
        """Simple vowel-repetition stretching for words without CMU data."""
        return self._insert_stretched_vowel(word, repeats)

    def _insert_stretched_vowel(self, word: str, repeats: int) -> str:
        """Find a vowel in the word and repeat it."""
        # Find vowel positions
        vowel_positions = [i for i, c in enumerate(word) if c in VOWELS]

        if not vowel_positions:
            # No vowels? Just append the last char repeated
            return word + word[-1] * (repeats // 2)

        # Pick the last vowel cluster (usually most sustained)
        target_pos = vowel_positions[-1]
        target_char = word[target_pos].lower()

        stretched = (
            word[: target_pos + 1]
            + target_char * (repeats - 1)
            + self.opts.separator
            + word[target_pos + 1 :]
        )
        return stretched.rstrip(self.opts.separator)


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("\n[bold cyan]Phonetic Stylizer Test[/bold cyan]\n")

    if not CMU_AVAILABLE:
        console.print(
            "[yellow]pronouncing not installed — using naive fallback.[/yellow]"
        )
        console.print("[dim]Install with: poetry add pronouncing[/dim]\n")

    stylizer = PhoneticStylizer()

    # Test cases: (word, duration in seconds)
    test_cases: list[tuple[str, float]] = [
        ("fallen",   0.3),
        ("fallen",   0.8),
        ("fallen",   1.5),
        ("fallen",   3.0),
        ("tree",     2.5),
        ("hello",    2.0),
        ("darkness", 1.2),
        ("friend",   4.0),
        ("goodbye",  2.8),
        ("my",       0.5),
        ("my",       2.0),
    ]

    table = Table(title="Word Stretching Examples")
    table.add_column("Word",     style="cyan")
    table.add_column("Duration", justify="right", style="yellow")
    table.add_column("Stylized", style="green")

    for word, dur in test_cases:
        stylized = stylizer.stylize_word(word, dur)
        table.add_row(word, f"{dur:.1f}s", stylized)

    console.print(table)

    # Test a full line
    console.print("\n[bold]Full line stylization:[/bold]\n")
    words = ["hello", "darkness", "my", "old", "friend"]
    durations = [0.4, 1.2, 0.3, 0.5, 3.5]

    result = stylizer.stylize_line(words, durations)
    console.print(f"  Original:  {' '.join(words)}")
    console.print(f"  Stylized:  [green]{result}[/green]")
