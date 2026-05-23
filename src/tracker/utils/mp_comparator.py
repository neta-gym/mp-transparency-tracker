"""MP Comparison tool — side-by-side comparison of two or more MPs."""

from __future__ import annotations

from ..models.schemas import ScoreResult, ScoreBreakdown
from ..utils.logger import get_logger

log = get_logger(__name__)

# Dimension labels for display
_DIMENSIONS = [
    ("mplads_score", "MPLADS Fund Utilization"),
    ("asset_score", "Asset Transparency"),
    ("criminal_score", "Criminal Record"),
    ("attendance_score", "Attendance"),
    ("participation_score", "Questions & Debates"),
    ("committee_score", "Committee Engagement"),
    ("accessibility_score", "Public Accessibility"),
    ("legislative_score", "Legislative Effectiveness"),
]


class ComparisonResult:
    """Result of comparing two or more MPs."""

    def __init__(self, scores: list[ScoreResult]) -> None:
        self.scores = scores
        self.mp_names = [s.mp.name for s in scores]
        self.dimensions = self._build_dimension_comparison()
        self.winner_index = self._overall_winner()

    def _build_dimension_comparison(self) -> list[dict]:
        """Build per-dimension comparison rows."""
        rows = []
        for attr, label in _DIMENSIONS:
            values = [getattr(s.breakdown, attr) for s in self.scores]
            best = max(values)
            winner_idx = values.index(best) if values.count(best) == 1 else -1
            rows.append({
                "dimension": label,
                "attr": attr,
                "values": values,
                "winner_index": winner_idx,
                "spread": max(values) - min(values),
            })
        return rows

    def _overall_winner(self) -> int:
        """Index of the MP with the highest composite score, or -1 if tied."""
        composites = [s.composite_score for s in self.scores]
        best = max(composites)
        if composites.count(best) > 1:
            return -1
        return composites.index(best)

    def to_markdown(self) -> str:
        """Render comparison as a Markdown table."""
        names = self.mp_names
        n = len(names)

        lines = [
            f"# MP Comparison: {' vs '.join(names)}",
            "",
        ]

        # Overview
        lines.append("## Overall Scores")
        lines.append("")
        header = "| Metric |" + " | ".join(names) + " |"
        sep = "|--------|" + " | ".join(["------"] * n) + " |"
        lines.extend([header, sep])

        composites = [f"**{s.composite_score:.1f}**" for s in self.scores]
        lines.append("| Composite Score | " + " | ".join(composites) + " |")
        confidences = [f"{s.data_confidence:.0%}" for s in self.scores]
        lines.append("| Data Confidence | " + " | ".join(confidences) + " |")
        parties = [s.mp.party for s in self.scores]
        lines.append("| Party | " + " | ".join(parties) + " |")
        consts = [s.mp.constituency for s in self.scores]
        lines.append("| Constituency | " + " | ".join(consts) + " |")

        # Dimension breakdown
        lines.extend(["", "## Dimension Breakdown", ""])
        header2 = "| Dimension |" + " | ".join(names) + " | Advantage |"
        sep2 = "|-----------|" + " | ".join(["------"] * n) + " |-----------|"
        lines.extend([header2, sep2])

        for row in self.dimensions:
            vals = []
            for i, v in enumerate(row["values"]):
                if i == row["winner_index"]:
                    vals.append(f"**{v:.1f}**")
                else:
                    vals.append(f"{v:.1f}")
            advantage = names[row["winner_index"]] if row["winner_index"] >= 0 else "Tie"
            lines.append(f"| {row['dimension']} | " + " | ".join(vals) + f" | {advantage} |")

        # Summary
        lines.extend(["", "## Summary", ""])
        wins = [0] * n
        for row in self.dimensions:
            if row["winner_index"] >= 0:
                wins[row["winner_index"]] += 1
        for i, name in enumerate(names):
            lines.append(f"- **{name}**: leads in {wins[i]}/{len(self.dimensions)} dimensions")

        if self.winner_index >= 0:
            lines.append(f"\n**Overall leader: {names[self.winner_index]}** "
                         f"({self.scores[self.winner_index].composite_score:.1f}/100)")

        return "\n".join(lines)


def compare_mps(scores: list[ScoreResult]) -> ComparisonResult:
    """Compare two or more MPs by their scored results."""
    if len(scores) < 2:
        raise ValueError("Need at least 2 MPs to compare")
    return ComparisonResult(scores)
