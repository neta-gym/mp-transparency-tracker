"""Researcher agent — fetches data from all sources concurrently for one MP."""

from __future__ import annotations

import asyncio
from typing import Optional

from ..models.schemas import (
    MPProfile,
    ResearchFindings,
    CriminalRecord,
    AssetDeclaration,
    MPLADSFund,
    ParliamentActivity,
    NewsAllegation,
    EvidenceGrade,
    House,
    CommitteeEngagement,
    PublicAccessibility,
    NewsSentiment,
    LegislativeRecord,
    ConstituencyContext,
)
from ..storage.database import Database
from ..tools.myneta import MyNetaParser
from ..tools.prs import PRSFetcher
from ..tools.mplads import MPLADSFetcher
from ..tools.esakshi import ESAKSHIFetcher
from ..tools.mplads_datagov import DataGovMPLADSFetcher
from ..tools.sansad import SansadFetcher
from ..tools.social_media import SocialMediaFetcher
from ..tools.news import NewsFetcher
from ..tools.constituency import ConstituencyFetcher
from ..utils.mp_compensation import get_mp_compensation
from ..utils.logger import get_logger
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
        esakshi: Optional[ESAKSHIFetcher] = None,
        mplads_datagov: Optional[DataGovMPLADSFetcher] = None,
        sansad: Optional[SansadFetcher] = None,
        social_media: Optional[SocialMediaFetcher] = None,
        news: Optional[NewsFetcher] = None,
        constituency: Optional[ConstituencyFetcher] = None,
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

    async def research(self, mp: MPProfile) -> ResearchFindings:
        """Research an MP from all available sources concurrently."""
        log.info("[bold cyan]Researching:[/bold cyan] %s (%s)", mp.name, mp.constituency)
        sources_consulted: list[str] = []
        evidence_summary: dict[str, str] = {}

        # Fetch from all sources concurrently
        tasks = {}

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
            except Exception as e:
                log.warning("Committee fetch failed for %s: %s", mp.name, e)

        if "legislative" in tasks:
            try:
                legislative = await tasks["legislative"]
                if legislative.confidence > 0:
                    sources_consulted.append("sansad_legislative")
                    evidence_summary["legislative"] = EvidenceGrade.A.value
            except Exception as e:
                log.warning("Legislative record fetch failed for %s: %s", mp.name, e)

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
            except Exception as e:
                log.warning("Social media fetch failed for %s: %s", mp.name, e)

        if "news_sentiment" in tasks:
            try:
                news_sentiment = await tasks["news_sentiment"]
                if news_sentiment.confidence > 0:
                    sources_consulted.append("news")
            except Exception as e:
                log.warning("News fetch failed for %s: %s", mp.name, e)

        # Constituency context (sync, static data)
        constituency_context = self.constituency.fetch_context(mp)

        # Merge PRS private_bills into legislative record
        if parliament.private_bills_introduced > 0 and legislative.private_member_bills == 0:
            legislative.private_member_bills = parliament.private_bills_introduced

        # News and raw notes
        news = []
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
        )

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


