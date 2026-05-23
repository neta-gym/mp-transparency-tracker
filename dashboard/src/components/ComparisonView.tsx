"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBadge } from "./ScoreBadge";
import type { SearchResult } from "@/lib/search-client";
import { searchMPs } from "@/lib/search-client";
import { formatScore } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";
import { SCORE_COMPONENTS } from "@/lib/types";

interface ComparisonViewProps {
  allEntries: SearchResult[];
}

type ComparisonMP = SearchResult;

export function ComparisonView({ allEntries }: ComparisonViewProps) {
  const [selected, setSelected] = useState<ComparisonMP[]>([]);
  const [query, setQuery] = useState("");

  const searchResults = useMemo(() => {
    if (query.length < 2) return [];
    return searchMPs(query, allEntries, 8).filter(
      (r) => !selected.some((s) => s.mpSlug === r.mpSlug && s.stateSlug === r.stateSlug)
    );
  }, [query, allEntries, selected]);

  const addMP = (result: SearchResult) => {
    if (selected.length >= 4) return;
    setSelected((prev) => [...prev, result]);
    setQuery("");
  };

  const removeMP = (index: number) => {
    setSelected((prev) => prev.filter((_, i) => i !== index));
  };

  // Color palette for comparison lines
  const colors = ["#2563EB", "#DC2626", "#059669", "#D97706"];

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
                <div className="absolute top-full left-0 right-0 z-50 mt-1 border-3 border-ink bg-background shadow-brutal max-h-60 overflow-y-auto">
                  {searchResults.map((result) => (
                    <button
                      key={`${result.stateSlug}-${result.mpSlug}`}
                      onClick={() => addMP(result)}
                      className="block w-full text-left p-3 border-b border-ink/20 hover:bg-highlight"
                    >
                      <span className="font-bold text-sm">{result.mpName}</span>
                      <span className="text-xs text-text-muted ml-2">
                        {result.constituency}, {result.state} · {result.party}
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
              className="flex items-center gap-2 border-3 border-ink px-3 py-1.5 bg-surface"
              style={{ borderLeftColor: colors[i], borderLeftWidth: "4px" }}
            >
              <span className="font-bold text-sm">{mp.mpName}</span>
              <span className="text-xs text-text-muted">({mp.party})</span>
              <button
                onClick={() => removeMP(i)}
                className="ml-1 text-danger font-bold hover:bg-danger/10 px-1"
              >
                x
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Comparison table */}
      {selected.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Score Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-2 border-ink">
                <thead>
                  <tr className="bg-surface border-b-2 border-ink">
                    <th className="text-left p-3 font-bold">Metric</th>
                    {selected.map((mp, i) => (
                      <th
                        key={i}
                        className="text-center p-3 font-bold"
                        style={{ color: colors[i] }}
                      >
                        {mp.mpName}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Composite score */}
                  <tr className="border-b-2 border-ink bg-highlight/30">
                    <td className="p-3 font-bold">Composite Score</td>
                    {selected.map((mp, i) => (
                      <td key={i} className="p-3 text-center">
                        <span
                          className="text-xl font-bold font-mono"
                          style={{ color: getScoreColor(mp.compositeScore) }}
                        >
                          {formatScore(mp.compositeScore)}
                        </span>
                      </td>
                    ))}
                  </tr>

                  {/* Profile info */}
                  <tr className="border-b border-ink/30">
                    <td className="p-3 text-text-muted">Constituency</td>
                    {selected.map((mp, i) => (
                      <td key={i} className="p-3 text-center text-xs">
                        {mp.constituency}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b border-ink/30">
                    <td className="p-3 text-text-muted">Party</td>
                    {selected.map((mp, i) => (
                      <td key={i} className="p-3 text-center font-bold text-xs">
                        {mp.party}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b border-ink/30">
                    <td className="p-3 text-text-muted">State</td>
                    {selected.map((mp, i) => (
                      <td key={i} className="p-3 text-center text-xs">
                        {mp.state}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b-2 border-ink">
                    <td className="p-3 text-text-muted">House</td>
                    {selected.map((mp, i) => (
                      <td key={i} className="p-3 text-center font-mono text-xs">
                        {mp.house === "lok_sabha" ? "LS" : "RS"}
                      </td>
                    ))}
                  </tr>

                  {/* Dimension scores */}
                  {SCORE_COMPONENTS.map((comp) => (
                    <tr key={comp.key} className="border-b border-ink/30">
                      <td className="p-3 text-text-muted">
                        {comp.label}
                        <span className="text-xs text-text-muted font-mono ml-1">
                          ({(comp.weight * 100).toFixed(0)}%)
                        </span>
                      </td>
                      {selected.map((mp, i) => {
                        const val = mp.dimensionScores?.[comp.key];
                        return (
                          <td key={i} className="p-3 text-center font-mono text-sm">
                            {val != null ? (
                              <span style={{ color: getScoreColor(val) }}>
                                {val.toFixed(1)}
                              </span>
                            ) : (
                              <span className="text-text-muted">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {selected.length < 2 && (
        <div className="text-center py-12 text-text-muted">
          <p className="text-lg font-bold">Select at least 2 MPs to compare</p>
          <p className="text-sm mt-1">Use the search box above to find and add MPs</p>
        </div>
      )}
    </div>
  );
}
