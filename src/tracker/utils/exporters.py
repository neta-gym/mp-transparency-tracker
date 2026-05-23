"""Export leaderboards and reports in multiple formats (CSV, HTML, JSON, Markdown)."""

from __future__ import annotations

import csv
import io
import json
from typing import Union

from ..models.schemas import Leaderboard, NationalLeaderboard
from ..utils.logger import get_logger

log = get_logger(__name__)

AnyLeaderboard = Union[Leaderboard, NationalLeaderboard]


class LeaderboardExporter:
    """Export leaderboards to various formats."""

    @staticmethod
    def to_csv(leaderboard: AnyLeaderboard) -> str:
        """Generate CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Rank", "House", "MP Name", "Constituency", "Party", "State",
            "Composite Score", "MPLADS", "Assets", "Criminal", "Attendance",
            "Participation", "Committee", "Accessibility", "Legislative",
            "Confidence", "Key Finding",
        ])
        for e in leaderboard.entries:
            house_tag = "LS" if e.house == "lok_sabha" else "RS"
            writer.writerow([
                e.rank, house_tag, e.mp_name, e.constituency, e.party, e.state,
                f"{e.composite_score:.1f}",
                f"{e.mplads_score:.1f}", f"{e.asset_score:.1f}", f"{e.criminal_score:.1f}",
                f"{e.attendance_score:.1f}", f"{e.participation_score:.1f}",
                f"{e.committee_score:.1f}", f"{e.accessibility_score:.1f}",
                f"{e.legislative_score:.1f}",
                f"{e.data_confidence:.2f}", e.key_finding,
            ])
        return output.getvalue()

    @staticmethod
    def to_json(leaderboard: AnyLeaderboard) -> str:
        """Pretty-printed JSON."""
        return leaderboard.model_dump_json(indent=2)

    @staticmethod
    def to_md(leaderboard: AnyLeaderboard) -> str:
        """Markdown table format."""
        lb = leaderboard
        state_label = getattr(lb, "state", "National")

        lines = [
            f"# MP Transparency Leaderboard — {state_label.title()}",
            "",
            f"*Generated: {lb.generated_at.strftime('%Y-%m-%d %H:%M UTC')} | "
            f"Methodology v{lb.methodology_version} | {lb.total_mps} MPs*",
            "",
            "| Rank | House | MP Name | Constituency | Party | Score | Confidence | Key Finding |",
            "|------|-------|---------|-------------|-------|-------|------------|-------------|",
        ]

        for e in lb.entries:
            house_tag = "LS" if e.house == "lok_sabha" else "RS"
            delta_str = ""
            if e.delta is not None:
                delta_str = f" ({'+' if e.delta >= 0 else ''}{e.delta:.1f})"
            lines.append(
                f"| {e.rank} | {house_tag} | {e.mp_name} | {e.constituency} | {e.party} | "
                f"{e.composite_score:.1f}{delta_str} | {e.data_confidence:.0%} | {e.key_finding} |"
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

    @staticmethod
    def to_html(leaderboard: AnyLeaderboard) -> str:
        """Self-contained interactive HTML dashboard."""
        lb = leaderboard
        state_label = getattr(lb, "state", "National")

        # Serialize entries to JSON for embedded JS
        entries_json = json.dumps([e.model_dump() for e in lb.entries], default=str)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MP Transparency Leaderboard — {state_label.title()}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #1a202c; padding: 20px; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 1.8em; margin-bottom: 4px; }}
  .meta {{ color: #718096; margin-bottom: 20px; font-size: 0.9em; }}
  .stats {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat-card {{ background: white; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .stat-card .value {{ font-size: 2em; font-weight: 700; }}
  .stat-card .label {{ color: #718096; font-size: 0.85em; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th {{ background: #2d3748; color: white; padding: 12px 8px; text-align: left; cursor: pointer; font-size: 0.85em; white-space: nowrap; }}
  th:hover {{ background: #4a5568; }}
  th.sorted-asc::after {{ content: ' ▲'; }}
  th.sorted-desc::after {{ content: ' ▼'; }}
  td {{ padding: 10px 8px; border-bottom: 1px solid #e2e8f0; font-size: 0.9em; }}
  tr:hover {{ background: #f7fafc; }}
  .score {{ font-weight: 700; padding: 2px 8px; border-radius: 4px; }}
  .score-high {{ background: #c6f6d5; color: #22543d; }}
  .score-mid {{ background: #fefcbf; color: #744210; }}
  .score-low {{ background: #fed7d7; color: #742a2a; }}
  .bar {{ display: inline-block; height: 8px; border-radius: 4px; min-width: 2px; }}
  .bar-green {{ background: #48bb78; }}
  .bar-yellow {{ background: #ecc94b; }}
  .bar-red {{ background: #f56565; }}
  .delta-pos {{ color: #38a169; font-weight: 600; }}
  .delta-neg {{ color: #e53e3e; font-weight: 600; }}
  #chart-container {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); max-width: 800px; }}
  .filter-bar {{ margin-bottom: 16px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  .filter-bar input {{ padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9em; }}
  .filter-bar select {{ padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9em; }}
  footer {{ margin-top: 24px; color: #a0aec0; font-size: 0.8em; text-align: center; }}
  @media (max-width: 768px) {{ table {{ font-size: 0.8em; }} td, th {{ padding: 6px 4px; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>MP Transparency Leaderboard — {state_label.title()}</h1>
  <p class="meta">Generated: {lb.generated_at.strftime('%Y-%m-%d %H:%M UTC')} | Methodology v{lb.methodology_version} | {lb.total_mps} MPs</p>

  <div class="stats" id="stats"></div>
  <div id="chart-container"><canvas id="scoreChart"></canvas></div>

  <div class="filter-bar">
    <input type="text" id="search" placeholder="Search MP name..." oninput="filterTable()">
    <select id="partyFilter" onchange="filterTable()"><option value="">All Parties</option></select>
    <select id="sortDim" onchange="sortByDimension()">
      <option value="composite_score">Sort by: Composite</option>
      <option value="mplads_score">MPLADS</option>
      <option value="asset_score">Assets</option>
      <option value="criminal_score">Criminal</option>
      <option value="attendance_score">Attendance</option>
      <option value="participation_score">Participation</option>
      <option value="committee_score">Committee</option>
      <option value="accessibility_score">Accessibility</option>
      <option value="legislative_score">Legislative</option>
    </select>
  </div>

  <table id="leaderboard">
    <thead>
      <tr>
        <th onclick="sortTable(0)">#</th>
        <th onclick="sortTable(1)">House</th>
        <th onclick="sortTable(2)">MP Name</th>
        <th onclick="sortTable(3)">Constituency</th>
        <th onclick="sortTable(4)">Party</th>
        <th onclick="sortTable(5)">Score</th>
        <th onclick="sortTable(6)">MPLADS</th>
        <th onclick="sortTable(7)">Assets</th>
        <th onclick="sortTable(8)">Criminal</th>
        <th onclick="sortTable(9)">Attend.</th>
        <th onclick="sortTable(10)">Particip.</th>
        <th onclick="sortTable(11)">Committee</th>
        <th onclick="sortTable(12)">Access.</th>
        <th onclick="sortTable(13)">Legisl.</th>
        <th onclick="sortTable(14)">Confidence</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <footer>MP Transparency Tracker — Automated scoring from public data sources</footer>
</div>

<script>
const DATA = {entries_json};
let sortCol = 5, sortAsc = false;

function scoreClass(v) {{ return v >= 70 ? 'score-high' : v >= 50 ? 'score-mid' : 'score-low'; }}
function barClass(v) {{ return v >= 70 ? 'bar-green' : v >= 50 ? 'bar-yellow' : 'bar-red'; }}
function dimBar(v) {{ return `<span class="bar ${{barClass(v)}}" style="width:${{v*0.6}}px"></span> ${{v.toFixed(0)}}`; }}

function renderStats() {{
  const scores = DATA.map(d => d.composite_score);
  const avg = (scores.reduce((a,b)=>a+b,0)/scores.length).toFixed(1);
  const maxS = Math.max(...scores).toFixed(1);
  const minS = Math.min(...scores).toFixed(1);
  document.getElementById('stats').innerHTML = `
    <div class="stat-card"><div class="value">${{DATA.length}}</div><div class="label">MPs Scored</div></div>
    <div class="stat-card"><div class="value">${{avg}}</div><div class="label">Average Score</div></div>
    <div class="stat-card"><div class="value">${{maxS}}</div><div class="label">Highest</div></div>
    <div class="stat-card"><div class="value">${{minS}}</div><div class="label">Lowest</div></div>
  `;
}}

function renderChart() {{
  const ctx = document.getElementById('scoreChart').getContext('2d');
  const sorted = [...DATA].sort((a,b) => b.composite_score - a.composite_score);
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: sorted.map(d => d.mp_name),
      datasets: [{{
        label: 'Composite Score',
        data: sorted.map(d => d.composite_score),
        backgroundColor: sorted.map(d => d.composite_score >= 70 ? '#48bb78' : d.composite_score >= 50 ? '#ecc94b' : '#f56565'),
        borderRadius: 4,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      scales: {{ x: {{ min: 0, max: 100 }} }},
      plugins: {{ legend: {{ display: false }} }},
      maintainAspectRatio: false,
    }}
  }});
  document.getElementById('chart-container').style.height = Math.max(200, sorted.length * 35 + 60) + 'px';
}}

function populateFilters() {{
  const parties = [...new Set(DATA.map(d => d.party))].sort();
  const sel = document.getElementById('partyFilter');
  parties.forEach(p => {{ const o = document.createElement('option'); o.value = p; o.textContent = p; sel.appendChild(o); }});
}}

function renderTable(data) {{
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = data.map((e, i) => {{
    const house = e.house === 'lok_sabha' ? 'LS' : 'RS';
    let deltaStr = '';
    if (e.delta != null) deltaStr = `<span class="${{e.delta >= 0 ? 'delta-pos' : 'delta-neg'}}">${{e.delta >= 0 ? '+' : ''}}${{e.delta.toFixed(1)}}</span>`;
    return `<tr>
      <td>${{e.rank}}</td><td>${{house}}</td><td><strong>${{e.mp_name}}</strong></td>
      <td>${{e.constituency}}</td><td>${{e.party}}</td>
      <td><span class="score ${{scoreClass(e.composite_score)}}">${{e.composite_score.toFixed(1)}}</span> ${{deltaStr}}</td>
      <td>${{dimBar(e.mplads_score)}}</td><td>${{dimBar(e.asset_score)}}</td><td>${{dimBar(e.criminal_score)}}</td>
      <td>${{dimBar(e.attendance_score)}}</td><td>${{dimBar(e.participation_score)}}</td>
      <td>${{dimBar(e.committee_score)}}</td><td>${{dimBar(e.accessibility_score)}}</td><td>${{dimBar(e.legislative_score)}}</td>
      <td>${{(e.data_confidence * 100).toFixed(0)}}%</td>
    </tr>`;
  }}).join('');
}}

function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  const party = document.getElementById('partyFilter').value;
  let filtered = DATA.filter(d => {{
    if (q && !d.mp_name.toLowerCase().includes(q)) return false;
    if (party && d.party !== party) return false;
    return true;
  }});
  renderTable(filtered);
}}

function sortByDimension() {{
  const dim = document.getElementById('sortDim').value;
  const sorted = [...DATA].sort((a, b) => b[dim] - a[dim]);
  sorted.forEach((e, i) => e.rank = i + 1);
  renderTable(sorted);
}}

function sortTable(col) {{
  sortAsc = (sortCol === col) ? !sortAsc : false;
  sortCol = col;
  // Re-render with current filter applied
  filterTable();
}}

renderStats();
renderChart();
populateFilters();
renderTable(DATA);
</script>
</body>
</html>"""
