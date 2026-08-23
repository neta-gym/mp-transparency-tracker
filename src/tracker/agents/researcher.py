"""Researcher agent — fetches data from all sources concurrently for one MP."""

from __future__ import annotations

import asyncio

from ..models.schemas import (
    AssetDeclaration,
    AttendancePattern,
    CommitteeEngagement,
    ConflictOfInterest,
    CriminalRecord,
    EvidenceGrade,
    House,
    LegislativeRecord,
    MPLADSFund,
    MPProfile,
    NewsSentiment,
    ParliamentActivity,
    PublicAccessibility,
    QuestionQuality,
    ResearchFindings,
)
from ..storage.database import Database
from ..tools.cag import CAGFetcher
from ..tools.constituency import ConstituencyFetcher
from ..tools.esakshi import ESAKSHIFetcher
from ..tools.mplads import MPLADSFetcher
from ..tools.mplads_datagov import DataGovMPLADSFetcher
from ..tools.myneta import MyNetaParser
from ..tools.news import NewsFetcher
from ..tools.prs import PRSFetcher
from ..tools.sagy import SAGYFetcher
from ..tools.sansad import SansadFetcher
from ..tools.social_media import SocialMediaFetcher
from ..utils.logger import get_logger
from ..utils.mp_compensation import get_mp_compensation
from ..utils.question_quality import assess_question_quality
from .base import BaseAgent

log = get_logger(__name__)


