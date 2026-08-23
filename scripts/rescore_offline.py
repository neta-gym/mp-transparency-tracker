#!/usr/bin/env python3
"""
Offline re-score of all MPs from cached raw findings.

Runs the real Validator -> Assessor -> Developer pipeline over cached raw
data (data/{state}/raw/{slug}.json) without any network fetches, then
rebuilds state leaderboards and the national leaderboard exactly as a
normal cached pipeline run would.

Use when scoring/validation code has changed and outputs must be
regenerated without waiting on a full re-crawl of every source.
"""

import asyncio
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tracker.agents.manager import ManagerAgent
from tracker.config import settings
from tracker.models.schemas import NationalLeaderboard, ResearchFindings
from tracker.storage.database import Database
from tracker.utils.exporters import LeaderboardExporter
from tracker.utils.logger import console, get_logger

log = get_logger(__name__)


async def rescore_all() -> None:
    manager = ManagerAgent(Database(settings.database_path))
    # The Sansad Q&A cross-check fetches a national search per MP; skip it
    # so the offline run performs zero network calls.
    manager.validator.sansad_qa = None
    await manager.db.connect()

    try:
        state_results: list[tuple[str, list]] = []
        all_scores = []
        skipped = 0

        raw_dirs = sorted(glob.glob(os.path.join(settings.data_dir, "*", "raw")))
        for raw_dir in raw_dirs:
            state_slug = os.path.basename(os.path.dirname(raw_dir))
            scores = []

            for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
                if os.path.basename(path).endswith("_validated.json"):
                    continue
                try:
                    with open(path) as f:
                        findings = ResearchFindings.model_validate_json(f.read())
                except Exception as e:
                    log.warning("Skipping %s: %s", path, e)
                    skipped += 1
                    continue

                mp = findings.mp
                try:
                    validated = await manager.validator.validate(findings)
                    score = await manager.assessor.assess(validated)
                    await manager.developer.compile_report(validated, score, settings.data_dir)
                    manager._save_json_artifacts(mp, findings, validated, score)
                    scores.append(score)
                except Exception as e:
                    log.error("Rescore failed for %s (%s): %s", mp.name, state_slug, e)
                    skipped += 1

            if scores:
                console.print(f"  {state_slug}: {len(scores)} MPs re-scored")
                state_results.append((state_slug, scores))
                all_scores.extend(scores)

        console.print(f"\nRe-scored {len(all_scores)} MPs ({skipped} skipped)")

        # Percentiles across ALL MPs before building leaderboards
        manager._compute_wealth_percentiles(all_scores)

        # Rebuild each state leaderboard (DB + JSON + snapshot + MD)
        all_entries = []
        for state_slug, scores in state_results:
            lb = manager._build_leaderboard(state_slug, scores)
            await manager._save_leaderboard(state_slug, lb)
            all_entries.extend(lb.entries)

        # National leaderboard — mirror main.run_national exports
        all_entries.sort(key=lambda e: e.composite_score, reverse=True)
        for i, entry in enumerate(all_entries, 1):
            entry.rank = i

        national = NationalLeaderboard(
            total_mps=len(all_entries),
            states_included=[s for s, _ in state_results],
            top_n=min(50, len(all_entries)),
            entries=all_entries[:50],
        )

        lb_dir = os.path.join(settings.data_dir, "national", "leaderboard")
        os.makedirs(lb_dir, exist_ok=True)
        with open(os.path.join(lb_dir, "latest.json"), "w") as f:
            f.write(national.model_dump_json(indent=2))
        with open(os.path.join(lb_dir, "latest.md"), "w") as f:
            f.write(LeaderboardExporter.to_md(national))
        with open(os.path.join(lb_dir, "latest.html"), "w") as f:
            f.write(LeaderboardExporter.to_html(national))

        console.print(
            f"\n[bold green]National leaderboard rebuilt:[/bold green] "
            f"{national.total_mps} MPs from {len(national.states_included)} states"
        )
        top = ", ".join(f"{e.mp_name} ({e.composite_score:.1f})" for e in national.entries[:5])
        console.print(f"Top 5: {top}")
    finally:
        await manager.db.close()


if __name__ == "__main__":
    asyncio.run(rescore_all())
