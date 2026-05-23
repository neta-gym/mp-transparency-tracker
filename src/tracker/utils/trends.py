"""Score trend tracking — computes deltas between pipeline runs."""

from __future__ import annotations

from ..models.schemas import Leaderboard, LeaderboardEntry, ScoreDelta
from ..utils.logger import get_logger

log = get_logger(__name__)


def compute_deltas(
    current: Leaderboard,
    previous_scores: dict[str, dict],
) -> list[ScoreDelta]:
    """Compare current leaderboard entries against previous run scores.

    Args:
        current: The just-computed leaderboard.
        previous_scores: Dict of {mp_slug: score_json_dict} from the prior run.

    Returns:
        List of ScoreDelta objects, one per MP that has a prior score.
    """
    deltas = []

    for entry in current.entries:
        slug = _name_to_slug(entry.mp_name)
        prev = previous_scores.get(slug)
        if prev is None:
            continue

        prev_composite = prev.get("composite_score", 0.0)
        delta = round(entry.composite_score - prev_composite, 1)

        # Per-dimension deltas
        prev_breakdown = prev.get("breakdown", {})
        dimension_deltas = {}
        for dim in [
            "mplads_score", "asset_score", "criminal_score", "attendance_score",
            "participation_score", "committee_score", "accessibility_score", "legislative_score",
        ]:
            current_val = getattr(entry, dim, 0.0)
            prev_val = prev_breakdown.get(dim, 0.0)
            if current_val != prev_val:
                dimension_deltas[dim] = round(current_val - prev_val, 1)

        deltas.append(ScoreDelta(
            mp_name=entry.mp_name,
            mp_slug=slug,
            state=entry.state,
            current_score=entry.composite_score,
            previous_score=prev_composite,
            delta=delta,
            dimension_deltas=dimension_deltas,
        ))

    return deltas


def annotate_leaderboard_with_deltas(
    leaderboard: Leaderboard,
    previous_scores: dict[str, dict],
) -> None:
    """Annotate leaderboard entries in-place with delta and previous_score fields."""
    for entry in leaderboard.entries:
        slug = _name_to_slug(entry.mp_name)
        prev = previous_scores.get(slug)
        if prev:
            entry.previous_score = prev.get("composite_score")
            if entry.previous_score is not None:
                entry.delta = round(entry.composite_score - entry.previous_score, 1)


def _name_to_slug(name: str) -> str:
    """Convert MP name to slug for matching."""
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
