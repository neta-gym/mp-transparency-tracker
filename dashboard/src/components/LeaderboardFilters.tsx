"use client";

import { useState, useMemo } from "react";
import type { LeaderboardEntry } from "@/lib/types";
import { MPCard } from "./MPCard";

/** Derive MP slug from entry name (client-safe, no fs dependency) */
function entryToSlug(entry: LeaderboardEntry): string {
  return entry.mp_name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

interface LeaderboardFiltersProps {
  entries: LeaderboardEntry[];
  stateSlug: string;
}

type SortField =
  | "composite_score"
  | "mplads_score"
  | "asset_score"
  | "criminal_score"
  | "attendance_score"
  | "participation_score"
  | "committee_score"
  | "accessibility_score"
  | "legislative_score";

export function LeaderboardFilters({ entries, stateSlug }: LeaderboardFiltersProps) {
  const [partyFilter, setPartyFilter] = useState<string[]>([]);
  const [houseFilter, setHouseFilter] = useState<string>("");
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(100);
  const [hasCriminalRecord, setHasCriminalRecord] = useState<boolean | null>(null);
  const [sortBy, setSortBy] = useState<SortField>("composite_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Extract unique parties
  const parties = useMemo(
    () => [...new Set(entries.map((e) => e.party))].sort(),
    [entries]
  );

  // Filter and sort
  const filtered = useMemo(() => {
    let result = [...entries];

    // Party filter
    if (partyFilter.length > 0) {
      result = result.filter((e) => partyFilter.includes(e.party));
    }

    // House filter
    if (houseFilter) {
      result = result.filter((e) => e.house === houseFilter);
    }

    // Score range
    result = result.filter(
      (e) => e.composite_score >= minScore && e.composite_score <= maxScore
    );

    // Criminal record filter
    if (hasCriminalRecord === true) {
      result = result.filter((e) => e.criminal_score < 100);
    } else if (hasCriminalRecord === false) {
      result = result.filter((e) => e.criminal_score >= 100);
    }

    // Sort
    result.sort((a, b) => {
      const aVal = a[sortBy];
      const bVal = b[sortBy];
      return sortDir === "desc" ? bVal - aVal : aVal - bVal;
    });

    return result;
  }, [entries, partyFilter, houseFilter, minScore, maxScore, hasCriminalRecord, sortBy, sortDir]);

  const toggleParty = (party: string) => {
    setPartyFilter((prev) =>
      prev.includes(party) ? prev.filter((p) => p !== party) : [...prev, party]
    );
  };

  return (
    <div className="space-y-4">
      {/* Filter controls */}
      <div className="p-4 border-3 border-ink bg-surface space-y-3">
        <h3 className="font-bold uppercase tracking-wide text-sm">Filters & Sort</h3>

        {/* Party multi-select */}
        <div>
          <label className="text-xs text-text-muted uppercase tracking-wide block mb-1">
            Party
          </label>
          <div className="flex flex-wrap gap-1">
            {parties.map((party) => (
              <button
                key={party}
                onClick={() => toggleParty(party)}
                className={`text-xs px-2 py-1 border-2 border-ink font-bold uppercase ${
                  partyFilter.includes(party)
                    ? "bg-primary text-white"
                    : "bg-surface text-ink hover:bg-highlight"
                }`}
              >
                {party}
              </button>
            ))}
            {partyFilter.length > 0 && (
              <button
                onClick={() => setPartyFilter([])}
                className="text-xs px-2 py-1 border-2 border-ink bg-danger text-white font-bold uppercase"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* House filter */}
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wide block mb-1">
              House
            </label>
            <select
              value={houseFilter}
              onChange={(e) => setHouseFilter(e.target.value)}
              className="w-full border-2 border-ink bg-surface px-2 py-1 text-sm font-mono"
            >
              <option value="">All</option>
              <option value="lok_sabha">Lok Sabha</option>
              <option value="rajya_sabha">Rajya Sabha</option>
            </select>
          </div>

          {/* Score range */}
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wide block mb-1">
              Min Score
            </label>
            <input
              type="number"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              min={0}
              max={100}
              className="w-full border-2 border-ink bg-surface px-2 py-1 text-sm font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wide block mb-1">
              Max Score
            </label>
            <input
              type="number"
              value={maxScore}
              onChange={(e) => setMaxScore(Number(e.target.value))}
              min={0}
              max={100}
              className="w-full border-2 border-ink bg-surface px-2 py-1 text-sm font-mono"
            />
          </div>

          {/* Criminal record */}
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wide block mb-1">
              Criminal Record
            </label>
            <select
              value={hasCriminalRecord === null ? "" : hasCriminalRecord ? "yes" : "no"}
              onChange={(e) =>
                setHasCriminalRecord(
                  e.target.value === "" ? null : e.target.value === "yes"
                )
              }
              className="w-full border-2 border-ink bg-surface px-2 py-1 text-sm font-mono"
            >
              <option value="">All</option>
              <option value="yes">Has Cases</option>
              <option value="no">Clean Record</option>
            </select>
          </div>
        </div>

        {/* Sort */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-text-muted uppercase tracking-wide">Sort by</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortField)}
            className="border-2 border-ink bg-surface px-2 py-1 text-sm font-mono"
          >
            <option value="composite_score">Composite</option>
            <option value="mplads_score">MPLADS</option>
            <option value="asset_score">Assets</option>
            <option value="criminal_score">Criminal</option>
            <option value="attendance_score">Attendance</option>
            <option value="participation_score">Participation</option>
            <option value="committee_score">Committees</option>
            <option value="accessibility_score">Accessibility</option>
            <option value="legislative_score">Legislative</option>
          </select>
          <button
            onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
            className="border-2 border-ink bg-surface px-2 py-1 text-sm font-mono hover:bg-highlight"
          >
            {sortDir === "desc" ? "High-Low" : "Low-High"}
          </button>
        </div>
      </div>

      {/* Results count */}
      <p className="text-sm text-text-muted">
        Showing {filtered.length} of {entries.length} MPs
      </p>

      {/* MP cards */}
      <div className="space-y-2">
        {filtered.map((entry, i) => (
          <MPCard
            key={entry.rank}
            entry={{ ...entry, rank: i + 1 }}
            stateSlug={stateSlug}
            mpSlug={entryToSlug(entry)}
          />
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-text-muted py-8">
          No MPs match the current filters.
        </p>
      )}
    </div>
  );
}
