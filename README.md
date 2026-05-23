# MP Transparency Tracker

Automated scoring system for Indian Members of Parliament. Researches, validates, and scores MPs on a 0–100 transparency index using data from MyNeta, PRS India, and MPLADS.

## Quick Start

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Run for Delhi (7 MPs)
python -m tracker.main --state delhi

# Or use the script
python scripts/run.py --state delhi
```

## Usage

```bash
# Run for any state — no code changes needed
python -m tracker.main --state maharashtra
python -m tracker.main --state "uttar pradesh"
python -m tracker.main --state goa

# Discover MPs only (no scoring)
python -m tracker.main --state delhi --discover-only

# Run for all states
python -m tracker.main --all-states
```

## Output

Results are saved under `data/{state-slug}/`:

```
data/delhi/
├── raw/              # Raw + validated JSON per MP
├── reports/          # Markdown reports per MP
├── scores/           # Score breakdown JSON per MP
└── leaderboard/      # latest.json, latest.md, timestamped snapshots
```

## Scoring Methodology (v1.0)

| Component | Weight | Source |
|-----------|--------|--------|
| MPLADS Fund Utilization | 30% | data.gov.in / dataful.in |
| Asset Growth | 20% | MyNeta affidavits |
| Criminal Record | 20% | MyNeta |
| Parliament Attendance | 15% | PRS India |
| Questions & Debates | 15% | PRS India |

**Composite Score** = weighted sum of all components (0–100).

## Architecture

```
Manager Agent → Researcher → Validator → Assessor → Developer
                (fetch data)  (cross-check) (score)   (report)
```

- Up to 3 MPs processed in parallel
- Claude API for gap-filling and qualitative assessment
- SQLite database for persistence and historical snapshots

## Tests

```bash
pytest tests/ -v
```

## Data Sources

- **MyNeta** (myneta.info) — Criminal records, asset declarations
- **PRS India** (via GitHub) — Parliament attendance, questions, debates
- **MPLADS** (dataful.in) — Fund utilization data
- **Claude** — Gap-filling, news context, qualitative assessment
