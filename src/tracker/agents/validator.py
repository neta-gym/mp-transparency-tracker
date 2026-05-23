"""Validator agent — cross-checks data and assigns confidence scores."""

from __future__ import annotations

from typing import Optional

from ..models.schemas import (
    ResearchFindings,
    ValidatedFindings,
    ValidationFlag,
    EvidenceGrade,
)
from ..storage.database import Database
from ..tools.cag import CAGFetcher
from ..tools.budget import BudgetFetcher
from ..tools.sansad_qa import SansadQAParser
from ..utils.logger import get_logger
from .base import BaseAgent

log = get_logger(__name__)


class ValidatorAgent(BaseAgent):
    """Cross-checks research findings and assigns overall confidence."""

    agent_name = "validator"

    def __init__(
        self,
        db: Database,
        cag: Optional[CAGFetcher] = None,
        budget: Optional[BudgetFetcher] = None,
        sansad_qa: Optional[SansadQAParser] = None,
    ) -> None:
        super().__init__(db)
        self.cag = cag or CAGFetcher()
        self.budget = budget
        self.sansad_qa = sansad_qa

    async def validate(self, findings: ResearchFindings) -> ValidatedFindings:
        """Validate research findings for one MP."""
        mp = findings.mp
        log.info("[bold yellow]Validating:[/bold yellow] %s", mp.name)

        flags: list[ValidationFlag] = []

        # Rule-based validation checks
        self._check_criminal(findings, flags)
        self._check_assets(findings, flags)
        self._check_mplads(findings, flags)
        self._check_parliament(findings, flags)
        self._check_committees(findings, flags)
        self._check_legislative(findings, flags)
        self._check_sources(findings, flags)
        self._check_evidence_quality(findings, flags)

        # Add CAG audit context (state-level, not individual MP penalty)
        cag_findings = self.cag.get_state_risk_indicators(mp.state)
        if cag_findings:
            findings.cag_findings = cag_findings
            cag_notes = "; ".join(
                f"[CAG {f.report_number}] {f.finding}" for f in cag_findings[:3]
            )
            flags.append(ValidationFlag(
                field="mplads",
                issue=f"CAG audit context for {mp.state.title()}: {len(cag_findings)} relevant findings",
                severity="info",
                suggestion=cag_notes,
            ))

        # Sansad Q&A cross-check (if available)
        if self.sansad_qa and findings.mplads.confidence > 0:
            await self._cross_check_sansad_qa(findings, flags)

        # Rule-based cross-reference summary (no LLM needed)
        cross_notes = self._rule_based_cross_check(findings, flags)

        # Calculate overall confidence across all dimensions
        source_confidences = [
            findings.criminal_record.confidence,
            findings.assets.confidence,
            findings.mplads.confidence,
            findings.parliament_activity.confidence,
            findings.committees.confidence,
            findings.social_media.confidence,
            findings.legislative.confidence,
        ]
        overall = sum(source_confidences) / len(source_confidences)

        # Penalize for error-level flags
        error_count = sum(1 for f in flags if f.severity == "error")
        overall = max(0.0, overall - error_count * 0.1)

        validated = ValidatedFindings(
            mp=mp,
            findings=findings,
            overall_confidence=round(overall, 2),
            flags=flags,
            cross_reference_notes=cross_notes,
        )

        await self.db.save_validated_findings(mp.slug, mp.state, validated)
        log.info(
            "[green]Validation complete:[/green] %s — confidence: %.2f, flags: %d",
            mp.name, overall, len(flags),
        )
        return validated

    def _check_criminal(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        cr = f.criminal_record
        if cr.serious_cases > cr.total_cases:
            flags.append(ValidationFlag(
                field="criminal_record",
                issue="Serious cases exceed total cases",
                severity="error",
            ))
        if cr.convictions > cr.total_cases:
            flags.append(ValidationFlag(
                field="criminal_record",
                issue="Convictions exceed total cases",
                severity="error",
            ))
        # Pending + disposed + convicted should not exceed total
        accounted = cr.pending_cases + cr.disposed_cases + cr.convictions
        if accounted > 0 and accounted > cr.total_cases:
            flags.append(ValidationFlag(
                field="criminal_record",
                issue=f"Pending ({cr.pending_cases}) + disposed ({cr.disposed_cases}) + convicted ({cr.convictions}) = {accounted} exceeds total ({cr.total_cases})",
                severity="warning",
            ))
        if cr.confidence < 0.5:
            flags.append(ValidationFlag(
                field="criminal_record",
                issue="Low confidence in criminal data — source may be unavailable",
                severity="warning",
            ))

    def _check_assets(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        a = f.assets
        if a.total_assets is not None and a.total_assets < 0:
            flags.append(ValidationFlag(
                field="assets",
                issue="Negative total assets — likely a parsing error",
                severity="error",
            ))
        if a.liabilities is not None and a.total_assets is not None:
            if a.liabilities > a.total_assets * 5:
                flags.append(ValidationFlag(
                    field="assets",
                    issue="Liabilities exceed 5x total assets — unusual, verify",
                    severity="warning",
                ))
        if a.growth_ratio is not None and a.growth_ratio > 10:
            flags.append(ValidationFlag(
                field="assets",
                issue=f"Asset growth ratio of {a.growth_ratio:.0%} is extremely high",
                severity="warning",
            ))
        if a.confidence < 0.5:
            flags.append(ValidationFlag(
                field="assets",
                issue="Low confidence in asset data",
                severity="warning",
            ))

    def _check_mplads(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        m = f.mplads
        if m.utilization_rate is not None:
            if m.utilization_rate > 100:
                if m.includes_covid_suspension or m.cumulative_released:
                    # Expected when using cumulative/multi-year data
                    flags.append(ValidationFlag(
                        field="mplads",
                        issue="Utilization rate > 100% — includes carryover/prior-year balances",
                        severity="info",
                        suggestion="Non-lapsable nature of MPLADS funds means expenditure can exceed single-year release",
                    ))
                else:
                    flags.append(ValidationFlag(
                        field="mplads",
                        issue="Utilization rate > 100% — may include carryover funds",
                        severity="info",
                    ))
            if m.utilization_rate < 10:
                flags.append(ValidationFlag(
                    field="mplads",
                    issue="Extremely low utilization rate — verify data",
                    severity="warning",
                ))
        if m.includes_covid_suspension:
            flags.append(ValidationFlag(
                field="mplads",
                issue="Data period includes COVID-19 MPLADS suspension (Apr 2020 – Nov 2021)",
                severity="info",
                suggestion="MPLADS was suspended for 20 months; utilization rates should be interpreted in this context",
            ))
        if m.confidence < 0.5:
            flags.append(ValidationFlag(
                field="mplads",
                issue="Low confidence in MPLADS data",
                severity="warning",
            ))

    def _check_parliament(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        p = f.parliament_activity
        if p.attendance_percentage is not None:
            if p.attendance_percentage > 100:
                flags.append(ValidationFlag(
                    field="parliament_activity",
                    issue="Attendance > 100% — data error",
                    severity="error",
                ))
        if p.confidence < 0.5:
            flags.append(ValidationFlag(
                field="parliament_activity",
                issue="Low confidence in parliament activity data",
                severity="warning",
            ))

    def _check_committees(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        c = f.committees
        if c.leadership_roles > c.total_committees:
            flags.append(ValidationFlag(
                field="committees",
                issue="Leadership roles exceed total committees",
                severity="error",
            ))
        if c.confidence < 0.3 and c.total_committees == 0:
            flags.append(ValidationFlag(
                field="committees",
                issue="No committee data found — Sansad profile may be unavailable",
                severity="info",
            ))

    def _check_legislative(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        leg = f.legislative
        if leg.confidence < 0.3:
            flags.append(ValidationFlag(
                field="legislative",
                issue="Low confidence in legislative effectiveness data",
                severity="info",
            ))

    def _check_sources(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        if len(f.sources_consulted) < 2:
            flags.append(ValidationFlag(
                field="sources",
                issue=f"Only {len(f.sources_consulted)} source(s) consulted — limited cross-referencing",
                severity="warning",
            ))

    def _check_evidence_quality(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        """Flag if evidence quality is low across all dimensions."""
        ev = f.evidence_summary
        if not ev:
            return

        grades = list(ev.values())
        low_grades = {"D", "E"}

        if all(g in low_grades for g in grades):
            flags.append(ValidationFlag(
                field="evidence_quality",
                issue="All data sources are Grade D or E — low reliability across all dimensions",
                severity="warning",
                suggestion="Seek authoritative government sources for verification",
            ))

        majority_low = sum(1 for g in grades if g in low_grades)
        if len(grades) > 0 and majority_low > len(grades) / 2 and not all(g in low_grades for g in grades):
            flags.append(ValidationFlag(
                field="evidence_quality",
                issue=f"Majority of data sources ({majority_low}/{len(grades)}) are Grade D or E",
                severity="info",
            ))

    async def _cross_check_sansad_qa(self, f: ResearchFindings, flags: list[ValidationFlag]) -> None:
        """Cross-check MPLADS data against Sansad Q&A annexure data."""
        try:
            questions = await self.sansad_qa.search_mplads_questions()
            for q in questions[:3]:  # Check up to 3 recent questions
                annexure_url = q.get("annexure_url", "")
                if not annexure_url:
                    continue

                text = await self.sansad_qa.fetch_annexure(annexure_url)
                if not text:
                    continue

                qa_data = self.sansad_qa.parse_mplads_table(text, f.mp.state)
                if not qa_data:
                    continue

                # Compare figures — flag discrepancies > 15%
                if qa_data.get("released") and f.mplads.released:
                    diff = abs(qa_data["released"] - f.mplads.released) / f.mplads.released
                    if diff > 0.15:
                        flags.append(ValidationFlag(
                            field="mplads",
                            issue=f"Sansad Q&A annexure shows released amount differs by {diff:.0%} from primary source",
                            severity="warning",
                            suggestion=f"Q&A: Rs {qa_data['released']:,.0f} vs Primary: Rs {f.mplads.released:,.0f}",
                        ))
                    else:
                        flags.append(ValidationFlag(
                            field="mplads",
                            issue=f"Sansad Q&A cross-check: figures match within {diff:.0%} (consistent)",
                            severity="info",
                        ))
                    break  # Found a match, stop searching

        except Exception as e:
            log.warning("Sansad Q&A cross-check failed for %s: %s", f.mp.name, e)

    def _rule_based_cross_check(self, f: ResearchFindings, flags: list[ValidationFlag]) -> str:
        """Produce a rule-based cross-reference summary without LLM."""
        lines = []
        mp = f.mp

        # Criminal record summary
        cr = f.criminal_record
        if cr.total_cases > 0:
            lines.append(
                f"Has {cr.total_cases} criminal case(s) ({cr.serious_cases} serious), "
                f"{cr.pending_cases} pending, {cr.convictions} conviction(s)."
            )
        else:
            lines.append("No criminal cases declared.")

        # Asset summary
        a = f.assets
        if a.total_assets is not None:
            lines.append(f"Declared assets: Rs {a.total_assets:,.0f}.")
            if a.growth_ratio is not None and a.growth_ratio > 1.0:
                lines.append(f"Asset growth ratio: {a.growth_ratio:.1f}x (notable increase).")

        # MPLADS summary
        m = f.mplads
        if m.utilization_rate is not None:
            lines.append(f"MPLADS utilization: {m.utilization_rate:.1f}%.")

        # Parliament activity summary
        p = f.parliament_activity
        if p.attendance_percentage is not None:
            lines.append(f"Parliament attendance: {p.attendance_percentage:.1f}%.")
        if p.questions_asked > 0:
            lines.append(f"Questions asked: {p.questions_asked}.")
        if p.debates_participated > 0:
            lines.append(f"Debates participated: {p.debates_participated}.")

        # Committee engagement
        if f.committees and f.committees.total_committees > 0:
            lines.append(f"Serves on {f.committees.total_committees} committee(s) ({f.committees.leadership_roles} leadership).")

        # Data quality notes
        low_conf = []
        for name, conf in [
            ("Criminal record", cr.confidence),
            ("Assets", a.confidence),
            ("MPLADS", m.confidence),
            ("Parliament activity", p.confidence),
        ]:
            if conf < 0.5:
                low_conf.append(name)
        if low_conf:
            lines.append(f"Low confidence data: {', '.join(low_conf)}.")

        # Flags summary
        if flags:
            error_flags = [fl for fl in flags if fl.severity == "error"]
            warning_flags = [fl for fl in flags if fl.severity == "warning"]
            if error_flags:
                lines.append(f"{len(error_flags)} data error(s) flagged.")
            if warning_flags:
                lines.append(f"{len(warning_flags)} warning(s) noted.")

        return " ".join(lines)
