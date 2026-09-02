"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatScore, formatCrore, formatINR, formatPercent } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";
import { SCORE_COMPONENTS } from "@/lib/types";
import { publicPath } from "@/lib/paths";

interface CompareMP {
  mpName: string;
  constituency: string;
  party: string;
  state: string;
  stateSlug: string;
  mpSlug: string;
  house: string;
  photoUrl: string | null;
  compositeScore: number;
  isMinister?: boolean;
  estimated?: {
    attendance?: boolean;
    participation?: boolean;
    mplads?: boolean;
    assets?: boolean;
    criminal?: boolean;
    committee?: boolean;
    legislative?: boolean;
    accessibility?: boolean;
  };
  notApplicable?: { mplads?: boolean };
  dimensionScores: Record<string, number | null>;
  metrics: {
    attendancePct: number | null;
    questionsAsked: number | null;
    debatesParticipated: number | null;
    privateBills: number | null;
    criminalCases: number | null;
    seriousCases: number | null;
    totalAssets: number | null;
    mpladsEntitled: number | null;
    mpladsReleased: number | null;
    mpladsSanctioned: number | null;
    mpladsExpended: number | null;
    mpladsUtilization: number | null;
    worksCount: number | null;
  };
}

type MetricKey = keyof CompareMP["metrics"];

interface MetricRow {
  key: MetricKey;
  label: string;
  format: (v: number) => string;
  // higher | lower | none - which direction wins; none = informational only
  better: "higher" | "lower" | "none";
}

const METRIC_GROUPS: { title: string; rows: MetricRow[] }[] = [
  {
    title: "Parliament",
    rows: [
      { key: "attendancePct", label: "Attendance", format: (v) => formatPercent(v), better: "higher" },
      { key: "questionsAsked", label: "Questions asked", format: (v) => v.toLocaleString("en-IN"), better: "higher" },
      { key: "debatesParticipated", label: "Debates participated", format: (v) => v.toLocaleString("en-IN"), better: "higher" },
      { key: "privateBills", label: "Private bills introduced", format: (v) => v.toLocaleString("en-IN"), better: "higher" },
    ],
  },
  {
    title: "MPLADS funds",
    rows: [
      { key: "mpladsSanctioned", label: "Funds sanctioned", format: (v) => formatCrore(v), better: "none" },
      { key: "mpladsExpended", label: "Funds spent", format: (v) => formatCrore(v), better: "none" },
      { key: "mpladsUtilization", label: "Fund utilization", format: (v) => formatPercent(v), better: "higher" },
      { key: "worksCount", label: "Development works", format: (v) => v.toLocaleString("en-IN"), better: "higher" },
    ],
  },
  {
    title: "Declared assets",
    rows: [
      { key: "totalAssets", label: "Total assets", format: (v) => formatINR(v), better: "none" },
    ],
  },
  {
    title: "Criminal record",
    rows: [
      { key: "criminalCases", label: "Criminal cases", format: (v) => v.toLocaleString("en-IN"), better: "lower" },
      { key: "seriousCases", label: "Serious cases", format: (v) => v.toLocaleString("en-IN"), better: "lower" },
    ],
  },
];

const COLORS = ["#2563EB", "#DC2626", "#059669", "#D97706"];

/** Normalize a string for fuzzy matching */
function normalize(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
}

function fuzzyMatch(query: string, target: string): number {
  const normQ = normalize(query);
  const normT = normalize(target);
  if (!normQ) return 0;
  if (normT.startsWith(normQ)) return 1.0;
  if (normT.includes(normQ)) return 0.9;
  const queryTokens = normQ.split(" ").filter(Boolean);
  const targetTokens = normT.split(" ").filter(Boolean);
  let matched = 0;
  for (const qt of queryTokens) {
    for (const tt of targetTokens) {
      if (tt.startsWith(qt) || qt.startsWith(tt)) {
        matched++;
        break;
      }
    }
  }
  return (matched / queryTokens.length) * 0.8;
}

function searchIndex(query: string, mps: CompareMP[], limit = 10): CompareMP[] {
  if (!query || query.trim().length < 2) return [];
  const scored: { mp: CompareMP; score: number }[] = [];
  for (const mp of mps) {
    const best = Math.max(
      fuzzyMatch(query, mp.mpName),
      fuzzyMatch(query, mp.constituency) * 0.8,
      fuzzyMatch(query, mp.party) * 0.6,
      fuzzyMatch(query, mp.state) * 0.5
    );
    if (best > 0.35) scored.push({ mp, score: best });
  }
  scored.sort((a, b) => b.score - a.score || b.mp.compositeScore - a.mp.compositeScore);
  return scored.slice(0, limit).map((s) => s.mp);
}

