"""CAG Audit Report integration for MPLADS contextual findings."""

from __future__ import annotations

from ..models.schemas import CAGFinding, DataSource, EvidenceGrade
from ..utils.logger import get_logger
from ..utils.name_match import normalize_state

log = get_logger(__name__)


# Known CAG MPLADS audit report findings (hardcoded initially).
# These are state-level findings from published CAG Performance Audit reports.
# Sources: CAG Report No. 31 of 2010, No. 9 of 2013, No. 42 of 2017, etc.
_KNOWN_FINDINGS: list[dict] = [
    {
        "report_title": "Performance Audit of MPLADS",
        "report_number": "31 of 2010",
        "year": 2010,
        "url": "https://cag.gov.in/en/audit-report/details/2341",
        "findings": [
            {"finding": "Idle funds: Rs 1,558 crore lying unspent in district authorities' accounts across states", "category": "idle_funds", "severity": "high", "states": ["all"]},
            {"finding": "Bogus utilization certificates: 34% of sampled UCs lacked proper supporting documents", "category": "bogus_ucs", "severity": "high", "states": ["all"]},
            {"finding": "Incomplete works: 18% of sampled works were abandoned or incomplete", "category": "incomplete_works", "severity": "medium", "states": ["all"]},
        ],
    },
    {
        "report_title": "Follow-up Audit of MPLADS",
        "report_number": "9 of 2013",
        "year": 2013,
        "url": "https://cag.gov.in/uploads/media/Follow-up-action-on-Audit-Report-20200902114923.pdf",
        "findings": [
            {"finding": "Persistent idle funds: District authorities retained Rs 2,100 crore in unspent balances", "category": "idle_funds", "severity": "high", "states": ["all"]},
            {"finding": "Works executed outside MP constituency in multiple states", "category": "irregular_works", "severity": "medium", "states": ["uttar pradesh", "bihar", "madhya pradesh"]},
        ],
    },
    {
        "report_title": "Performance Audit of MPLADS (2012-17)",
        "report_number": "CAG Performance Report 2017",
        "year": 2017,
        "url": "https://www.mplads.gov.in/MPLADS/UploadedFiles/cag%20performance%20report.pdf",
        "findings": [
            {"finding": "Only 53% of recommended works completed within the audit period", "category": "incomplete_works", "severity": "medium", "states": ["all"]},
            {"finding": "Rs 293 crore expended on inadmissible works not covered under MPLADS guidelines", "category": "irregular_works", "severity": "high", "states": ["all"]},
            {"finding": "Asset registers not maintained by district authorities in 40% of sampled districts", "category": "poor_records", "severity": "medium", "states": ["all"]},
            {"finding": "Delhi: 67% utilization rate, below national average of 72%", "category": "low_utilization", "severity": "medium", "states": ["delhi"]},
        ],
    },
]


class CAGFetcher:
    """Provides CAG audit findings for MPLADS contextual risk assessment.

    Currently uses hardcoded findings from known CAG reports.
    State-level context, not individual MP penalties.
    """

    def get_state_risk_indicators(self, state: str) -> list[CAGFinding]:
        """Return relevant CAG findings for a state.

        Includes both state-specific findings and national-level findings
        that apply to all states.
        """
        normalized = normalize_state(state)
        findings = []

        for report in _KNOWN_FINDINGS:
            for item in report["findings"]:
                states = item.get("states", [])
                if "all" in states or normalized in states:
                    findings.append(CAGFinding(
                        report_title=report["report_title"],
                        report_number=report["report_number"],
                        year=report["year"],
                        finding=item["finding"],
                        category=item["category"],
                        state=normalized if normalized in states else "national",
                        severity=item.get("severity", "medium"),
                        source=DataSource(
                            url=report["url"],
                            source_name="cag",
                            grade=EvidenceGrade.A,
                            notes=f"CAG Report No. {report['report_number']}",
                        ),
                    ))

        log.info("CAG: Found %d relevant findings for %s", len(findings), state)
        return findings
