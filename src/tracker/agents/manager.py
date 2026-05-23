"""Manager agent — orchestrates the full pipeline and builds leaderboards."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone, timedelta

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from ..config import settings
from ..models.schemas import (
    MPProfile,
    House,
    ResearchFindings,
    ScoreResult,
    LeaderboardEntry,
    Leaderboard,
)
from ..storage.database import Database
from ..tools.scraper import AsyncScraper
from ..tools.browser import PlaywrightBrowser
from ..tools.sansad import SansadFetcher
from ..tools.mp_discovery import MPDiscovery
from ..tools.myneta import MyNetaParser
from ..tools.prs import PRSFetcher
from ..tools.mplads import MPLADSFetcher
from ..tools.esakshi import ESAKSHIFetcher
from ..tools.mplads_datagov import DataGovMPLADSFetcher
from ..tools.cag import CAGFetcher
from ..tools.budget import BudgetFetcher
from ..tools.sansad_qa import SansadQAParser
from ..tools.social_media import SocialMediaFetcher
from ..tools.news import NewsFetcher
from ..tools.constituency import ConstituencyFetcher
from ..utils.logger import get_logger, console
from ..utils.name_match import name_matches
from .researcher import ResearcherAgent
from .validator import ValidatorAgent
from .developer import DeveloperAgent
from .assessor import AssessorAgent

log = get_logger(__name__)


# Path to seed data JSON
_SEED_DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "seed_mps.json")
_seed_cache: dict[str, list[MPProfile]] | None = None


def _load_seed_data() -> dict[str, list[MPProfile]]:
    """Load seed MP data from seed_mps.json for all states."""
    global _seed_cache
    if _seed_cache is not None:
        return _seed_cache

    _seed_cache = {}
    try:
        with open(_SEED_DATA_PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        log.warning("Seed data file not found: %s", _SEED_DATA_PATH)
        return _seed_cache

    for state_key, houses in data.items():
        state_norm = state_key.replace("-", " ").lower()
        mps: list[MPProfile] = []
        for house_key in ("lok_sabha", "rajya_sabha"):
            entries = houses.get(house_key, [])
            house_enum = House.LOK_SABHA if house_key == "lok_sabha" else House.RAJYA_SABHA
            for entry in entries:
                mps.append(MPProfile(
                    name=entry["name"],
                    constituency=entry["constituency"],
                    state=state_norm,
                    party=entry.get("party", "Unknown"),
                    myneta_candidate_id=entry.get("myneta_candidate_id"),
                    house=house_enum,
                ))
        _seed_cache[state_norm] = mps

    return _seed_cache


class ManagerAgent:
    """Orchestrates the full Research -> Validate -> Develop -> Assess pipeline."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.scraper = AsyncScraper()
        self._browser: PlaywrightBrowser | None = None
        self.sansad = SansadFetcher(self.scraper)
        self.discovery = MPDiscovery(self.scraper, self.sansad)

        # Tools
        self.myneta = MyNetaParser(self.scraper)
        self.prs = PRSFetcher(self.scraper)
        self.mplads = MPLADSFetcher(self.scraper)
        self.esakshi = ESAKSHIFetcher(self.scraper)  # browser wired in _ensure_browser
        self.mplads_datagov = DataGovMPLADSFetcher(self.scraper)
        self.cag = CAGFetcher()
        self.budget = BudgetFetcher(self.scraper)
        self.sansad_qa = SansadQAParser(self.scraper)
        self.social_media = SocialMediaFetcher(self.scraper)
        self.news = NewsFetcher(self.scraper)
        self.constituency = ConstituencyFetcher()

        # Agents
        self.researcher = ResearcherAgent(
            db, self.myneta, self.prs, self.mplads,
            esakshi=self.esakshi,
            mplads_datagov=self.mplads_datagov,
            sansad=self.sansad,
            social_media=self.social_media,
            news=self.news,
            constituency=self.constituency,
        )
        self.validator = ValidatorAgent(
            db, cag=self.cag, budget=self.budget, sansad_qa=self.sansad_qa,
        )
        self.developer = DeveloperAgent(db)
        self.assessor = AssessorAgent(db)

        self._semaphore = asyncio.Semaphore(settings.max_concurrent_mps)

    async def _ensure_browser(self) -> None:
        """Lazily start a Playwright browser and wire it into ESAKSHIFetcher."""
        if self._browser is not None:
            return
        try:
            self._browser = PlaywrightBrowser()
            await self._browser.start()
            self.esakshi = ESAKSHIFetcher(self.scraper, browser=self._browser)
            # Re-wire researcher with the updated esakshi fetcher
            self.researcher = ResearcherAgent(
                self.db, self.myneta, self.prs, self.mplads,
                esakshi=self.esakshi,
                mplads_datagov=self.mplads_datagov,
                sansad=self.sansad,
                social_media=self.social_media,
                news=self.news,
                constituency=self.constituency,
            )
            log.info("Playwright browser ready — eSAKSHI will use JS rendering")
        except Exception as e:
            log.warning(
                "Playwright browser failed to start: %s — eSAKSHI will use API/HTML fallbacks only",
                e,
            )
            self._browser = None

    async def run(
        self, state: str, discover_only: bool = False, include_rs: bool = False,
        update: bool = False,
    ) -> Leaderboard | None:
        """Run the full pipeline for a state."""
        state_slug = state.replace(" ", "-").lower()
        log.info("[bold green]Starting pipeline for state:[/bold green] %s", state)

        # Only start Playwright browser when re-fetching data
        if update:
            await self._ensure_browser()

        # Step 1: Discover MPs
        mps = await self._discover_mps(state_slug, include_rs=include_rs)
        if not mps:
            log.error("No MPs found for state: %s", state)
            return None

        ls_count = sum(1 for m in mps if m.house == House.LOK_SABHA)
        rs_count = sum(1 for m in mps if m.house == House.RAJYA_SABHA)
        console.print(f"\n[bold]Found {len(mps)} MPs for {state.title()} (LS: {ls_count}, RS: {rs_count}):[/bold]")
        for i, mp in enumerate(mps, 1):
            house_tag = "LS" if mp.house == House.LOK_SABHA else "RS"
            console.print(f"  {i}. [{house_tag}] {mp.name} — {mp.constituency} ({mp.party})")
        console.print()

        if discover_only:
            return None

        # Register MPs in database
        for mp in mps:
            await self.db.upsert_mp(mp)

        # Log cache status
        if update:
            console.print(f"[bold]Fetching fresh data for {len(mps)} MPs from sources...[/bold]\n")
        else:
            console.print(
                f"[bold]Smart cache enabled[/bold] (max age: {settings.cache_max_age_days}d) — "
                f"fresh data reused, missing dimensions auto-refreshed\n"
            )

        # Step 2: Process each MP through the pipeline
        scores: list[ScoreResult] = []
        failed: list[str] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Processing {len(mps)} MPs...", total=len(mps))

            async def process_mp(mp: MPProfile) -> ScoreResult | None:
                async with self._semaphore:
                    try:
                        return await self._pipeline(mp, update=update)
                    except Exception as e:
                        log.error("Pipeline failed for %s: %s", mp.name, e)
                        failed.append(mp.name)
                        return None
                    finally:
                        progress.advance(task)

            results = await asyncio.gather(*[process_mp(mp) for mp in mps])

        scores = [r for r in results if r is not None]

        if not scores:
            log.error("All MP pipelines failed!")
            return None

        # Step 3: Compute wealth percentiles across all MPs
        self._compute_wealth_percentiles(scores)

        # Step 4: Build leaderboard
        leaderboard = self._build_leaderboard(state_slug, scores)
        await self._save_leaderboard(state_slug, leaderboard)

        # Display results
        self._display_leaderboard(leaderboard)

        if failed:
            console.print(f"\n[bold red]Failed MPs:[/bold red] {', '.join(failed)}")

        console.print(f"\n[dim]Pipeline complete — no API tokens used (open data only)[/dim]")

        return leaderboard

    async def _discover_mps(self, state_slug: str, include_rs: bool = False) -> list[MPProfile]:
        """Discover MPs for a state, with seed data fallback."""
        mps = await self.discovery.discover(state_slug, include_rs=include_rs)

        # Fallback to seed data if discovery returned nothing
        seed_data = _load_seed_data()
        state_norm = state_slug.replace("-", " ").lower()
        seed_mps = seed_data.get(state_norm, [])

        if not mps and seed_mps:
            log.info("Using seed data for %s MPs", state_slug)
            seed = [mp for mp in seed_mps if mp.house == House.LOK_SABHA]
            if include_rs:
                seed.extend(mp for mp in seed_mps if mp.house == House.RAJYA_SABHA)
            mps = [mp.model_copy() for mp in seed]

        # If discovery found MPs but without MyNeta IDs, try to enrich from seed
        # Uses fuzzy matching to handle name spelling variants (e.g., Chandoliya vs Chandolia)
        if seed_mps and mps:
            from ..utils.name_match import name_matches
            seed_map = {mp.name.lower(): mp for mp in seed_mps}
            for mp in mps:
                if mp.myneta_candidate_id:
                    continue
                # Try exact match first
                seed_mp = seed_map.get(mp.name.lower())
                if not seed_mp:
                    # Fuzzy match: find best match from seed using name + constituency
                    for smp in seed_mps:
                        if name_matches(mp.name, smp.name, min_confidence=0.7):
                            if mp.constituency.lower() == smp.constituency.lower():
                                seed_mp = smp
                                break
                if seed_mp:
                    mp.myneta_candidate_id = seed_mp.myneta_candidate_id

        # Enrich with Sansad member IDs for any MPs that don't have them
        if mps:
            enriched = 0
            for mp in mps:
                if not mp.sansad_member_id:
                    member = await self.sansad.lookup_member(mp)
                    if member:
                        enriched += 1
            if enriched:
                log.info("Enriched %d/%d MPs with Sansad member IDs", enriched, len(mps))

        return mps

    def _load_cached_findings(self, mp: MPProfile) -> ResearchFindings | None:
        """Load cached research findings from disk if they exist."""
        cache_path = os.path.join(
            settings.data_dir, mp.state.replace(" ", "-").lower(),
            "raw", f"{mp.slug}.json",
        )
        if not os.path.exists(cache_path):
            return None
        try:
            with open(cache_path) as f:
                return ResearchFindings.model_validate_json(f.read())
        except Exception as e:
            log.warning("Failed to load cache for %s: %s", mp.name, e)
            return None

    def _is_cache_fresh(self, findings: ResearchFindings, max_age_days: int) -> bool:
        """Check if cached findings are within the freshness threshold."""
        collected = findings.collected_at
        # Handle naive datetimes (assume UTC)
        if collected.tzinfo is None:
            collected = collected.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - collected
        return age < timedelta(days=max_age_days)

    def _has_missing_dimensions(self, findings: ResearchFindings) -> list[str]:
        """Detect dimensions that returned empty/zero data and should be re-fetched.

        Returns list of source keys that need refreshing.
        Only includes sources where there's a realistic chance of getting data.
        """
        missing: list[str] = []

        # Committee data missing — only retry if MP has a working Sansad profile URL
        # (the /ls/members/{id} pages return 404 and committee API is 403)
        committees = findings.committees
        if not committees or committees.total_committees == 0:
            # Only attempt if we have a real profile URL (not a constructed one)
            mp = findings.mp
            if mp.profile_url and "sansad.in" in mp.profile_url:
                missing.append("committees")

        # Legislative data missing — same constraint as committees
        legislative = findings.legislative
        if not legislative or (
            legislative.zero_hour_mentions == 0
            and legislative.special_mentions == 0
            and legislative.bills_introduced == 0
            and legislative.private_member_bills == 0
            and legislative.confidence < 0.5
        ):
            mp = findings.mp
            if mp.profile_url and "sansad.in" in mp.profile_url:
                missing.append("legislative")

        # MyNeta data missing — check criminal and assets independently
        if (
            findings.criminal_record.confidence == 0.0
            and findings.assets.confidence == 0.0
        ):
            missing.append("myneta")
        elif (
            findings.assets.total_assets is None
            and findings.assets.confidence < 0.5
            and findings.mp.myneta_candidate_id
        ):
            # Assets specifically failed even though criminal parsed OK — re-fetch
            missing.append("myneta")

        # PRS data missing
        if (
            findings.parliament_activity.confidence == 0.0
            and findings.parliament_activity.attendance_percentage is None
        ):
            missing.append("prs")

        return missing

    async def _selective_refresh(
        self, mp: MPProfile, findings: ResearchFindings, missing: list[str],
    ) -> ResearchFindings:
        """Re-fetch only specific data sources and merge into existing findings."""
        log.info(
            "Selective refresh for %s — re-fetching: %s",
            mp.name, ", ".join(missing),
        )

        if "committees" in missing or "legislative" in missing:
            # Need Sansad member ID — ensure it's looked up
            if not mp.sansad_member_id:
                await self.sansad.lookup_member(mp)

        if "committees" in missing and self.sansad:
            try:
                committees = await self.sansad.fetch_committees(mp)
                findings.committees = committees
                if committees.total_committees > 0:
                    findings.evidence_summary["committees"] = "A"
                    log.info("  [refreshed] committees for %s: %d found", mp.name, committees.total_committees)
            except Exception as e:
                log.warning("  Committee refresh failed for %s: %s", mp.name, e)

        if "legislative" in missing and self.sansad:
            try:
                legislative = await self.sansad.fetch_legislative_record(mp)
                findings.legislative = legislative
                if legislative.confidence > 0.3:
                    findings.evidence_summary["legislative"] = "A"
                    log.info("  [refreshed] legislative for %s", mp.name)
            except Exception as e:
                log.warning("  Legislative refresh failed for %s: %s", mp.name, e)

        if "myneta" in missing and mp.myneta_candidate_id:
            try:
                criminal, assets, extras = await self.researcher.myneta.fetch_candidate(
                    mp.myneta_candidate_id
                )
                findings.criminal_record = criminal
                findings.assets = assets
                findings.evidence_summary["criminal"] = "B"
                findings.evidence_summary["assets"] = "B"
                # Also re-apply profile extras (education, photo, etc.)
                if extras.get("education"):
                    findings.mp.education = extras["education"]
                if extras.get("profession"):
                    findings.mp.profession = extras["profession"]
                if extras.get("age"):
                    findings.mp.age = extras["age"]
                if extras.get("photo_url"):
                    findings.mp.photo_url = extras["photo_url"]
                log.info(
                    "  [refreshed] myneta for %s — assets: %s, conf: %.1f",
                    mp.name,
                    f"Rs {assets.total_assets:,.0f}" if assets.total_assets else "null",
                    assets.confidence,
                )
            except Exception as e:
                log.warning("  MyNeta refresh failed for %s: %s", mp.name, e)

        if "prs" in missing:
            try:
                activity = await self.researcher.prs.fetch_activity(mp)
                findings.parliament_activity = activity
                if activity.confidence > 0:
                    findings.evidence_summary["parliament"] = "C"
                    log.info("  [refreshed] prs for %s", mp.name)
            except Exception as e:
                log.warning("  PRS refresh failed for %s: %s", mp.name, e)

        # Update collected_at to reflect the refresh
        findings.collected_at = datetime.now(timezone.utc)
        return findings

    async def _pipeline(self, mp: MPProfile, update: bool = False) -> ScoreResult:
        """Run the full R -> V -> D -> A pipeline for one MP.

        Smart caching:
        - If --update: always re-fetch everything
        - If cache exists and is fresh (< max_age_days): reuse, but selectively
          refresh any dimensions that returned empty (e.g., Sansad was down)
        - If cache is stale or missing: full re-fetch
        """
        max_age = settings.cache_max_age_days
        findings = None

        if not update:
            cached = self._load_cached_findings(mp)
            if cached:
                if self._is_cache_fresh(cached, max_age):
                    # Cache is fresh — check for missing dimensions to selectively refresh
                    missing = self._has_missing_dimensions(cached)
                    if missing:
                        collected = cached.collected_at.strftime("%Y-%m-%d")
                        log.info(
                            "[cached+refresh] %s — data from %s, refreshing: %s",
                            mp.name, collected, ", ".join(missing),
                        )
                        findings = await self._selective_refresh(mp, cached, missing)
                    else:
                        collected = cached.collected_at.strftime("%Y-%m-%d")
                        log.info("[cached] %s — all data fresh from %s", mp.name, collected)
                        findings = cached
                else:
                    age_days = (datetime.now(timezone.utc) - cached.collected_at.replace(
                        tzinfo=timezone.utc if cached.collected_at.tzinfo is None else cached.collected_at.tzinfo
                    )).days
                    log.info("[stale] %s — cache is %d days old (max %d), re-fetching", mp.name, age_days, max_age)

        if findings is None:
            await self._ensure_browser()
            findings = await self.researcher.research(mp)

        # Validate
        validated = await self.validator.validate(findings)

        # Assess (score)
        score = await self.assessor.assess(validated)

        # Develop (report)
        await self.developer.compile_report(validated, score, settings.data_dir)

        # Save raw JSON artifacts
        self._save_json_artifacts(mp, findings, validated, score)

        return score

    def _save_json_artifacts(self, mp, findings, validated, score) -> None:
        """Save raw JSON files for debugging / future use."""
        state_slug = mp.state.replace(" ", "-").lower()
        base = os.path.join(settings.data_dir, state_slug)

        # Raw findings
        raw_dir = os.path.join(base, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        with open(os.path.join(raw_dir, f"{mp.slug}.json"), "w") as f:
            f.write(findings.model_dump_json(indent=2))
        with open(os.path.join(raw_dir, f"{mp.slug}_validated.json"), "w") as f:
            f.write(validated.model_dump_json(indent=2))

        # Scores
        scores_dir = os.path.join(base, "scores")
        os.makedirs(scores_dir, exist_ok=True)
        with open(os.path.join(scores_dir, f"{mp.slug}.json"), "w") as f:
            f.write(score.model_dump_json(indent=2))

    def _compute_wealth_percentiles(self, scores: list[ScoreResult]) -> None:
        """Compute wealth percentile for each MP relative to all scored MPs.

        Reads cached findings to get asset data, computes percentiles, and
        writes updated findings back.
        """
        # Load asset values from cached findings
        asset_data: list[tuple[str, float]] = []  # (slug, total_assets)
        for s in scores:
            state_slug = s.mp.state.replace(" ", "-").lower()
            findings_path = os.path.join(
                settings.data_dir, state_slug, "raw", f"{s.mp.slug}.json"
            )
            if os.path.exists(findings_path):
                try:
                    with open(findings_path) as f:
                        findings = ResearchFindings.model_validate_json(f.read())
                    if findings.assets.total_assets is not None:
                        asset_data.append((s.mp.slug, findings.assets.total_assets))
                except Exception as e:
                    log.warning("Failed to load findings for percentile calc (%s): %s", s.mp.slug, e)

        if len(asset_data) < 2:
            return

        # Sort by total_assets and assign percentiles
        sorted_assets = sorted(asset_data, key=lambda x: x[1])
        n = len(sorted_assets)
        percentile_map = {}
        for i, (slug, _) in enumerate(sorted_assets):
            percentile_map[slug] = round((i / (n - 1)) * 100, 1) if n > 1 else 50.0

        # Update cached findings with percentiles
        for s in scores:
            if s.mp.slug not in percentile_map:
                continue
            state_slug = s.mp.state.replace(" ", "-").lower()
            findings_path = os.path.join(
                settings.data_dir, state_slug, "raw", f"{s.mp.slug}.json"
            )
            if os.path.exists(findings_path):
                try:
                    with open(findings_path) as f:
                        findings = ResearchFindings.model_validate_json(f.read())
                    findings.assets.wealth_percentile = percentile_map[s.mp.slug]
                    with open(findings_path, "w") as f:
                        f.write(findings.model_dump_json(indent=2))
                except Exception as e:
                    log.warning("Failed to update percentile for %s: %s", s.mp.slug, e)

    def _build_leaderboard(self, state_slug: str, scores: list[ScoreResult]) -> Leaderboard:
        """Build a ranked leaderboard from scores."""
        sorted_scores = sorted(scores, key=lambda s: s.composite_score, reverse=True)

        entries = []
        for rank, score in enumerate(sorted_scores, 1):
            house_val = score.mp.house.value if score.mp.house else "lok_sabha"
            avg_grade = self._compute_avg_evidence_grade(score.mp)

            entries.append(LeaderboardEntry(
                rank=rank,
                mp_name=score.mp.name,
                constituency=score.mp.constituency,
                party=score.mp.party,
                state=score.mp.state,
                composite_score=score.composite_score,
                mplads_score=score.breakdown.mplads_score,
                asset_score=score.breakdown.asset_score,
                criminal_score=score.breakdown.criminal_score,
                attendance_score=score.breakdown.attendance_score,
                participation_score=score.breakdown.participation_score,
                committee_score=score.breakdown.committee_score,
                accessibility_score=score.breakdown.accessibility_score,
                legislative_score=score.breakdown.legislative_score,
                data_confidence=score.data_confidence,
                key_finding=score.key_finding,
                house=house_val,
                photo_url=score.mp.photo_url,
                avg_evidence_grade=avg_grade,
            ))

        return Leaderboard(
            state=state_slug,
            total_mps=len(entries),
            entries=entries,
        )

    def _compute_avg_evidence_grade(self, mp: MPProfile) -> str:
        """Compute average evidence grade from cached findings for an MP.

        Reads evidence_summary from the raw findings JSON and averages the
        letter grades (A=4, B=3, C=2, D=1, E=0). Returns the closest letter.
        """
        grade_map = {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0}
        reverse_map = {4: "A", 3: "B", 2: "C", 1: "D", 0: "E"}

        state_slug = mp.state.replace(" ", "-").lower()
        findings_path = os.path.join(
            settings.data_dir, state_slug, "raw", f"{mp.slug}.json"
        )

        if not os.path.exists(findings_path):
            return "E"

        try:
            with open(findings_path) as f:
                data = json.load(f)
            evidence = data.get("evidence_summary", {})
            if not evidence:
                return "E"

            values = [grade_map.get(g.upper(), 0) for g in evidence.values() if g]
            if not values:
                return "E"

            avg = sum(values) / len(values)
            # Round to nearest grade
            rounded = min(reverse_map.keys(), key=lambda k: abs(k - avg))
            return reverse_map[rounded]
        except Exception as e:
            log.warning("Failed to compute evidence grade for %s: %s", mp.name, e)
            return "E"

    async def _save_leaderboard(self, state_slug: str, leaderboard: Leaderboard) -> None:
        """Save leaderboard to database + JSON + Markdown files."""
        await self.db.save_leaderboard(state_slug, leaderboard)

        lb_dir = os.path.join(settings.data_dir, state_slug, "leaderboard")
        os.makedirs(lb_dir, exist_ok=True)

        # JSON
        json_path = os.path.join(lb_dir, "latest.json")
        with open(json_path, "w") as f:
            f.write(leaderboard.model_dump_json(indent=2))

        # Timestamped snapshot
        ts = datetime.now(tz=None).strftime("%Y%m%d_%H%M%S")
        with open(os.path.join(lb_dir, f"{ts}.json"), "w") as f:
            f.write(leaderboard.model_dump_json(indent=2))

        # Markdown
        md_path = os.path.join(lb_dir, "latest.md")
        with open(md_path, "w") as f:
            f.write(self._leaderboard_to_md(leaderboard))

        log.info("[green]Leaderboard saved:[/green] %s", json_path)

    def _leaderboard_to_md(self, lb: Leaderboard) -> str:
        """Convert leaderboard to Markdown table."""
        lines = [
            f"# MP Transparency Leaderboard — {lb.state.title()}",
            "",
            f"*Generated: {lb.generated_at.strftime('%Y-%m-%d %H:%M UTC')} | "
            f"Methodology v{lb.methodology_version} | {lb.total_mps} MPs*",
            "",
            "| Rank | House | MP Name | Constituency | Party | Score | Confidence | Key Finding |",
            "|------|-------|---------|-------------|-------|-------|------------|-------------|",
        ]

        for e in lb.entries:
            house_tag = "LS" if e.house == "lok_sabha" else "RS"
            lines.append(
                f"| {e.rank} | {house_tag} | {e.mp_name} | {e.constituency} | {e.party} | "
                f"{e.composite_score:.1f} | {e.data_confidence:.0%} | {e.key_finding} |"
            )

        lines.extend([
            "",
            "### Score Breakdown",
            "",
            "| Rank | MP Name | House | MPLADS | Assets | Criminal | Attend. | Particip. | Committee | Access. | Legisl. |",
            "|------|---------|-------|--------|--------|----------|---------|-----------|-----------|---------|---------|",
        ])

        for e in lb.entries:
            house_tag = "LS" if e.house == "lok_sabha" else "RS"
            lines.append(
                f"| {e.rank} | {e.mp_name} | {house_tag} | {e.mplads_score:.0f} | {e.asset_score:.0f} | "
                f"{e.criminal_score:.0f} | {e.attendance_score:.0f} | {e.participation_score:.0f} | "
                f"{e.committee_score:.0f} | {e.accessibility_score:.0f} | {e.legislative_score:.0f} |"
            )

        return "\n".join(lines)

    def _display_leaderboard(self, lb: Leaderboard) -> None:
        """Print leaderboard as a Rich table."""
        table = Table(title=f"MP Transparency Leaderboard — {lb.state.title()}")
        table.add_column("Rank", justify="center", style="bold")
        table.add_column("House", justify="center")
        table.add_column("MP Name", style="cyan")
        table.add_column("Constituency")
        table.add_column("Party")
        table.add_column("Score", justify="center", style="bold green")
        table.add_column("Confidence", justify="center")
        table.add_column("Key Finding", style="dim")

        for e in lb.entries:
            house_tag = "LS" if e.house == "lok_sabha" else "RS"
            score_style = "bold green" if e.composite_score >= 70 else "bold yellow" if e.composite_score >= 50 else "bold red"
            table.add_row(
                str(e.rank),
                house_tag,
                e.mp_name,
                e.constituency,
                e.party,
                f"{e.composite_score:.1f}",
                f"{e.data_confidence:.0%}",
                e.key_finding,
                style=None,
            )

        console.print()
        console.print(table)

    async def cleanup(self) -> None:
        """Close connections."""
        if self._browser:
            await self._browser.close()
        await self.scraper.close()
        await self.db.close()