function Avatar({ mp, size }: { mp: CompareMP; size: number }) {
  if (mp.photoUrl) {
    return (
      <img
        src={publicPath(mp.photoUrl)}
        alt={mp.mpName}
        className="rounded-full border-2 border-ink object-cover shrink-0"
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <div
      className="rounded-full border-2 border-ink bg-highlight flex items-center justify-center font-bold text-ink shrink-0"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {mp.mpName.charAt(0)}
    </div>
  );
}

function HouseChip({ house }: { house: string }) {
  return (
    <span className={`font-mono text-[10px] font-bold px-1 border border-ink ${house === "rajya_sabha" ? "bg-accent text-white" : "bg-surface text-ink"}`}>
      {house === "rajya_sabha" ? "RS" : "LS"}
    </span>
  );
}

/** Winner indexes for a metric row: indexes of selected MPs with the best
 * comparable value (all non-null, at least 2 values, not a tie). */
function winners(values: (number | null)[], better: "higher" | "lower" | "none"): Set<number> {
  const out = new Set<number>();
  if (better === "none") return out;
  const present = values.filter((v): v is number => v != null);
  if (present.length < 2) return out;
  const best = better === "higher" ? Math.max(...present) : Math.min(...present);
  const count = present.filter((v) => v === best).length;
  if (count !== 1) return out; // tie for best: no winner
  values.forEach((v, i) => {
    if (v === best) out.add(i);
  });
  return out;
}

/** Map a score-component key to its estimated-flag key. */
const ESTIMATED_KEY: Record<string, keyof NonNullable<CompareMP["estimated"]>> = {
  mplads_score: "mplads",
  asset_score: "assets",
  criminal_score: "criminal",
  attendance_score: "attendance",
  participation_score: "participation",
  committee_score: "committee",
  accessibility_score: "accessibility",
  legislative_score: "legislative",
};

/** Is a dimension score an estimated neutral placeholder (no underlying data)? */
function dimEstimated(mp: CompareMP, compKey: string): boolean {
  const k = ESTIMATED_KEY[compKey];
  return k ? !!mp.estimated?.[k] : false;
}

/** Does a dimension not apply to this MP at all (e.g. MPLADS for Rajya Sabha)? */
function dimNotApplicable(mp: CompareMP, compKey: string): boolean {
  if (compKey === "mplads_score") return !!mp.notApplicable?.mplads;
  return false;
}

/** Winner indexes among real (non-estimated) values only. Placeholder scores
 * can never win a row, and a row needs at least 2 real values to have a winner. */
function winnersReal(values: (number | null)[], estimated: boolean[]): Set<number> {
  const out = new Set<number>();
  const realIdx = values.map((v, i) => (v != null && !estimated[i] ? i : -1)).filter((i) => i >= 0);
  if (realIdx.length < 2) return out;
  const realVals = realIdx.map((i) => values[i] as number);
  const best = Math.max(...realVals);
  if (realVals.filter((v) => v === best).length !== 1) return out;
  out.add(realIdx[realVals.indexOf(best)]);
  return out;
}

export function ComparisonView() {
  const [mps, setMps] = useState<CompareMP[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState<CompareMP[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetch(publicPath("/data/compare-index.json"))
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((d) => setMps(d.mps))
      .catch(() => setLoadError(true));
  }, []);

  const searchResults = useMemo(() => {
    if (!mps || query.length < 2) return [];
    return searchIndex(query, mps, 8).filter(
      (r) => !selected.some((s) => s.mpSlug === r.mpSlug && s.stateSlug === r.stateSlug)
    );
  }, [query, mps, selected]);

  const addMP = (mp: CompareMP) => {
    if (selected.length >= 4) return;
    setSelected((prev) => [...prev, mp]);
    setQuery("");
  };

  const removeMP = (index: number) => {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  };

  // Dimension wins per MP (for the verdict)
  const dimensionWins: number[] = selected.map(() => 0);
  let dimsComparable = 0;
  if (selected.length >= 2) {
    for (const comp of SCORE_COMPONENTS) {
      const vals = selected.map((mp) => mp.dimensionScores?.[comp.key] ?? null);
      const est = selected.map((mp) => dimEstimated(mp, comp.key));
      const w = winnersReal(vals, est);
      if (vals.filter((v, i) => v != null && !est[i]).length >= 2) dimsComparable++;
      w.forEach((i) => dimensionWins[i]++);
    }
  }
  const maxWins = Math.max(...dimensionWins);
  const leaders = dimensionWins
    .map((w, i) => (w === maxWins ? i : -1))
    .filter((i) => i >= 0);
  const compositeVals = selected.map((mp) => mp.compositeScore);
  const bestComposite = Math.max(...compositeVals);
  const compositeWinner = compositeVals.filter((v) => v === bestComposite).length === 1
    ? compositeVals.indexOf(bestComposite)
    : -1;

  // Largest single dimension gap for the verdict sentence
  let biggestGap: { label: string; leader: number; delta: number } | null = null;
  if (selected.length >= 2) {
    for (const comp of SCORE_COMPONENTS) {
      const est = selected.map((mp) => dimEstimated(mp, comp.key));
      const vals = selected.map((mp, i) =>
        est[i] ? null : (mp.dimensionScores?.[comp.key] ?? null)
      );
      if (vals.some((v) => v == null)) continue;
      const max = Math.max(...(vals as number[]));
      const min = Math.min(...(vals as number[]));
      const delta = max - min;
      if (delta > (biggestGap?.delta ?? 0)) {
        biggestGap = { label: comp.label, leader: vals.indexOf(max), delta };
      }
    }
  }

  if (loadError) {
    return <p className="text-text-muted">Could not load the MP comparison index. Try reloading.</p>;
  }
  if (!mps) {
    return <p className="text-text-muted font-mono text-sm">Loading MP index...</p>;
  }

  return (
    <div className="space-y-6">
      {/* Search to add MPs */}
      {selected.length < 4 && (
        <Card>
          <CardContent className="p-4">
            <div className="relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`Search and add MP (${selected.length}/4 selected)...`}
                className="w-full border-3 border-ink bg-surface px-3 py-2 text-sm font-mono focus:outline-none focus:bg-highlight"
              />
              {searchResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 z-50 mt-1 border-3 border-ink bg-background shadow-brutal max-h-80 overflow-y-auto">
                  {searchResults.map((mp) => (
                    <button
                      key={`${mp.stateSlug}-${mp.mpSlug}`}
                      onClick={() => addMP(mp)}
                      className="flex w-full items-center gap-3 text-left p-2.5 border-b border-ink/20 hover:bg-highlight"
                    >
                      <Avatar mp={mp} size={32} />
                      <span className="flex-1 min-w-0">
                        <span className="font-bold text-sm block truncate">{mp.mpName}</span>
                        <span className="text-xs text-text-muted block truncate">
                          {mp.constituency}, {mp.state} · {mp.party}
                        </span>
                      </span>
                      <HouseChip house={mp.house} />
                      <span
                        className="font-mono text-xs font-bold shrink-0"
                        style={{ color: getScoreColor(mp.compositeScore) }}
                      >
                        {formatScore(mp.compositeScore)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Selected MPs */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selected.map((mp, i) => (
            <div
              key={i}
              className="flex items-center gap-2 border-3 border-ink px-2 py-1.5 bg-surface"
              style={{ borderLeftColor: COLORS[i], borderLeftWidth: "4px" }}
            >
              <Avatar mp={mp} size={28} />
              <span className="font-bold text-sm">{mp.mpName}</span>
              <HouseChip house={mp.house} />
              <button
                onClick={() => removeMP(i)}
                className="ml-1 text-danger font-bold hover:bg-danger/10 px-1"
                aria-label={`Remove ${mp.mpName}`}
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}

      {selected.length >= 2 && (
        <>
          {/* Head-to-head verdict */}
          <Card>
            <CardHeader>
              <CardTitle>Verdict</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {leaders.length === 1 ? (
                <p>
                  <span className="font-bold" style={{ color: COLORS[leaders[0]] }}>
                    {selected[leaders[0]].mpName}
                  </span>{" "}
                  leads on {maxWins} of {dimsComparable} comparable score dimensions.
                </p>
              ) : (
                <p>Even split across {dimsComparable} comparable score dimensions.</p>
              )}
              {compositeWinner >= 0 && (
                <p>
                  Overall transparency score:{" "}
                  <span className="font-bold" style={{ color: COLORS[compositeWinner] }}>
                    {selected[compositeWinner].mpName} {formatScore(bestComposite)}
                  </span>{" "}
                  vs {selected.map((mp, i) => (i === compositeWinner ? null : `${mp.mpName} ${formatScore(mp.compositeScore)}`)).filter(Boolean).join(" vs ")}.
                </p>
              )}
              {biggestGap && biggestGap.delta >= 5 && (
                <p className="text-text-muted">
                  Biggest gap: {biggestGap.label} -{" "}
                  {selected[biggestGap.leader].mpName} is {biggestGap.delta.toFixed(1)} points ahead.
                </p>
              )}
              <p className="text-text-muted text-xs">
                Green highlight marks the better real value in each row. Scores marked * are neutral estimates (no underlying data - e.g. PRS does not track ministers' attendance) and never win a row. Asset totals are shown for context - wealth alone is neither good nor bad.
              </p>
            </CardContent>
          </Card>

          {/* Head-to-head table */}
          <Card>
            <CardHeader>
              <CardTitle>Head to Head</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-2 border-ink">
                  <thead>
                    <tr className="bg-surface border-b-2 border-ink">
                      <th className="text-left p-3 font-bold min-w-[120px]">Metric</th>
                      {selected.map((mp, i) => (
                        <th key={i} className="text-center p-3 font-bold min-w-[96px]" style={{ color: COLORS[i] }}>
                          <Link
                            href={`/state/${mp.stateSlug}/mp/${mp.mpSlug}`}
                            className="hover:underline"
                          >
                            {mp.mpName}
                          </Link>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {/* Composite */}
                    <tr className="border-b-2 border-ink bg-highlight/30">
                      <td className="p-3 font-bold">Composite score</td>
                      {selected.map((mp, i) => {
                        const w = winners(compositeVals, "higher");
                        return (
                          <td key={i} className={`p-3 text-center ${w.has(i) ? "bg-success/20" : ""}`}>
                            <span className="text-xl font-bold font-mono" style={{ color: getScoreColor(mp.compositeScore) }}>
                              {formatScore(mp.compositeScore)}
                            </span>
                          </td>
                        );
                      })}
                    </tr>

                    {/* Dimension scores */}
                    {SCORE_COMPONENTS.map((comp) => {
                      const vals = selected.map((mp) =>
                        dimNotApplicable(mp, comp.key) ? null : (mp.dimensionScores?.[comp.key] ?? null)
                      );
                      const est = selected.map((mp) => dimEstimated(mp, comp.key));
                      const w = winnersReal(vals, est);
                      return (
                        <tr key={comp.key} className="border-b border-ink/30">
                          <td className="p-3 text-text-muted">
                            {comp.label}
                            <span className="text-xs text-text-muted font-mono ml-1">
                              ({(comp.weight * 100).toFixed(0)}%)
                            </span>
                          </td>
                          {vals.map((v, i) => (
                            <td key={i} className={`p-3 text-center font-mono text-sm ${w.has(i) ? "bg-success/20 font-bold" : ""}`}>
                              {dimNotApplicable(selected[i], comp.key) ? (
                                <span className="text-text-muted" title="Not applicable for this MP">
                                  N/A
                                </span>
                              ) : v != null ? (
                                est[i] ? (
                                  <span className="text-text-muted" title="Estimated: no underlying data">
                                    {v.toFixed(1)}*
                                  </span>
                                ) : (
                                  <span style={{ color: getScoreColor(v) }}>{v.toFixed(1)}</span>
                                )
                              ) : (
                                <span className="text-text-muted">—</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      );
                    })}

                    {/* Raw metric groups */}
                    {METRIC_GROUPS.map((group) => {
                      const visible = group.rows.filter((r) =>
                        selected.some((mp) => mp.metrics[r.key] != null)
                      );
                      if (visible.length === 0) return null;
                      return (
                        <MetricGroupRows key={group.title} group={{ ...group, rows: visible }} selected={selected} />
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {selected.length < 2 && (
        <div className="text-center py-12 text-text-muted">
          <p className="text-lg font-bold">Select at least 2 MPs to compare</p>
          <p className="text-sm mt-1">Search by name, constituency, or party - photos and house badges help you pick the right person</p>
        </div>
      )}
    </div>
  );
}

function MetricGroupRows({
  group,
  selected,
}: {
  group: { title: string; rows: MetricRow[] };
  selected: CompareMP[];
}) {
  return (
    <>
      <tr className="border-b border-ink/30 bg-surface">
        <td colSpan={selected.length + 1} className="p-2 px-3 font-bold uppercase text-xs tracking-wide text-text-secondary">
          {group.title}
        </td>
      </tr>
      {group.rows.map((row) => {
        const vals = selected.map((mp) => mp.metrics[row.key]);
        const w = winners(vals, row.better);
        return (
          <tr key={row.key} className="border-b border-ink/30">
            <td className="p-3 text-text-muted">{row.label}</td>
            {vals.map((v, i) => (
              <td key={i} className={`p-3 text-center font-mono text-sm ${w.has(i) ? "bg-success/20 font-bold" : ""}`}>
                {v != null ? row.format(v) : <span className="text-text-muted">—</span>}
              </td>
            ))}
          </tr>
        );
      })}
    </>
  );
}
