"""
Wrenify — Final accuracy scoring for a karaoke session.

Aggregates word states from Timeline into a final performance report.
"""

from __future__ import annotations

from dataclasses import dataclass

from wrenify.karaoke.timeline import Timeline, WordState


@dataclass
class ScoreReport:
    """Final karaoke performance summary."""

    total_words:   int
    correct_count: int
    wrong_count:   int
    missed_count:  int
    pending_count: int          # Never became active (song stopped early?)

    total_score:   float        # 0-100 percentage
    correct_pct:   float
    average_match: float        # Average match score for CORRECT words

    grade: str                  # Letter grade A+ to F

    @property
    def summary(self) -> str:
        return (
            f"Score: {self.total_score:.0f}%  "
            f"Correct: {self.correct_count}/{self.total_words}  "
            f"Grade: {self.grade}"
        )


class Scorer:
    """Computes final scores from a Timeline."""

    def compute(self, timeline: Timeline) -> ScoreReport:
        total = timeline.total_words()

        correct = sum(1 for w in timeline.words if w.state == WordState.CORRECT)
        wrong   = sum(1 for w in timeline.words if w.state == WordState.WRONG)
        missed  = sum(1 for w in timeline.words if w.state == WordState.MISSED)
        pending = sum(1 for w in timeline.words if w.state == WordState.PENDING)

        # Correct gives full point, wrong+missed give zero
        if total == 0:
            score = 0.0
            correct_pct = 0.0
            avg_match = 0.0
        else:
            score = (correct / total) * 100.0
            correct_pct = (correct / total) * 100.0
            match_scores = [
                w.match_score for w in timeline.words
                if w.state == WordState.CORRECT
            ]
            avg_match = (
                sum(match_scores) / len(match_scores)
                if match_scores else 0.0
            )

        return ScoreReport(
            total_words=total,
            correct_count=correct,
            wrong_count=wrong,
            missed_count=missed,
            pending_count=pending,
            total_score=score,
            correct_pct=correct_pct,
            average_match=avg_match,
            grade=self._grade(score),
        )

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 95:
            return "A+"
        if score >= 90:
            return "A"
        if score >= 85:
            return "A-"
        if score >= 80:
            return "B+"
        if score >= 75:
            return "B"
        if score >= 70:
            return "B-"
        if score >= 65:
            return "C+"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "F"
