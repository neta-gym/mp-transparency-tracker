"""Developer agent — compiles Markdown reports per MP."""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime

from ..models.schemas import ValidatedFindings, ScoreResult, House
from ..storage.database import Database
from ..utils.logger import get_logger
from ..utils.rti_generator import generate_rti_template
from .base import BaseAgent

log = get_logger(__name__)


def _fmt_currency(val: float | None) -> str:
    """Format a number as Indian currency string."""
    if val is None:
        return "N/A"
    if val >= 1_00_00_000:
        return f"Rs {val / 1_00_00_000:.2f} Crore"
    if val >= 1_00_000:
        return f"Rs {val / 1_00_000:.2f} Lakh"
    return f"Rs {val:,.0f}"


def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


def _confidence_badge(c: float) -> str:
    if c >= 0.8:
        return "High"
    if c >= 0.5:
        return "Medium"
    return "Low"


def _grade_badge(grade: str) -> str:
    """Human-readable evidence grade label."""
    labels = {
        "A": "Authoritative (A)",
        "B": "Official (B)",
        "C": "Third-party (C)",
        "D": "Secondary (D)",
        "E": "LLM/Estimated (E)",
    }
    return labels.get(grade, f"Grade {grade}")


class DeveloperAgent(BaseAgent):
    """Compiles validated findings + scores into a Markdown report."""

    agent_name = "developer"

    async def compile_report(
        self,
        validated: ValidatedFindings,
        score: ScoreResult,
        data_dir: str = "data",
    ) -> str:
        """Generate and save a Markdown report for one MP."""
        mp = validated.mp
        f = validated.findings
        b = score.breakdown
        log.info("[bold blue]Compiling report:[/bold blue] %s", mp.name)

        house_label = "Lok Sabha" if mp.house == House.LOK_SABHA else "Rajya Sabha"

        # Compute average evidence grade for header
        ev = f.evidence_summary
        avg_grade = self._avg_evidence_grade(ev)

        lines = [
            f"# {mp.name} — Transparency Report",
            "",
            f"**Constituency:** {mp.constituency}, {mp.state.title()}",
            f"**Party:** {mp.party}",
            f"**House:** {house_label} (18th Parliament, 2024-present)",
        ]

        # Phase 1: Profile enrichment
        profile_parts = []
        if mp.age:
            profile_parts.append(f"**Age:** {mp.age}")
        if mp.education:
            profile_parts.append(f"**Education:** {mp.education}")
        if mp.profession:
            profile_parts.append(f"**Profession:** {mp.profession}")
        if profile_parts:
            lines.extend(profile_parts)

        lines.extend([
            f"**Report Date:** {datetime.utcnow().strftime('%Y-%m-%d')}",
            f"**Data Confidence:** {_confidence_badge(validated.overall_confidence)} ({validated.overall_confidence:.0%}) | **Evidence Grade:** {_grade_badge(avg_grade)}",
            "",
            "---",
            "",
            f"## Composite Transparency Score: {score.composite_score:.1f} / 100",
            "",
            "| Component | Score | Weight |",
            "|-----------|-------|--------|",
            f"| MPLADS Fund Utilization | {b.mplads_score:.1f} | 25% |",
            f"| Asset Growth | {b.asset_score:.1f} | 15% |",
            f"| Criminal Record | {b.criminal_score:.1f} | 15% |",
            f"| Parliament Attendance | {b.attendance_score:.1f} | 10% |",
            f"| Questions & Debates | {b.participation_score:.1f} | 10% |",
            f"| Committee Engagement | {b.committee_score:.1f} | 10% |",
            f"| Public Accessibility | {b.accessibility_score:.1f} | 5% |",
            f"| Legislative Effectiveness | {b.legislative_score:.1f} | 10% |",
            "",
            "---",
            "",
            "## Criminal Record",
            "",
            f"- **Total Cases:** {f.criminal_record.total_cases}",
            f"- **Serious Cases:** {f.criminal_record.serious_cases}",
            f"- **Convictions:** {f.criminal_record.convictions}",
            f"- **Pending Cases:** {f.criminal_record.pending_cases}",
            f"- **Disposed Cases:** {f.criminal_record.disposed_cases}",
            f"- **Data Source:** {f.criminal_record.source}",
            "",
        ])

        if f.criminal_record.cases:
            lines.append("### Cases Detail")
            lines.append("")
            for i, case in enumerate(f.criminal_record.cases, 1):
                status_tag = f" [{case.status}]" if case.status != "unknown" else ""
                lines.append(
                    f"{i}. {case.description or 'No description'} "
                    f"(Sections: {', '.join(case.ipc_sections) or 'N/A'}){status_tag} "
                    f"{'**SERIOUS**' if case.is_serious else ''}"
                )
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Asset Declaration",
            "",
            f"- **Movable Assets:** {_fmt_currency(f.assets.movable_assets)}",
            f"- **Immovable Assets:** {_fmt_currency(f.assets.immovable_assets)}",
            f"- **Total Assets:** {_fmt_currency(f.assets.total_assets)}",
            f"- **Liabilities:** {_fmt_currency(f.assets.liabilities)}",
            f"- **Net Worth:** {_fmt_currency(f.assets.net_worth)}",
            f"- **Previous Total Assets:** {_fmt_currency(f.assets.previous_total_assets)}",
            f"- **Asset Growth:** {_pct(f.assets.growth_ratio * 100 if f.assets.growth_ratio is not None else None)}",
        ])

        # Phase 1: Annual income and election expenditure
        if f.assets.annual_income is not None:
            lines.append(f"- **Annual Income:** {_fmt_currency(f.assets.annual_income)}")
        if f.assets.election_expenditure is not None:
            lines.append(f"- **Election Expenditure:** {_fmt_currency(f.assets.election_expenditure)}")

        # Phase 5: Wealth percentile
        if f.assets.wealth_percentile is not None:
            lines.append(f"- **Wealth Percentile:** Wealthier than {f.assets.wealth_percentile:.0f}% of Lok Sabha MPs")

        lines.append("")

        lines.extend([
            "---",
            "",
            "## MPLADS Fund Utilization",
            "",
            f"- **Entitled:** {_fmt_currency(f.mplads.entitled)}",
            f"- **Released:** {_fmt_currency(f.mplads.released)}",
            f"- **Sanctioned:** {_fmt_currency(f.mplads.sanctioned)}",
            f"- **Expended:** {_fmt_currency(f.mplads.expended)}",
            f"- **Utilization Rate:** {_pct(f.mplads.utilization_rate)}",
            "",
        ])

        # Phase 4: MPLADS Sector Breakdown
        if f.mplads.works:
            lines.extend(self._build_mplads_sector_breakdown(f.mplads.works))

        lines.extend([
            "---",
            "",
            "## Parliament Activity",
            "",
            f"- **Attendance:** {_pct(f.parliament_activity.attendance_percentage)}",
            f"- **Questions Asked:** {f.parliament_activity.questions_asked}",
            f"- **Debates Participated:** {f.parliament_activity.debates_participated}",
            f"- **Private Bills:** {f.parliament_activity.private_bills_introduced}",
            f"- **Is Minister:** {'Yes' if f.parliament_activity.is_minister else 'No'}",
            "",
        ])

        # Phase 3: Focus Areas
        if f.parliament_activity.focus_topics:
            lines.extend([
                "### Focus Areas",
                "",
            ])
            for topic in f.parliament_activity.focus_topics:
                lines.append(f"- {topic}")
            lines.append("")

        if f.parliament_activity.notable_questions:
            lines.extend([
                "### Notable Questions",
                "",
            ])
            for q in f.parliament_activity.notable_questions:
                lines.append(f"- {q}")
            lines.append("")

        # Phase 2: Committee Memberships
        if f.committees.total_committees > 0:
            lines.extend([
                "---",
                "",
                "## Committee Memberships",
                "",
                f"- **Total Committees:** {f.committees.total_committees}",
                f"- **Leadership Roles:** {f.committees.leadership_roles}",
                "",
                "| Committee | Role | Type |",
                "|-----------|------|------|",
            ])
            for m in f.committees.memberships:
                lines.append(f"| {m.committee_name} | {m.role.title()} | {m.committee_type or 'N/A'} |")
            lines.append("")

        # Phase 9: Legislative Effectiveness
        leg = f.legislative
        if leg.private_member_bills > 0 or leg.zero_hour_mentions > 0 or leg.special_mentions > 0:
            lines.extend([
                "---",
                "",
                "## Legislative Effectiveness",
                "",
                f"- **Private Member Bills:** {leg.private_member_bills}",
                f"- **Zero Hour Mentions:** {leg.zero_hour_mentions}",
                f"- **Special Mentions:** {leg.special_mentions}",
                "",
            ])

        # Phase 8: Key Votes
        if f.parliament_activity.voting_record:
            lines.extend([
                "---",
                "",
                "## Key Votes",
                "",
                "| Bill | Date | Vote | Passed |",
                "|------|------|------|--------|",
            ])
            for v in f.parliament_activity.voting_record[:10]:
                passed = "Yes" if v.bill_passed else "No"
                lines.append(f"| {v.bill_name} | {v.date} | {v.vote.title()} | {passed} |")
            lines.append("")

        # Phase 6: Public Accessibility
        if f.social_media.total_platforms > 0:
            lines.extend([
                "---",
                "",
                "## Public Accessibility",
                "",
                f"- **Platforms:** {f.social_media.total_platforms}",
                f"- **Total Followers:** {f.social_media.total_followers:,}" if f.social_media.total_followers > 0 else "",
                "",
                "| Platform | Handle | Verified | Active |",
                "|----------|--------|----------|--------|",
            ])
            for p in f.social_media.profiles:
                verified = "Yes" if p.verified else "No"
                active = "Yes" if p.active else "No"
                handle_display = f"[@{p.handle}]({p.url})" if p.url else f"@{p.handle}"
                lines.append(f"| {p.platform.title()} | {handle_display} | {verified} | {active} |")
            lines.append("")

        # Phase 7: News Sentiment
        if f.news_sentiment.total_articles > 0:
            ns = f.news_sentiment
            lines.extend([
                "---",
                "",
                "## In The News",
                "",
                f"*{ns.sentiment_summary}*",
                "",
                f"- **Total Articles:** {ns.total_articles}",
                f"- **Positive:** {ns.positive} | **Negative:** {ns.negative} | **Neutral:** {ns.neutral}",
                "",
            ])
            if ns.top_headlines:
                for item in ns.top_headlines[:5]:
                    sentiment_tag = f" [{item.sentiment}]" if item.sentiment else ""
                    lines.append(f"- {item.headline} ({item.source}){sentiment_tag}")
                lines.append("")

        # Phase 10: Constituency Profile
        ctx = f.constituency_context
        if ctx.district or ctx.population:
            lines.extend([
                "---",
                "",
                "## Constituency Profile",
                "",
            ])
            if ctx.district:
                lines.append(f"- **District:** {ctx.district}")
            if ctx.population:
                lines.append(f"- **Population:** {ctx.population:,}")
            if ctx.literacy_rate is not None:
                lines.append(f"- **Literacy Rate:** {ctx.literacy_rate:.1f}%")
            if ctx.urban_percentage is not None:
                lines.append(f"- **Urban:** {ctx.urban_percentage:.0f}%")
            lines.append("")

        if f.news_allegations:
            lines.extend([
                "---",
                "",
                "## News & Allegations",
                "",
            ])
            for item in f.news_allegations:
                sev = {"high": "!!!", "medium": "!!", "low": "!"}.get(item.severity, "")
                lines.append(f"- {sev} **{item.headline}** ({item.source})")
            lines.append("")

        if validated.flags:
            lines.extend([
                "---",
                "",
                "## Data Validation Flags",
                "",
            ])
            for flag in validated.flags:
                icon = {"error": "X", "warning": "!", "info": "i"}.get(flag.severity, "-")
                lines.append(f"- [{icon}] **{flag.field}**: {flag.issue}")
            lines.append("")

        if score.qualitative_assessment:
            lines.extend([
                "---",
                "",
                "## Qualitative Assessment",
                "",
                score.qualitative_assessment,
                "",
            ])

        if validated.cross_reference_notes:
            lines.extend([
                "---",
                "",
                validated.cross_reference_notes,
                "",
            ])

        # Compensation section (informational)
        if f.compensation:
            comp = f.compensation
            lines.extend([
                "---",
                "",
                "## Compensation (Informational)",
                "",
                f"- **Salary:** {_fmt_currency(comp.salary_per_month)}/month",
                f"- **Constituency Allowance:** {_fmt_currency(comp.constituency_allowance_per_month)}/month",
                f"- **Office Expense Allowance:** {_fmt_currency(comp.office_expense_allowance_per_month)}/month",
                f"- **Sumptuary Allowance:** {_fmt_currency(comp.sumptuary_allowance_per_month)}/month",
                f"- **Total Monthly:** {_fmt_currency(comp.total_monthly)}",
                f"- **Total Annual:** {_fmt_currency(comp.total_annual)}",
                f"- *Effective from: {comp.effective_from}*",
                f"- *Source: {comp.source_notification}*",
                "",
                f"> {comp.notes}" if comp.notes else "",
                "",
            ])

        # CAG Audit Context
        if f.cag_findings:
            lines.extend([
                "---",
                "",
                "## CAG Audit Context",
                "",
                f"*{len(f.cag_findings)} relevant CAG findings for {mp.state.title()}:*",
                "",
            ])
            for cag in f.cag_findings[:5]:
                lines.append(
                    f"- **[{cag.report_number}]** ({cag.year}) {cag.finding} "
                    f"[{cag.severity}] — [Source]({cag.source.url})"
                )
            lines.append("")

        # RTI Template section
        rti_text = generate_rti_template(mp, f.mplads)
        lines.extend([
            "---",
            "",
            "## RTI Template for MPLADS Verification",
            "",
            "<details>",
            "<summary>Click to expand pre-filled RTI application</summary>",
            "",
            "```",
            rti_text,
            "```",
            "",
            "</details>",
            "",
        ])

        # Data Provenance section
        lines.extend([
            "---",
            "",
            "## Data Provenance",
            "",
            "| Component | Source | Evidence Grade |",
            "|-----------|--------|---------------|",
        ])
        for dimension, grade in sorted(ev.items()):
            lines.append(f"| {dimension.title()} | {self._source_for_dim(dimension, f)} | {_grade_badge(grade)} |")
        lines.append("")

        lines.extend([
            "---",
            "",
            f"*Sources consulted: {', '.join(f.sources_consulted)}*",
            f"*Methodology version: 3.0 (8 scoring dimensions)*",
        ])

        report = "\n".join(lines)

        # Save to file
        state_slug = mp.state.replace(" ", "-").lower()
        report_dir = os.path.join(data_dir, state_slug, "reports")
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(report_dir, f"{mp.slug}.md")

        with open(path, "w") as fh:
            fh.write(report)

        log.info("[green]Report saved:[/green] %s", path)
        return report

    def _build_mplads_sector_breakdown(self, works: list) -> list[str]:
        """Build MPLADS sector breakdown table from works data."""
        sector_stats: dict[str, dict] = defaultdict(lambda: {
            "count": 0, "total_amount": 0.0, "completed": 0,
        })

        for w in works:
            sector = w.sector or "other"
            sector_stats[sector]["count"] += 1
            if w.expended_amount:
                sector_stats[sector]["total_amount"] += w.expended_amount
            if w.status == "completed":
                sector_stats[sector]["completed"] += 1

        if not sector_stats:
            return []

        lines = [
            "### Sector Breakdown",
            "",
            "| Sector | Works | Amount | Completion |",
            "|--------|-------|--------|------------|",
        ]

        for sector, stats in sorted(sector_stats.items(), key=lambda x: x[1]["total_amount"], reverse=True):
            completion_rate = (stats["completed"] / stats["count"] * 100) if stats["count"] > 0 else 0
            lines.append(
                f"| {sector.title()} | {stats['count']} | {_fmt_currency(stats['total_amount'])} | {completion_rate:.0f}% |"
            )

        lines.append("")
        return lines

    def _avg_evidence_grade(self, ev: dict[str, str]) -> str:
        """Compute average evidence grade from summary dict."""
        if not ev:
            return "E"
        grade_values = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        total = sum(grade_values.get(g, 1) for g in ev.values())
        avg = total / len(ev)
        if avg >= 4.5:
            return "A"
        if avg >= 3.5:
            return "B"
        if avg >= 2.5:
            return "C"
        if avg >= 1.5:
            return "D"
        return "E"

    def _source_for_dim(self, dimension: str, f) -> str:
        """Get human-readable source name for a dimension."""
        source_map = {
            "criminal": f.criminal_record.source,
            "assets": f.assets.source,
            "mplads": f.mplads.source,
            "parliament": f.parliament_activity.source,
            "committees": "sansad",
            "accessibility": "social_media",
            "legislative": "sansad",
        }
        return source_map.get(dimension, "unknown")