class ResearcherAgent(BaseAgent):
    """Fetches data from all sources concurrently for one MP."""

    agent_name = "researcher"

    def __init__(
        self,
        db: Database,
        myneta: MyNetaParser,
        prs: PRSFetcher,
        mplads: MPLADSFetcher,
        esakshi: ESAKSHIFetcher | None = None,
        mplads_datagov: DataGovMPLADSFetcher | None = None,
        sansad: SansadFetcher | None = None,
        social_media: SocialMediaFetcher | None = None,
        news: NewsFetcher | None = None,
        constituency: ConstituencyFetcher | None = None,
        sagy: SAGYFetcher | None = None,
        cag: CAGFetcher | None = None,
    ) -> None:
        super().__init__(db)
        self.myneta = myneta
        self.prs = prs
        self.mplads = mplads
        self.esakshi = esakshi
        self.mplads_datagov = mplads_datagov
        self.sansad = sansad
        self.social_media = social_media
        self.news = news
        self.constituency = constituency or ConstituencyFetcher()
        self.sagy = sagy
        self.cag = cag

    async def research(self, mp: MPProfile) -> ResearchFindings:
        """Research an MP from all available sources concurrently."""
        log.info("[bold cyan]Researching:[/bold cyan] %s (%s)", mp.name, mp.constituency)
        sources_consulted: list[str] = []
        evidence_summary: dict[str, str] = {}

        # Fetch from all sources concurrently
        tasks: dict[str, asyncio.Task] = {}

        if mp.myneta_candidate_id:
            tasks["myneta"] = asyncio.create_task(
                self.myneta.fetch_candidate(mp.myneta_candidate_id)
            )

        tasks["prs"] = asyncio.create_task(
            self.prs.fetch_activity(mp)
        )

        # MPLADS cascade: eSAKSHI (A) > data.gov.in (B) > dataful.in CSV (C)
        tasks["mplads"] = asyncio.create_task(
            self.mplads.fetch_fund_data(mp)
        )
        if self.esakshi:
            tasks["esakshi"] = asyncio.create_task(
                self.esakshi.fetch_fund_data(mp)
            )
            tasks["esakshi_works"] = asyncio.create_task(
                self.esakshi.fetch_works(mp)
            )
        if self.mplads_datagov:
            tasks["mplads_datagov"] = asyncio.create_task(
                self.mplads_datagov.fetch_fund_data(mp)
            )

        # New data sources (Phases 2, 6, 7, 9)
        if self.sansad:
            tasks["committees"] = asyncio.create_task(
                self.sansad.fetch_committees(mp)
            )
            tasks["legislative"] = asyncio.create_task(
                self.sansad.fetch_legislative_record(mp)
            )
            tasks["voting"] = asyncio.create_task(
                self.sansad.fetch_voting_record(mp)
            )
        if self.social_media:
            tasks["social_media"] = asyncio.create_task(
                self.social_media.fetch_social_media(mp)
            )
        if self.news:
            tasks["news_sentiment"] = asyncio.create_task(
                self.news.fetch_news(mp)
            )
        if self.sagy:
            tasks["sagy"] = asyncio.create_task(
                self.sagy.fetch_adoptions(mp)
            )

        # Gather results
        criminal = CriminalRecord()
        assets = AssetDeclaration()
        parliament = ParliamentActivity()
        mplads_fund = MPLADSFund()
        committees = CommitteeEngagement()
        social_media = PublicAccessibility()
        news_sentiment = NewsSentiment()
        legislative = LegislativeRecord()
        profile_extras: dict = {}
        news: list = []

        if "myneta" in tasks:
            try:
                result = await tasks["myneta"]
                criminal, assets, profile_extras = result
                sources_consulted.append("myneta")
                if criminal.sources:
                    evidence_summary["criminal"] = criminal.sources[0].grade.value
                else:
                    evidence_summary["criminal"] = EvidenceGrade.B.value
                if assets.sources:
                    evidence_summary["assets"] = assets.sources[0].grade.value
                else:
                    evidence_summary["assets"] = EvidenceGrade.B.value
            except Exception as e:
                log.warning("MyNeta fetch failed for %s: %s", mp.name, e)

        try:
            parliament = await tasks["prs"]
            if parliament.confidence > 0:
                sources_consulted.append("prs")
                if parliament.sources:
                    evidence_summary["parliament"] = parliament.sources[0].grade.value
                else:
                    evidence_summary["parliament"] = EvidenceGrade.C.value
        except Exception as e:
            log.warning("PRS fetch failed for %s: %s", mp.name, e)

        # MPLADS source cascade: prefer highest grade with confidence > 0.5
        mplads_fund = await self._resolve_mplads_cascade(tasks, mp)
        if mplads_fund.confidence > 0:
            sources_consulted.append("mplads")
            if mplads_fund.sources:
                evidence_summary["mplads"] = mplads_fund.sources[0].grade.value
            else:
                evidence_summary["mplads"] = EvidenceGrade.C.value

        # Collect new data sources
        if "committees" in tasks:
            try:
                committees = await tasks["committees"]
                if committees.confidence > 0:
                    sources_consulted.append("sansad_committees")
                    evidence_summary["committees"] = EvidenceGrade.A.value
                else:
                    evidence_summary["committees"] = EvidenceGrade.E.value
            except Exception as e:
                log.warning("Committee fetch failed for %s: %s", mp.name, e)
                evidence_summary["committees"] = EvidenceGrade.E.value

        if "legislative" in tasks:
            try:
                legislative = await tasks["legislative"]
                if legislative.confidence > 0:
                    sources_consulted.append("sansad_legislative")
                    evidence_summary["legislative"] = EvidenceGrade.A.value
                else:
                    evidence_summary["legislative"] = EvidenceGrade.E.value
            except Exception as e:
                log.warning("Legislative record fetch failed for %s: %s", mp.name, e)
                evidence_summary["legislative"] = EvidenceGrade.E.value

        if "voting" in tasks:
            try:
                voting_records = await tasks["voting"]
                if voting_records:
                    parliament.voting_record = voting_records
            except Exception as e:
                log.warning("Voting record fetch failed for %s: %s", mp.name, e)

        if "social_media" in tasks:
            try:
                social_media = await tasks["social_media"]
                if social_media.confidence > 0:
                    sources_consulted.append("social_media")
                    evidence_summary["accessibility"] = EvidenceGrade.D.value
                else:
                    evidence_summary["accessibility"] = EvidenceGrade.E.value
            except Exception as e:
                log.warning("Social media fetch failed for %s: %s", mp.name, e)
                evidence_summary["accessibility"] = EvidenceGrade.E.value

        if "news_sentiment" in tasks:
            try:
                news_sentiment = await tasks["news_sentiment"]
                if news_sentiment.confidence > 0:
                    sources_consulted.append("news")
                    # Populate news_allegations from news_sentiment top headlines
                    news = list(news_sentiment.top_headlines)
            except Exception as e:
                log.warning("News fetch failed for %s: %s", mp.name, e)

        # SAGY village adoption data (informational)
        sagy_adoptions: list = []
        if "sagy" in tasks:
            try:
                sagy_adoptions = await tasks["sagy"]
                if sagy_adoptions:
                    sources_consulted.append("sagy")
            except Exception as e:
                log.warning("SAGY fetch failed for %s: %s", mp.name, e)

        # CAG audit findings (state-level context)
        cag_findings: list = []
        if self.cag:
            try:
                cag_findings = self.cag.get_state_risk_indicators(mp.state)
                if cag_findings:
                    sources_consulted.append("cag")
            except Exception as e:
                log.warning("CAG fetch failed for %s: %s", mp.name, e)

        # Set default evidence grades for dimensions not yet set
        if "committees" not in evidence_summary:
            evidence_summary["committees"] = EvidenceGrade.E.value
        if "legislative" not in evidence_summary:
            evidence_summary["legislative"] = EvidenceGrade.E.value
        if "accessibility" not in evidence_summary:
            evidence_summary["accessibility"] = EvidenceGrade.E.value

        # Constituency context (sync, static data)
        constituency_context = self.constituency.fetch_context(mp)

        # Merge PRS private_bills into legislative record
        if parliament.private_bills_introduced > 0 and legislative.private_member_bills == 0:
            legislative.private_member_bills = parliament.private_bills_introduced

        # News and raw notes
        raw_notes = ""

        # Add MP compensation (informational, not scored)
        is_rs = mp.house == House.RAJYA_SABHA
        compensation = get_mp_compensation(is_rajya_sabha=is_rs)

        # Apply profile extras from MyNeta (Phase 1)
        if profile_extras.get("education"):
            mp.education = profile_extras["education"]
        if profile_extras.get("profession"):
            mp.profession = profile_extras["profession"]
        if profile_extras.get("age"):
            mp.age = profile_extras["age"]
        if profile_extras.get("photo_url"):
            mp.photo_url = profile_extras["photo_url"]

        findings = ResearchFindings(
            mp=mp,
            criminal_record=criminal,
            assets=assets,
            mplads=mplads_fund,
            parliament_activity=parliament,
            news_allegations=news,
            raw_notes=raw_notes,
            sources_consulted=sources_consulted,
            evidence_summary=evidence_summary,
            compensation=compensation,
            committees=committees,
            social_media=social_media,
            news_sentiment=news_sentiment,
            legislative=legislative,
            constituency_context=constituency_context,
            sagy=sagy_adoptions,
            cag_findings=cag_findings,
        )

        # Add question quality analysis
        question_quality = self._analyze_question_quality(mp, parliament)
        findings.question_quality = question_quality

        # Add attendance pattern analysis
        attendance_pattern = self._analyze_attendance_pattern(mp, parliament)
        findings.attendance_pattern = attendance_pattern

        # Add conflict of interest analysis
        conflict_of_interest = self._analyze_conflict_of_interest(mp, committees, parliament)
        findings.conflict_of_interest = conflict_of_interest

        # Persist
        await self.db.save_research_findings(mp.slug, mp.state, findings)
        log.info(
            "[green]Research complete:[/green] %s — %d sources consulted",
            mp.name, len(sources_consulted),
        )
        return findings

    async def _resolve_mplads_cascade(self, tasks: dict, mp: MPProfile) -> MPLADSFund:
        """Resolve MPLADS data using cascade: eSAKSHI (A) > data.gov.in (B) > dataful.in (C).

        Runs all fetchers concurrently and picks the highest-grade source with confidence > 0.5.
        Merges source lists from all responding fetchers for provenance tracking.
        """
        esakshi_fund = None
        datagov_fund = None
        csv_fund = None
        esakshi_works = []

        # Collect results from all MPLADS sources
        if "esakshi" in tasks:
            try:
                esakshi_fund = await tasks["esakshi"]
            except Exception as e:
                log.warning("eSAKSHI fetch failed for %s: %s", mp.name, e)

        if "esakshi_works" in tasks:
            try:
                esakshi_works = await tasks["esakshi_works"]
            except Exception as e:
                log.warning("eSAKSHI works fetch failed for %s: %s", mp.name, e)

        if "mplads_datagov" in tasks:
            try:
                datagov_fund = await tasks["mplads_datagov"]
            except Exception as e:
                log.warning("data.gov.in fetch failed for %s: %s", mp.name, e)

        try:
            csv_fund = await tasks["mplads"]
        except Exception as e:
            log.warning("MPLADS CSV fetch failed for %s: %s", mp.name, e)

        # Cascade: pick highest-grade source with confidence > 0.5
        primary = None

        if esakshi_fund and esakshi_fund.confidence > 0.5:
            primary = esakshi_fund
            log.info("MPLADS cascade: using eSAKSHI (Grade A) for %s", mp.name)
        elif datagov_fund and datagov_fund.confidence > 0.5:
            primary = datagov_fund
            log.info("MPLADS cascade: using data.gov.in (Grade B) for %s", mp.name)
        elif csv_fund and csv_fund.confidence > 0.5:
            primary = csv_fund
            log.info("MPLADS cascade: using dataful.in CSV (Grade C) for %s", mp.name)
        else:
            # Use whichever has any data at all
            primary = esakshi_fund or datagov_fund or csv_fund or MPLADSFund()

        # Merge sources from all fetchers for provenance
        all_sources = list(primary.sources)
        for alt in [esakshi_fund, datagov_fund, csv_fund]:
            if alt and alt is not primary:
                for src in alt.sources:
                    if src.source_name not in {s.source_name for s in all_sources}:
                        all_sources.append(src)
        primary.sources = all_sources

        # Attach eSAKSHI work-level data if available
        if esakshi_works:
            primary.works = esakshi_works
            primary.works_count = len(esakshi_works)

        return primary

    def _analyze_question_quality(self, mp: MPProfile, parliament: ParliamentActivity) -> QuestionQuality:
        """Analyze question quality based on available data."""
        if parliament.questions_asked == 0:
            return QuestionQuality(confidence=0.0)

        # Use PRS data to estimate starred vs unstarred
        # PRS CSV doesn't break down question types, so we estimate
        # Assume ~30% starred, ~70% unstarred for typical MPs
        starred = int(parliament.questions_asked * 0.3)
        unstarred = parliament.questions_asked - starred

        return assess_question_quality(
            questions_asked=parliament.questions_asked,
            starred=starred,
            unstarred=unstarred,
            topics=parliament.focus_topics,
            constituency_name=mp.constituency,
            notable_questions=parliament.notable_questions,
        )

    def _analyze_attendance_pattern(self, mp: MPProfile, parliament: ParliamentActivity) -> AttendancePattern:
        """Analyze attendance patterns based on available data."""
        if parliament.attendance_percentage is None:
            return AttendancePattern(confidence=0.0)

        # Determine pattern label based on attendance
        att = parliament.attendance_percentage
        if att >= 90:
            pattern_label = "Consistent"
        elif att >= 70:
            pattern_label = "Moderate"
        elif att >= 50:
            pattern_label = "Variable"
        else:
            pattern_label = "Low attendance"

        return AttendancePattern(
            overall_pct=att,
            session_breakdown={},
            consecutive_absences=0,
            attended_key_debates=att >= 70,
            zero_hour_presence=None,
            pattern_label=pattern_label,
            confidence=0.7 if att else 0.0,
        )

    def _analyze_conflict_of_interest(
        self, mp: MPProfile, committees: CommitteeEngagement, parliament: ParliamentActivity
    ) -> ConflictOfInterest:
        """Analyze potential conflict of interest based on available data."""
        # This is a simplified analysis - full implementation would cross-reference
        # MP business interests with committee sectors
        mp_businesses: list[str] = []
        committee_sectors: list[str] = []
        question_sectors: list[str] = []
        overlaps: list[str] = []

        # Extract committee sectors
        for membership in committees.memberships:
            name_lower = membership.committee_name.lower()
            if "finance" in name_lower or "banking" in name_lower:
                committee_sectors.append("finance")
            elif "health" in name_lower:
                committee_sectors.append("health")
            elif "education" in name_lower:
                committee_sectors.append("education")
            elif "defence" in name_lower or "defense" in name_lower:
                committee_sectors.append("defence")
            elif "agriculture" in name_lower or "rural" in name_lower:
                committee_sectors.append("agriculture")
            elif "industry" in name_lower or "commerce" in name_lower:
                committee_sectors.append("industry")
            elif "energy" in name_lower or "power" in name_lower:
                committee_sectors.append("energy")
            elif "transport" in name_lower or "railway" in name_lower:
                committee_sectors.append("transport")

        # For now, we can't determine overlaps without detailed business data
        severity = "none"
        if len(overlaps) > 2:
            severity = "high"
        elif len(overlaps) > 0:
            severity = "medium"

        return ConflictOfInterest(
            mp_businesses=mp_businesses,
            committee_sectors=committee_sectors,
            question_sectors=question_sectors,
            overlaps=overlaps,
            severity=severity,
            analysis_notes="Simplified analysis - full cross-referencing requires detailed business data",
            confidence=0.3 if committee_sectors else 0.0,
        )


