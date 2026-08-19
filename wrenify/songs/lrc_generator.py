"""
Wrenify — LRC generation with two modes:

MODE 1: whisper_only (fast, messy)
  Uses Whisper transcription as-is
  Words come from Whisper (may be wrong)
  Timing accurate to Whisper

MODE 2: hybrid (slow, clean)  ← RECOMMENDED
  Fetches clean lyrics from Genius/Musixmatch
  Uses Whisper only for word timing
  Words are clean and punctuated
  Timing perfectly aligned to your audio
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

from wrenify.lyrics.aligner import LyricsAligner, format_as_lrc
from wrenify.lyrics.fetcher import LyricsFetcher
from wrenify.speech.recognizer import SpeechRecognizer, Word


class LRCMode(Enum):
    """LRC generation strategy."""

    WHISPER_ONLY = "whisper_only"  # Fast, messy
    HYBRID = "hybrid"              # Slow, clean (default)


@dataclass
class LRCGeneratorConfig:
    mode:    LRCMode = LRCMode.HYBRID
    title:   Optional[str] = None
    artist:  Optional[str] = None
    album:   Optional[str] = None

    # For whisper_only mode
    line_break_gap_sec: float = 1.5
    max_words_per_line: int = 10


class LRCGenerator:
    """Generates LRC files with clean text and accurate timing."""

    def __init__(self) -> None:
        self.recognizer = SpeechRecognizer()
        self.fetcher = LyricsFetcher()
        self.aligner = LyricsAligner()

    def generate(
        self,
        audio_path: Path,
        config: Optional[LRCGeneratorConfig] = None,
    ) -> str:
        cfg = config or LRCGeneratorConfig()
        audio_path = Path(audio_path)

        if cfg.mode == LRCMode.HYBRID:
            return self._generate_hybrid(audio_path, cfg)
        else:
            return self._generate_whisper_only(audio_path, cfg)

    def _generate_hybrid(
        self,
        audio_path: Path,
        cfg: LRCGeneratorConfig,
    ) -> str:
        """
        Hybrid mode: clean lyrics from Genius + timestamps from Whisper.
        """
        logger.info("Hybrid mode: fetching clean lyrics + aligning...")

        # 1. Fetch clean lyrics
        if not cfg.title or not cfg.artist:
            logger.warning("No title/artist — falling back to whisper_only")
            return self._generate_whisper_only(audio_path, cfg)

        clean_lyrics = self.fetcher.fetch_plain_lyrics(cfg.title, cfg.artist)

        if not clean_lyrics:
            logger.warning(
                f"No clean lyrics found for {cfg.title} - {cfg.artist}. "
                f"Falling back to whisper_only mode."
            )
            return self._generate_whisper_only(audio_path, cfg)

        logger.success(f"Fetched clean lyrics ({len(clean_lyrics)} chars)")

        # 2. Transcribe audio with Whisper (for timestamps)
        logger.info("Transcribing audio for timing...")
        result = self.recognizer.transcribe(audio_path)

        if not result.words:
            logger.error("Whisper found no words. Check audio quality.")
            return self._build_lrc_no_timing(clean_lyrics, cfg, result.duration)

        logger.info(f"Whisper found {result.word_count} words for alignment")

        # 3. Align clean lyrics to Whisper timestamps
        aligned = self.aligner.align(clean_lyrics, result.words)

        if not aligned:
            logger.error("Alignment failed, using no-timing fallback")
            return self._build_lrc_no_timing(clean_lyrics, cfg, result.duration)

        # 4. Quality gate: if most lines had to be guessed, the fetched
        # lyrics don't match what is actually sung (different version,
        # live arrangement, wrong song). Prefer Whisper's own text then.
        estimated = sum(1 for line in aligned if line.estimated)
        if estimated / len(aligned) > 0.5:
            logger.warning(
                f"{estimated}/{len(aligned)} lines were estimated — fetched "
                f"lyrics don't match the audio. Falling back to whisper_only."
            )
            return self._generate_whisper_only(audio_path, cfg)

        # 5. Format as LRC
        return format_as_lrc(
            aligned,
            title=cfg.title or "",
            artist=cfg.artist or "",
            album=cfg.album or "",
            duration_sec=result.duration,
        )

    def _generate_whisper_only(
        self,
        audio_path: Path,
        cfg: LRCGeneratorConfig,
    ) -> str:
        """
        Whisper-only mode: use raw Whisper output.
        Falls back to this when clean lyrics unavailable.
        """
        logger.info("Whisper-only mode: transcribing directly...")

        result = self.recognizer.transcribe(audio_path)
        logger.info(f"Got {result.word_count} words")

        if result.word_count < 5:
            logger.warning("Very few words detected — is this instrumental?")

        # Group into lines (existing logic)
        lines = self._group_into_lines(
            result.words,
            cfg.line_break_gap_sec,
            cfg.max_words_per_line,
        )

        return self._build_lrc_from_grouped(lines, cfg, result.duration)

    def _group_into_lines(
        self,
        words: list[Word],
        gap: float,
        max_per_line: int,
    ) -> list[list[Word]]:
        """Existing line grouping logic (unchanged)."""
        if not words:
            return []

        lines: list[list[Word]] = []
        current: list[Word] = [words[0]]

        for i in range(1, len(words)):
            prev, curr = words[i - 1], words[i]
            time_gap = curr.start - prev.end
            line_full = len(current) >= max_per_line
            sentence_end = prev.text.rstrip().endswith((".", "?", "!"))

            if time_gap >= gap or line_full or sentence_end:
                lines.append(current)
                current = [curr]
            else:
                current.append(curr)

        if current:
            lines.append(current)
        return lines

    def _build_lrc_from_grouped(
        self,
        lines: list[list[Word]],
        cfg: LRCGeneratorConfig,
        duration: float,
    ) -> str:
        """Build LRC from grouped Whisper words."""
        from wrenify.lyrics.aligner import AlignedLine

        aligned = []
        for word_list in lines:
            if word_list:
                text = " ".join(w.text for w in word_list)
                aligned.append(AlignedLine(text=text, start=word_list[0].start))

        return format_as_lrc(
            aligned,
            title=cfg.title or "",
            artist=cfg.artist or "",
            album=cfg.album or "",
            duration_sec=duration,
        )

    def _build_lrc_no_timing(
        self,
        clean_lyrics: str,
        cfg: LRCGeneratorConfig,
        duration: float,
    ) -> str:
        """Last-resort: lyrics with estimated timing."""
        from wrenify.lyrics.aligner import AlignedLine

        lines = [line.strip() for line in clean_lyrics.split("\n") if line.strip()]
        if not lines:
            return ""

        # Distribute evenly across duration
        per_line = duration / len(lines) if duration > 0 else 3.0
        aligned = [
            AlignedLine(text=line, start=i * per_line)
            for i, line in enumerate(lines)
        ]

        logger.warning("Using estimated line timing (no Whisper words)")
        return format_as_lrc(
            aligned,
            title=cfg.title or "",
            artist=cfg.artist or "",
            album=cfg.album or "",
            duration_sec=duration,
        )

    def generate_and_save(
        self,
        audio_path: Path,
        output_path: Path,
        config: Optional[LRCGeneratorConfig] = None,
    ) -> Path:
        content = self.generate(audio_path, config)
        Path(output_path).write_text(content, encoding="utf-8")
        logger.success(f"LRC saved: {output_path}")
        return output_path


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print("\n[bold cyan]LRC Generator (Hybrid)[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print(
            "[red]Usage:[/red] "
            "python -m wrenify.songs.lrc_generator <audio.wav> "
            "[\"title\"] [\"artist\"]"
        )
        sys.exit(1)

    audio = Path(sys.argv[1])
    if not audio.exists():
        console.print(f"[red]Not found:[/red] {audio}")
        sys.exit(1)

    title  = sys.argv[2] if len(sys.argv) > 2 else Prompt.ask("[cyan]Title[/cyan]")
    artist = sys.argv[3] if len(sys.argv) > 3 else Prompt.ask("[cyan]Artist[/cyan]")
    out = audio.with_suffix(".lrc")

    console.print(f"[cyan]Audio:[/cyan]  {audio}")
    console.print(f"[cyan]Song:[/cyan]   {artist} - {title}")
    console.print("[dim]Hybrid mode: Genius lyrics + Whisper timing[/dim]\n")

    generator = LRCGenerator()
    generator.generate_and_save(
        audio,
        out,
        LRCGeneratorConfig(mode=LRCMode.HYBRID, title=title, artist=artist),
    )

    console.print(f"\n[green]LRC saved:[/green] {out}")
    console.print("[dim]Preview:[/dim]")
    console.print(out.read_text(encoding="utf-8")[:800])
