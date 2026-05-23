# Agent Guide for MP Transparency Tracker

This file is for AI coding agents such as Codex, Claude Code, OpenCode, and other automated contributors.

Read `README.md` first. The key project goal is to turn open public data about Indian MPs into reproducible transparency rankings and an inspectable static dashboard.

## Non-negotiable invariants

1. No hidden LLM/API dependency in the data pipeline.
   - Do not add Claude/OpenAI/LLM calls to discovery, enrichment, validation, scoring, or report generation unless explicitly requested by the maintainer.
   - Prefer rule-based, source-backed, reproducible logic.

2. Do not hand-edit rankings.
   - Leaderboards are generated artifacts.
   - If a rank looks wrong, fix source matching, data normalization, validation, or scoring code; then regenerate outputs.

3. Keep the methodology explainable.
   - Score = weighted 0-100 composite.
   - Confidence = evidence/source confidence, not the same as score.
   - Watchlists/red flags are scrutiny aids, not legal conclusions.

4. Preserve national coverage.
   - Current expected scale: 36 states/UTs, 537 MPs.
   - After pipeline changes, check `data/national/leaderboard/latest.json`.

5. Respect GitHub Pages subpath deployment.
   - Live URL is `https://neta-gym.github.io/mp-transparency-tracker/`.
   - Dashboard public assets and client fetches must work under `/mp-transparency-tracker/`.

## Important files

```text
src/tracker/config.py                 scoring weights and source URL config
src/tracker/agents/assessor.py        component scoring and composite score calculation
src/tracker/agents/manager.py         orchestration and leaderboard export
src/tracker/tools/                    public-data connectors
data/national/leaderboard/latest.json current national ranking
dashboard/src/                        Next.js dashboard source
dashboard/next.config.ts              static export/base path config
.github/workflows/deploy-dashboard.yml GitHub Pages deploy
```

## Commands

Run tests:

```bash
PYTHONPATH=src pytest tests -q
```

Run one state:

```bash
PYTHONPATH=src python -m tracker.main --state "Delhi" --format json
```

Run all states:

```bash
PYTHONPATH=src python -m tracker.main --all-states --format json
```

Build dashboard:

```bash
cd dashboard
npm run build
```

Preview dashboard static export:

```bash
cd dashboard
npx serve@latest out -p 3000
```

## Before finalizing changes

- Check `git status --short` and avoid overwriting unrelated local work.
- Run relevant tests/builds.
- If scoring weights or formulas change, update README methodology text.
- If dashboard data changes, rebuild before assessing UI.
- If Pages rendering changes, verify base-path-safe assets under `/mp-transparency-tracker/`.
