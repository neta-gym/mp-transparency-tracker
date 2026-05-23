"""Assessor agent — calculates composite 0-100 transparency score."""

from __future__ import annotations

from ..config import settings
from ..models.schemas import (
    ValidatedFindings,
    ScoreBreakdown,
    ScoreResult,
    EvidenceGrade,
)
from ..storage.database import Database
from ..utils.logger import get_logger
from ..utils.mplads_calc import adjusted_utilization_rate
from .base import BaseAgent

log = get_logger(__name__)

# Evidence grade multipliers — higher grades get more scoring weight
_GRADE_MULTIPLIERS: dict[str, float] = {
    EvidenceGrade.A.value: 1.0,
    EvidenceGrade.B.value: 0.9,
    EvidenceGrade.C.value: 0.7,
    EvidenceGrade.D.value: 0.5,
    EvidenceGrade.E.value: 0.3,
}


def evidence_grade_multiplier(grade: str) -> float:
    """Return confidence multiplier for an evidence grade."""
    return _GRADE_MULTIPLIERS.get(grade, 0.3)


def calc_mplads_score(
    utilization_rate: float | None,
    works: list | None = None,
) -> float:
    """MPLADS Fund Utilization scoring (v2.0).

    Base score from utilization rate, with bonus from eSAKSHI work-level data:
    - % works completed boosts score (up to +5)
    - Data freshness: recent eSAKSHI data gets +3 confidence boost
    """
    if utilization_rate is None:
        return 50.0  # Neutral when no data
    rate = utilization_rate
    if rate >= 90:
        base = min(100, 90 + (rate - 90))
    elif rate >= 70:
        base = 70 + (rate - 70)
    elif rate >= 50:
        base = 40 + (rate - 50) * 1.5
    else:
        base = rate * 0.8

    # Work-level bonus when eSAKSHI data is available
    if works and len(works) > 0:
        completed = sum(1 for w in works if w.status == "completed")
        completion_pct = completed / len(works) if len(works) > 0 else 0
        # Up to +5 for high completion rate
        base += completion_pct * 5

    return min(100.0, base)


def calc_asset_score(growth_ratio: float | None) -> float:
    """Asset Growth scoring — lower growth = better score."""
    if growth_ratio is None:
        return 50.0  # Neutral when no previous data
    pct = growth_ratio * 100
    if pct <= 0:
        return 85
    if pct <= 20:
        return 80
    if pct <= 50:
        return 65
    if pct <= 100:
        return 45
    if pct <= 200:
        return 25
    return 10


def calc_criminal_score(
    total_cases: int,
    serious_cases: int,
    convictions: int,
    pending_cases: int = 0,
    disposed_cases: int = 0,
) -> float:
    """Criminal Cases scoring — distinguishes pending vs convicted vs disposed.

    Convictions: -30 each (heaviest)
    Serious pending: -20 each
    Non-serious pending: -10 each
    Disposed/acquitted: -3 each (minimal — not proven guilt)
    """
    score = 100.0

    # Convictions are the heaviest penalty
    score -= convictions * 30

    # Pending cases: distinguish serious vs non-serious
    if pending_cases > 0:
        # If we have per-case data, use it; otherwise estimate from totals
        serious_pending = min(serious_cases, pending_cases)
        non_serious_pending = pending_cases - serious_pending
        score -= serious_pending * 20
        score -= non_serious_pending * 10
    elif total_cases > 0 and pending_cases == 0 and disposed_cases == 0:
        # Legacy path: no pending/disposed breakdown available, use old formula
        non_serious = total_cases - serious_cases
        score -= non_serious * 15
        score -= serious_cases * 25

    # Disposed cases: minimal penalty
    score -= disposed_cases * 3

    return max(0.0, score)


def calc_attendance_score(attendance_pct: float | None, is_minister: bool = False) -> float:
    """Parliament Attendance scoring — direct 1:1 mapping."""
    if is_minister:
        return 50.0
    if attendance_pct is None:
        return 50.0
    return min(100.0, max(0.0, attendance_pct))


def calc_participation_score(
    questions: int, debates: int, is_minister: bool = False
) -> float:
    """Questions & Debates participation scoring."""
    if is_minister:
        return 50.0

    # Questions component (50% weight)
    if questions >= 50:
        q_score = 100
    elif questions >= 30:
        q_score = 80
    elif questions >= 15:
        q_score = 60
    elif questions >= 5:
        q_score = 40
    elif questions > 0:
        q_score = 20
    else:
        q_score = 0

    # Debates component (50% weight)
    if debates >= 30:
        d_score = 100
    elif debates >= 15:
        d_score = 80
    elif debates >= 5:
        d_score = 60
    elif debates >= 1:
        d_score = 40
    else:
        d_score = 0

    return q_score * 0.5 + d_score * 0.5


