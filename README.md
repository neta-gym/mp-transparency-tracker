# MP Transparency Tracker

A production-ready, agentic transparency scoring pipeline for Indian Members of Parliament (MPs), with a static web dashboard for public exploration.

The system discovers MPs, collects public records from multiple open sources, validates data quality, computes standardized scores, and publishes state + national leaderboards.

It is designed to be:
- open-data first
- reproducible
- automation-friendly
- GitHub Pages deployable

## Why this project exists

Citizens often need to check MP performance across fragmented data sources (Sansad, PRS, affidavits, utilization reports, etc.). This project unifies that into a single structured workflow and scoring framework:

- discover current MPs from authoritative sources
- enrich profiles with parliamentary and governance indicators
- score each MP using a weighted transparency methodology
- publish machine-readable JSON + human-readable markdown reports
- render an interactive dashboard with maps, comparisons, and MP pages

## Core principles

1. Open-data only
   - Pipeline is built to run without paid LLM/API dependencies.
   - Inputs come from public, auditable sources.

2. Agentic pipeline design
   - The codebase uses role-based processing stages (manager/research/validate/assess/report) to keep responsibilities modular and extensible.

3. Deterministic outputs
   - Scoring rules and data transforms are code-defined and reproducible.

4. Public deployment by default
   - Dashboard is statically exported and deployable on GitHub Pages.

## High-level architecture

The tracker follows a staged, agentic flow:

Manager -> Discovery -> Research/Enrichment -> Validation -> Scoring -> Report Compilation -> Leaderboard Export

Mapped in code:
- src/tracker/agents/manager.py
- src/tracker/agents/researcher.py
- src/tracker/agents/validator.py
- src/tracker/agents/assessor.py
- src/tracker/agents/developer.py

Data and source connectors live under:
- src/tracker/tools/

Persistence and output helpers:
- src/tracker/storage/
- src/tracker/utils/

## Repository structure

- src/tracker/                    Core tracker package
- tests/                          Unit/integration tests
- scripts/                        Operational scripts (refresh, enrichment, notifications)
- data/                           Generated state/national outputs
- dashboard/                      Next.js static site
- .github/workflows/              CI + deployment workflows

## Data outputs

For each state, outputs are written under:

- data/{state-slug}/raw/          Raw and validated MP records
- data/{state-slug}/scores/       Score JSON per MP
- data/{state-slug}/reports/      Markdown report per MP
- data/{state-slug}/leaderboard/  latest.json + snapshots + latest.md

National aggregates are maintained under data/national/.

## Scoring model (overview)

Each MP receives a composite transparency score (0-100) from weighted components.

Current methodology in this repo is based on factors such as:
- MPLADS fund utilization
- asset growth/declarations
- criminal case disclosures
- parliamentary participation (attendance, questions, debates)

Exact implementation lives in scoring and utility modules inside src/tracker/.

## Supported data sources

- Digital Sansad / Sansad
- MyNeta affidavit-linked records
- PRS parliamentary data
- MPLADS/public expenditure datasets
- Additional governance/public-domain signals where available

## Quick start

Requirements:
- Python 3.10+ (recommended: 3.11)
- Node.js 20+ for dashboard build

### 1) Create virtual environment and install dependencies

From repo root:

python3.11 -m venv .venv311
. .venv311/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt pytest pytest-asyncio aioresponses

If you use another Python version, ensure it is >= 3.10.

### 2) Run tests

PYTHONPATH=src pytest tests -q

### 3) Run tracker for one state

PYTHONPATH=src python -m tracker.main --state delhi --format json

### 4) Run for all states

PYTHONPATH=src python -m tracker.main --all-states --format json

## Dashboard (Next.js static export)

The dashboard is a static app generated from files in data/.

Build:

cd dashboard
npm ci
npm run build

Local preview of exported site:

npx serve@latest out -p 3000

Important:
- Use Node 20+ (Next.js 15 requirement)
- This project uses static export output in dashboard/out

## GitHub Pages deployment

Workflow file:
- .github/workflows/deploy-dashboard.yml

Trigger:
- push to main affecting dashboard/** or data/**
- manual workflow dispatch

Expected public URL:
- https://neta-gym.github.io/mp-transparency-tracker/

If path routing looks broken, verify basePath/assetPrefix settings in dashboard Next config for repository pages deployment.

## CI

The repository includes CI checks via:
- .github/workflows/ci.yml

Typical gates include dependency install + test execution.

## Agentic operation model (for contributors)

Think in stable stages:
1) discovery: identify current MPs by state/house
2) enrichment: gather source records and normalize schemas
3) validation: confidence, consistency, and anomaly flags
4) scoring: weighted metric calculation
5) publication: reports + leaderboards + static dashboard

This separation keeps behavior debuggable and lets you improve one stage without destabilizing others.

## Development tips

- Always run tests before pushing
- Keep outputs reproducible and source-attributable
- Prefer schema-safe changes (models first, then tools)
- Avoid introducing hidden non-open dependencies

## Status and maturity

The codebase is already operational for nationwide data slices and supports static dashboard publication. Remaining work typically focuses on:
- improving enrichment coverage
- tightening validation confidence logic
- adding data quality diagnostics
- improving UX/visualization in dashboard

## Contributing

Contributions are welcome in:
- data quality checks
- source connector hardening
- test coverage
- scoring methodology transparency
- dashboard usability/performance

Please keep changes deterministic, documented, and aligned with open-data principles.

## License

Add your preferred open-source license in this repository (e.g., MIT/Apache-2.0) if not already set.
