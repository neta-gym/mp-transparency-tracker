"""Entry point — accepts CLI args, wires everything together."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

from .config import settings
from .storage.database import Database
from .agents.manager import ManagerAgent
from .utils.logger import get_logger, console

log = get_logger(__name__)

# Indian states and UTs for --all-states
ALL_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "chandigarh",
    "dadra and nagar haveli and daman and diu", "lakshadweep",
    "andaman and nicobar islands", "puducherry",
]


async def run(
    state: str,
    discover_only: bool = False,
    include_rs: bool = False,
    update: bool = False,
    output_format: str = "md",
    compare: bool = False,
) -> None:
    """Run the pipeline for a single state."""
    db = Database(settings.database_path)
    await db.connect()

    manager = ManagerAgent(db)
    try:
        leaderboard = await manager.run(
            state, discover_only=discover_only, include_rs=include_rs, update=update,
        )
        if leaderboard:
            # Trend analysis: annotate leaderboard with deltas from previous run
            if compare:
                from .utils.trends import annotate_leaderboard_with_deltas
                previous = await db.get_previous_scores(state.replace(" ", "-").lower())
                if previous:
                    annotate_leaderboard_with_deltas(leaderboard, previous)
                    console.print(f"[dim]Trend data: compared against {len(previous)} prior scores[/dim]")
                else:
                    console.print("[dim]No prior run data available for comparison[/dim]")

            # Export in requested format
            _save_exports(leaderboard, state, output_format)

            console.print(f"\n[bold green]Pipeline complete for {state.title()}![/bold green]")
            state_slug = state.replace(' ', '-').lower()
            console.print(f"  Leaderboard: data/{state_slug}/leaderboard/latest.json")
            console.print(f"  Reports: data/{state_slug}/reports/")
    finally:
        await manager.cleanup()


async def run_states(states: list[str], include_rs: bool = False, update: bool = False, output_format: str = "md") -> None:
    """Run the pipeline for a list of states sequentially."""
    for state in states:
        try:
            console.print(f"\n{'='*60}")
            console.print(f"[bold]Processing: {state.title()}[/bold]")
            console.print(f"{'='*60}\n")
            await run(state, include_rs=include_rs, update=update, output_format=output_format)
        except Exception as e:
            log.error("Failed for state %s: %s", state, e)
            continue


async def run_all_states(include_rs: bool = False, update: bool = False, output_format: str = "md") -> None:
    """Run the pipeline for all Indian states sequentially."""
    await run_states(ALL_STATES, include_rs=include_rs, update=update, output_format=output_format)


async def run_single_mp(mp_name: str, state: str | None, update: bool = False) -> None:
    """Run the pipeline for a single MP by name."""
    db = Database(settings.database_path)
    await db.connect()

    manager = ManagerAgent(db)
    try:
        from .utils.name_match import name_matches

        # Find the MP
        if state:
            state_slug = state.replace(" ", "-").lower()
            mps = await manager._discover_mps(state_slug, include_rs=True)
            matches = [mp for mp in mps if name_matches(mp.name, mp_name, min_confidence=0.6)]
        else:
            # Search across all states in DB
            rows = await db.find_mp_by_name(mp_name)
            if rows:
                from .models.schemas import MPProfile, House
                matches = []
                for r in rows:
                    matches.append(MPProfile(
                        name=r["name"], constituency=r["constituency"],
                        state=r["state"], party=r["party"],
                        house=House(r.get("house", "lok_sabha")),
                        myneta_candidate_id=r.get("myneta_candidate_id"),
                        sansad_member_id=r.get("sansad_member_id"),
                    ))
            else:
                matches = []

        if not matches:
            console.print(f"[bold red]No MP found matching '{mp_name}'[/bold red]")
            if not state:
                console.print("[dim]Hint: try adding --state to narrow the search[/dim]")
            return

        if len(matches) > 1:
            console.print(f"[bold yellow]Multiple matches for '{mp_name}':[/bold yellow]")
            for i, mp in enumerate(matches, 1):
                console.print(f"  {i}. {mp.name} — {mp.constituency}, {mp.state.title()}")
            console.print("[dim]Using first match[/dim]")

        mp = matches[0]
        console.print(f"\n[bold cyan]Profiling:[/bold cyan] {mp.name} ({mp.constituency}, {mp.state.title()})")

        # Register MP
        await db.upsert_mp(mp)

        # Run pipeline for this MP only
        if update:
            await manager._ensure_browser()
        score = await manager._pipeline(mp, update=update)
        console.print(f"\n[bold green]Score: {score.composite_score:.1f}/100[/bold green]")
        console.print(f"  Key finding: {score.key_finding}")
        state_slug = mp.state.replace(" ", "-").lower()
        console.print(f"  Report: data/{state_slug}/reports/{mp.slug}.md")
    finally:
        await manager.cleanup()


async def run_national() -> None:
    """Build a national leaderboard from all cached state leaderboards."""
    db = Database(settings.database_path)
    await db.connect()

    try:
        from .models.schemas import NationalLeaderboard, Leaderboard

        rows = await db.get_all_latest_leaderboards()
        if not rows:
            console.print("[bold red]No state leaderboards found. Run --state first.[/bold red]")
            return

        all_entries = []
        states = []
        for row in rows:
            lb = Leaderboard.model_validate_json(row["leaderboard_json"])
            all_entries.extend(lb.entries)
            states.append(lb.state)

        # Sort by composite score, re-rank
        all_entries.sort(key=lambda e: e.composite_score, reverse=True)
        for i, entry in enumerate(all_entries, 1):
            entry.rank = i

        national = NationalLeaderboard(
            total_mps=len(all_entries),
            states_included=states,
            top_n=min(50, len(all_entries)),
            entries=all_entries[:50],
        )

        # Save
        import json
        lb_dir = os.path.join(settings.data_dir, "national", "leaderboard")
        os.makedirs(lb_dir, exist_ok=True)

        with open(os.path.join(lb_dir, "latest.json"), "w") as f:
            f.write(national.model_dump_json(indent=2))

        from .utils.exporters import LeaderboardExporter
        with open(os.path.join(lb_dir, "latest.md"), "w") as f:
            f.write(LeaderboardExporter.to_md(national))
        with open(os.path.join(lb_dir, "latest.html"), "w") as f:
            f.write(LeaderboardExporter.to_html(national))

        console.print(f"\n[bold green]National leaderboard: {len(all_entries)} MPs from {len(states)} states[/bold green]")
        console.print(f"  JSON: {lb_dir}/latest.json")
        console.print(f"  HTML: {lb_dir}/latest.html")

        # Display top 10
        from rich.table import Table
        table = Table(title="National Top 10")
        table.add_column("#", style="bold")
        table.add_column("MP", style="cyan")
        table.add_column("State")
        table.add_column("Party")
        table.add_column("Score", style="bold green")
        for e in national.entries[:10]:
            table.add_row(str(e.rank), e.mp_name, e.state.title(), e.party, f"{e.composite_score:.1f}")
        console.print(table)
    finally:
        await db.close()


async def run_compare_mps(names: list[str], state: str | None) -> None:
    """Compare two or more MPs side-by-side."""
    db = Database(settings.database_path)
    await db.connect()

    try:
        from .models.schemas import ScoreResult
        from .utils.mp_comparator import compare_mps

        scores = []
        for name in names:
            rows = await db.find_mp_by_name(name)
            if not rows:
                console.print(f"[bold red]MP not found: '{name}'[/bold red]")
                continue

            mp_row = rows[0]
            # Load score from DB
            assert db._conn is not None
            cursor = await db._conn.execute(
                "SELECT score_json FROM scores WHERE mp_slug = ? AND state = ? ORDER BY created_at DESC LIMIT 1",
                (mp_row["slug"], mp_row["state"]),
            )
            score_row = await cursor.fetchone()
            if score_row:
                score = ScoreResult.model_validate_json(score_row["score_json"])
                scores.append(score)
            else:
                console.print(f"[yellow]No score data for {name}. Run the pipeline first.[/yellow]")

        if len(scores) < 2:
            console.print("[bold red]Need at least 2 scored MPs to compare.[/bold red]")
            return

        result = compare_mps(scores)
        console.print(result.to_markdown())
    finally:
        await db.close()


def _save_exports(leaderboard, state: str, output_format: str) -> None:
    """Save leaderboard in the requested format(s)."""
    from .utils.exporters import LeaderboardExporter

    state_slug = state.replace(" ", "-").lower()
    lb_dir = os.path.join(settings.data_dir, state_slug, "leaderboard")

    ext_map = {"md": ".md", "csv": ".csv", "html": ".html", "json": ".json"}
    method_map = {
        "md": LeaderboardExporter.to_md,
        "csv": LeaderboardExporter.to_csv,
        "html": LeaderboardExporter.to_html,
        "json": LeaderboardExporter.to_json,
    }

    if output_format in method_map:
        ext = ext_map[output_format]
        content = method_map[output_format](leaderboard)
        path = os.path.join(lb_dir, f"latest{ext}")
        with open(path, "w") as f:
            f.write(content)
        if output_format != "json":
            console.print(f"  Export ({output_format.upper()}): {path}")


def _show_freshness(state: str) -> None:
    """Display data freshness report."""
    from rich.table import Table
    from .utils.freshness import freshness_report

    rows = freshness_report(state, settings.data_dir)
    if not rows:
        console.print(f"[yellow]No cached data found for {state.title()}[/yellow]")
        return

    table = Table(title=f"Data Freshness — {state.title()}")
    table.add_column("MP Name", style="cyan")
    table.add_column("Source")
    table.add_column("Last Fetched")
    table.add_column("Age (days)", justify="right")
    table.add_column("Grade")

    for r in rows:
        age = r["age_days"]
        if age > 90:
            age_style = "bold red"
        elif age > 30:
            age_style = "yellow"
        else:
            age_style = "green"
        table.add_row(
            r["mp_name"], r["source"],
            r["fetched_at"][:10] if len(r["fetched_at"]) >= 10 else r["fetched_at"],
            f"[{age_style}]{age}[/{age_style}]",
            r["grade"],
        )

    console.print(table)


def cli_entry() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MP Transparency Tracker — automated scoring of Indian Parliament members",
    )
    parser.add_argument("--state", type=str, help="State to process (e.g., 'delhi', 'maharashtra')")
    parser.add_argument("--states", type=str, help="Comma-separated list of states (e.g., 'delhi,maharashtra,bihar')")
    parser.add_argument("--all-states", action="store_true", help="Run for all Indian states")
    parser.add_argument("--discover-only", action="store_true", help="Only discover MPs, skip scoring")
    parser.add_argument("--include-rs", action="store_true", help="Include Rajya Sabha members")
    parser.add_argument("--update", action="store_true", help="Force re-fetch data from sources")

    # New feature flags
    parser.add_argument("--mp", type=str, help="Profile a specific MP by name (e.g., 'Bansuri Swaraj')")
    parser.add_argument("--national", action="store_true", help="Build national leaderboard from cached state data")
    parser.add_argument("--compare", action="store_true", help="Show score changes since last run")
    parser.add_argument("--compare-mps", nargs="+", metavar="NAME", help="Compare two or more MPs side-by-side")
    parser.add_argument("--format", choices=["md", "csv", "html", "json"], default="md", help="Leaderboard export format")
    parser.add_argument("--freshness", action="store_true", help="Show data freshness report")
    parser.add_argument("--rti-batch", action="store_true", help="Generate RTI templates for all MPs in a state")
    parser.add_argument("--max-age", type=int, default=None, help="Cache max age in days (default: 7). Cached data older than this is re-fetched.")

    # Debug flags
    parser.add_argument("--debug", action="store_true", help="Run debugger (no API key needed)")
    parser.add_argument("--debug-suite", type=str, default=None, help="Run specific debug suite")

    args = parser.parse_args()

    # Load .env
    load_dotenv()
    from .config import Settings
    import tracker.config
    tracker.config.settings = Settings()

    # Apply --max-age override
    if args.max_age is not None:
        tracker.config.settings.cache_max_age_days = args.max_age

    # --- Debugger ---
    if args.debug:
        from .debugger import DebuggerAgent
        agent = DebuggerAgent(
            data_dir=settings.data_dir,
            db_path=settings.database_path,
            state=args.state,
        )
        if args.debug_suite:
            asyncio.run(agent.run_suite(args.debug_suite))
        else:
            asyncio.run(agent.run_all())
        sys.exit(0)

    # --- Freshness report ---
    if args.freshness:
        if not args.state:
            console.print("[bold red]--freshness requires --state[/bold red]")
            sys.exit(1)
        _show_freshness(args.state)
        sys.exit(0)

    # --- RTI batch ---
    if args.rti_batch:
        if not args.state:
            console.print("[bold red]--rti-batch requires --state[/bold red]")
            sys.exit(1)
        from .utils.rti_batch import generate_rti_batch
        files = generate_rti_batch(args.state, settings.data_dir)
        console.print(f"[bold green]Generated {len(files)} RTI files[/bold green]")
        for f in files[:5]:
            console.print(f"  {f}")
        if len(files) > 5:
            console.print(f"  ... and {len(files) - 5} more")
        sys.exit(0)

    # --- National leaderboard ---
    if args.national:
        asyncio.run(run_national())
        sys.exit(0)

    # --- MP comparison ---
    if args.compare_mps:
        asyncio.run(run_compare_mps(args.compare_mps, args.state))
        sys.exit(0)

    # --- Single MP mode ---
    if args.mp:
        asyncio.run(run_single_mp(args.mp, args.state, update=args.update))
        sys.exit(0)

    # --- Standard pipeline ---
    if not args.state and not args.states and not args.all_states:
        parser.print_help()
        console.print("\n[yellow]Hint: try --state delhi  or  --states delhi,maharashtra,bihar[/yellow]")
        sys.exit(1)

    if args.all_states:
        asyncio.run(run_all_states(include_rs=args.include_rs, update=args.update, output_format=args.format))
    elif args.states:
        state_list = [s.strip().lower() for s in args.states.split(",") if s.strip()]
        asyncio.run(run_states(state_list, include_rs=args.include_rs, update=args.update, output_format=args.format))
    else:
        asyncio.run(run(
            args.state.lower(),
            discover_only=args.discover_only,
            include_rs=args.include_rs,
            update=args.update,
            output_format=args.format,
            compare=args.compare,
        ))


if __name__ == "__main__":
    cli_entry()