def calc_committee_score(
    total_committees: int,
    leadership_roles: int = 0,
) -> float:
    """Committee Engagement scoring.

    0 committees → 0
    1 committee → 30
    2 committees → 50
    3+ committees → 70
    Leadership role bonus: +15 per chair, +10 per vice-chair
    Cap at 100
    """
    if total_committees == 0:
        return 0.0

    if total_committees == 1:
        base = 30.0
    elif total_committees == 2:
        base = 50.0
    else:
        base = 70.0

    # Leadership bonus (simplified: +15 per leadership role)
    base += leadership_roles * 15

    return min(100.0, base)


def calc_accessibility_score(
    total_platforms: int,
    verified_count: int = 0,
    active: bool = False,
) -> float:
    """Public Accessibility scoring via social media presence.

    0 platforms → 10
    1 platform → 30
    2 platforms → 50
    3+ platforms → 70
    Verified bonus: +10 per verified account
    Active bonus: +10 if posted in last 30 days
    Cap at 100
    """
    if total_platforms == 0:
        return 10.0

    if total_platforms == 1:
        base = 30.0
    elif total_platforms == 2:
        base = 50.0
    else:
        base = 70.0

    base += verified_count * 10
    if active:
        base += 10

    return min(100.0, base)


def calc_legislative_score(
    private_member_bills: int = 0,
    zero_hour_mentions: int = 0,
    special_mentions: int = 0,
) -> float:
    """Legislative Effectiveness scoring.

    Private bills: 0→0, 1→30, 2→50, 3+→70
    Zero hour mentions: 0→0, 1-2→15, 3-5→25, 5+→35
    Special mentions: 0→0, 1-2→10, 3+→20
    Combined with cap at 100
    """
    # Private bills component
    if private_member_bills >= 3:
        bill_score = 70.0
    elif private_member_bills == 2:
        bill_score = 50.0
    elif private_member_bills == 1:
        bill_score = 30.0
    else:
        bill_score = 0.0

    # Zero hour component
    if zero_hour_mentions > 5:
        zh_score = 35.0
    elif zero_hour_mentions >= 3:
        zh_score = 25.0
    elif zero_hour_mentions >= 1:
        zh_score = 15.0
    else:
        zh_score = 0.0

    # Special mentions component
    if special_mentions >= 3:
        sm_score = 20.0
    elif special_mentions >= 1:
        sm_score = 10.0
    else:
        sm_score = 0.0

    return min(100.0, bill_score + zh_score + sm_score)


