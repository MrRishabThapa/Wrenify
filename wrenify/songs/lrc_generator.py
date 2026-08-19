"""
Wrenify — Auto-generate LRC from audio using faster-whisper.

Transcribes audio and outputs standard .lrc format with
per-word timestamps. Best results on isolated vocals (from Demucs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

from wrenify.speech.recognizer import SpeechRecognizer, Word


@dataclass
class LRCGeneratorConfig:
    line_break_gap_sec: float = 1.5
    max_words_per_line: int = 10
    title:  Optional[str] = None
    artist: Optional[str] = None
    album:  Optional[str] = None


class LRCGenerator:
    def __init__(self) -> None:
        self.recognizer = SpeechRecognizer()

    def generate(
        self,
        audio_path: Path,
        config: Optional[LRCGeneratorConfig] = None,
    ) -> str:
        cfg = config or LRCGeneratorConfig()
        audio_path = Path(audio_path)

        logger.info(f"Transcribing {audio_path.name} for LRC...")

        result = self.recognizer.transcribe(audio_path)

        logger.info(
            f"Got {result.word_count} words in {result.processing_time:.1f}s"
        )

        if result.word_count < 5:
            logger.warning(
                "Very few words detected. This might be instrumental. "
                "Use a vocal track for best results."
            )

        lines = self._group_into_lines(
            result.words, cfg.line_break_gap_sec, cfg.max_words_per_line
        )

        return self._build_lrc(lines, cfg, result.duration)

    def generate_and_save(
        self,
        audio_path: Path,
        output_path: Path,
        config: Optional[LRCGeneratorConfig] = None,
    ) -> Path:
        output_path = Path(output_path)
        content = self.generate(audio_path, config)
        output_path.write_text(content, encoding="utf-8")
        logger.success(f"LRC saved: {output_path}")
        return output_path

    def _group_into_lines(
        self, words: list[Word], gap: float, max_per_line: int
    ) -> list[list[Word]]:
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

    def _build_lrc(
        self,
        lines: list[list[Word]],
        cfg: LRCGeneratorConfig,
        duration: float,
    ) -> str:
        parts: list[str] = []

        if cfg.title:
            parts.append(f"[ti:{cfg.title}]")
        if cfg.artist:
            parts.append(f"[ar:{cfg.artist}]")
        if cfg.album:
            parts.append(f"[al:{cfg.album}]")

        m, s = divmod(int(duration), 60)
        parts.append(f"[length:{m:02d}:{s:02d}]")
        parts.append("[re:Wrenify LRC Generator]")
        parts.append("")

        for word_list in lines:
            if not word_list:
                continue
            ts = self._fmt_ts(word_list[0].start)
            line_text = " ".join(w.text for w in word_list)
            parts.append(f"{ts}{line_text}")

        return "\n".join(parts) + "\n"

    @staticmethod
    def _fmt_ts(sec: float) -> str:
        m, s = divmod(sec, 60)
        return f"[{int(m):02d}:{s:05.2f}]"


# ────────────────────── Standalone test ──────────────────────

if __name__ == "__main__":
    import sys

    from rich.console import Console

    console = Console()
    console.print("\n[bold cyan]LRC Generator (Whisper)[/bold cyan]\n")

    if len(sys.argv) < 2:
        console.print(
            "[red]Usage:[/red] "
            "python -m wrenify.songs.lrc_generator <audio.wav> [output.lrc]"
        )
        sys.exit(1)

    audio = Path(sys.argv[1])
    if not audio.exists():
        console.print(f"[red]Not found:[/red] {audio}")
        sys.exit(1)

    out = Path(sys.argv[2]) if len(sys.argv) > 2 else audio.with_suffix(".lrc")
    console.print(f"[cyan]Audio:[/cyan]   {audio}")
    console.print(f"[cyan]Output:[/cyan]  {out}")
    console.print("[dim]First run downloads the Whisper model (~74MB)...[/dim]\n")

    generator = LRCGenerator()
    generator.generate_and_save(audio, out)

    console.print(f"\n[green]LRC saved:[/green] {out}")
    console.print("[dim]Preview:[/dim]")
    console.print(out.read_text(encoding="utf-8")[:600])