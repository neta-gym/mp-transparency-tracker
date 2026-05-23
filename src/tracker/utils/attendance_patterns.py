"""Attendance pattern analysis — goes beyond a single percentage."""

from __future__ import annotations

from ..models.schemas import AttendancePattern
from ..utils.logger import get_logger

log = get_logger(__name__)


def analyze_attendance(
    overall_pct: float | None,
    session_data: dict[str, float] | None = None,
    is_minister: bool = False,
) -> AttendancePattern:
    """Analyze attendance patterns to identify behavioral trends.

    Args:
        overall_pct: Overall attendance percentage.
        session_data: Dict of {session_name: attendance_%} for breakdown.
        is_minister: Ministers have legitimate reasons for lower attendance.
    """
    if overall_pct is None:
        return AttendancePattern(confidence=0.0)

    session_breakdown = session_data or {}
    pattern = AttendancePattern(
        overall_pct=overall_pct,
        session_breakdown=session_breakdown,
    )

    if not session_breakdown:
        # Without session-level data, we can only classify by overall %
        pattern.pattern_label = _classify_overall(overall_pct, is_minister)
        pattern.confidence = 0.4
        return pattern

    # Analyze session-level patterns
    values = list(session_breakdown.values())
    if len(values) < 2:
        pattern.pattern_label = _classify_overall(overall_pct, is_minister)
        pattern.confidence = 0.5
        return pattern

    max_pct = max(values)
    min_pct = min(values)
    spread = max_pct - min_pct

    # Identify which sessions have lowest attendance
    sorted_sessions = sorted(session_breakdown.items(), key=lambda x: x[1])
    worst_session = sorted_sessions[0][0] if sorted_sessions else ""

    # Consecutive absence streak (estimated from session gaps)
    low_sessions = sum(1 for v in values if v < 50)
    pattern.consecutive_absences = low_sessions  # rough proxy

    # Key debate detection
    budget_sessions = [k for k in session_breakdown if "budget" in k.lower()]
    if budget_sessions:
        budget_attendance = session_breakdown[budget_sessions[0]]
        pattern.attended_key_debates = budget_attendance >= 50

    # Pattern classification
    if is_minister:
        pattern.pattern_label = "Minister (executive duties)"
    elif spread < 15:
        pattern.pattern_label = "Consistent" if overall_pct >= 70 else "Consistently low"
    elif "monsoon" in worst_session.lower() and min_pct < 50:
        pattern.pattern_label = "Monsoon slumper"
    elif not pattern.attended_key_debates:
        pattern.pattern_label = "Key debate skipper"
    elif max_pct > 80 and min_pct < 40:
        pattern.pattern_label = "Highly variable"
    else:
        pattern.pattern_label = _classify_overall(overall_pct, is_minister)

    pattern.confidence = 0.7
    return pattern


def _classify_overall(pct: float, is_minister: bool) -> str:
    """Simple classification based on overall attendance percentage."""
    if is_minister:
        return "Minister (executive duties)"
    if pct >= 85:
        return "Exemplary"
    if pct >= 70:
        return "Regular"
    if pct >= 50:
        return "Below average"
    return "Poor"