class AssessorAgent(BaseAgent):
    """Calculates composite transparency score for one MP."""

    agent_name = "assessor"

    async def assess(self, validated: ValidatedFindings) -> ScoreResult:
        """Score an MP based on validated findings."""
        mp = validated.mp
        f = validated.findings
        log.info("[bold magenta]Scoring:[/bold magenta] %s", mp.name)

        # Calculate component scores — use adjusted rate when cumulative data available
        effective_rate = adjusted_utilization_rate(f.mplads)
        mplads_s = calc_mplads_score(effective_rate, works=f.mplads.works or None)
        asset_s = calc_asset_score(f.assets.growth_ratio)
        criminal_s = calc_criminal_score(
            f.criminal_record.total_cases,
            f.criminal_record.serious_cases,
            f.criminal_record.convictions,
            f.criminal_record.pending_cases,
            f.criminal_record.disposed_cases,
        )
        attendance_s = calc_attendance_score(
            f.parliament_activity.attendance_percentage,
            f.parliament_activity.is_minister,
        )
        participation_s = calc_participation_score(
            f.parliament_activity.questions_asked,
            f.parliament_activity.debates_participated,
            f.parliament_activity.is_minister,
        )

        # New scoring dimensions
        committee_s = calc_committee_score(
            f.committees.total_committees,
            f.committees.leadership_roles,
        )
        accessibility_s = calc_accessibility_score(
            f.social_media.total_platforms,
            verified_count=sum(1 for p in f.social_media.profiles if p.verified),
            active=any(p.active for p in f.social_media.profiles),
        )
        legislative_s = calc_legislative_score(
            f.legislative.private_member_bills,
            f.legislative.zero_hour_mentions,
            f.legislative.special_mentions,
        )

        breakdown = ScoreBreakdown(
            mplads_score=round(mplads_s, 1),
            asset_score=round(asset_s, 1),
            criminal_score=round(criminal_s, 1),
            attendance_score=round(attendance_s, 1),
            participation_score=round(participation_s, 1),
            committee_score=round(committee_s, 1),
            accessibility_score=round(accessibility_s, 1),
            legislative_score=round(legislative_s, 1),
        )

        # Composite weighted score
        # Note: news_sentiment is intentionally excluded from scoring — it's collected
        # as informational context for reports, not as a scored dimension.
        w = settings.weights
        composite = (
            mplads_s * w.mplads
            + asset_s * w.asset
            + criminal_s * w.criminal
            + attendance_s * w.attendance
            + participation_s * w.participation
            + committee_s * w.committee
            + accessibility_s * w.accessibility
            + legislative_s * w.legislative
        )

        # Compute data_confidence as weighted average factoring evidence grades
        data_confidence = self._compute_evidence_weighted_confidence(validated)

        # Rule-based qualitative assessment (no LLM needed)
        assessment = self._auto_assessment(mp, breakdown, composite, validated)
        key_finding = self._auto_key_finding(breakdown)

        score = ScoreResult(
            mp=mp,
            composite_score=round(composite, 1),
            breakdown=breakdown,
            data_confidence=data_confidence,
            qualitative_assessment=assessment,
            key_finding=key_finding,
        )

        await self.db.save_score(mp.slug, mp.state, score)
        log.info(
            "[green]Score complete:[/green] %s — %.1f/100 (confidence: %.0f%%)",
            mp.name, composite, data_confidence * 100,
        )
        return score

    def _compute_evidence_weighted_confidence(self, validated: ValidatedFindings) -> float:
        """Compute confidence as weighted average factoring evidence grades."""
        f = validated.findings
        evidence = f.evidence_summary

        # Source confidences with their evidence grade multipliers
        components = [
            (f.criminal_record.confidence, evidence.get("criminal", "E")),
            (f.assets.confidence, evidence.get("assets", "E")),
            (f.mplads.confidence, evidence.get("mplads", "E")),
            (f.parliament_activity.confidence, evidence.get("parliament", "E")),
            (f.committees.confidence, evidence.get("committees", "E")),
            (f.social_media.confidence, evidence.get("accessibility", "E")),
            (f.legislative.confidence, evidence.get("legislative", "E")),
        ]

        total_weight = 0.0
        weighted_sum = 0.0
        for confidence, grade in components:
            mult = evidence_grade_multiplier(grade)
            weighted_sum += confidence * mult
            total_weight += mult

        if total_weight == 0:
            return validated.overall_confidence

        raw = weighted_sum / total_weight

        # Note: error-flag penalty is already applied by the validator in
        # overall_confidence. We don't apply it again here to avoid double-penalizing.

        return round(min(1.0, raw), 2)

    def _auto_key_finding(self, b: ScoreBreakdown) -> str:
        """Generate a key finding string from score breakdown."""
        parts = []
        if b.criminal_score >= 100:
            parts.append("Clean record")
        elif b.criminal_score < 50:
            parts.append("Significant criminal cases")
        if b.mplads_score >= 80:
            parts.append("Strong fund utilization")
        elif b.mplads_score < 40:
            parts.append("Low fund utilization")
        if b.attendance_score >= 80:
            parts.append("High attendance")
        elif b.attendance_score < 40:
            parts.append("Low attendance")
        if b.committee_score >= 70:
            parts.append("Active in committees")
        if b.legislative_score >= 50:
            parts.append("Legislative initiative")
        return ", ".join(parts) if parts else "Mixed transparency record"

    def _auto_assessment(
        self, mp, breakdown: ScoreBreakdown, composite: float, validated: ValidatedFindings
    ) -> str:
        """Generate a rule-based qualitative assessment without LLM."""
        parts = []

        # Overall
        if composite >= 70:
            parts.append(f"{mp.name} demonstrates strong transparency with an overall score of {composite:.1f}/100.")
        elif composite >= 50:
            parts.append(f"{mp.name} shows moderate transparency with a score of {composite:.1f}/100.")
        else:
            parts.append(f"{mp.name} has a below-average transparency score of {composite:.1f}/100, indicating significant room for improvement.")

        # Criminal
        if breakdown.criminal_score >= 100:
            parts.append("No criminal cases declared.")
        elif breakdown.criminal_score >= 70:
            parts.append("Minor criminal cases on record.")
        else:
            parts.append("Significant criminal cases are a concern.")

        # MPLADS
        if breakdown.mplads_score >= 80:
            parts.append("Strong MPLADS fund utilization.")
        elif breakdown.mplads_score < 40:
            parts.append("Low MPLADS fund utilization needs attention.")

        # Attendance
        if breakdown.attendance_score >= 80:
            parts.append("High parliament attendance.")
        elif breakdown.attendance_score < 40:
            parts.append("Low parliament attendance is notable.")

        # Participation
        if breakdown.participation_score >= 60:
            parts.append("Active in questions and debates.")
        elif breakdown.participation_score < 30:
            parts.append("Limited participation in parliamentary proceedings.")

        # Data confidence
        if validated.overall_confidence < 0.3:
            parts.append("Data confidence is low — scores should be interpreted with caution.")

        return " ".join(parts)
