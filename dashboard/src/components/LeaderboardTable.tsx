"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import type { LeaderboardEntry } from "@/lib/types";
import { SCORE_COMPONENTS } from "@/lib/types";
import { getScoreColor, getPartyColor, getPartyTextColor } from "@/lib/colors";
import { formatScore } from "@/lib/format";

/** Derive MP slug from entry name */
function entryToSlug(entry: LeaderboardEntry): string {
  return entry.mp_name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
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

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
  stateSlug?: string; // if provided, links go to /state/X/mp/Y; otherwise inferred from entry.state
  showState?: boolean;
  showPartyFilter?: boolean;
  initialLimit?: number;
}

const DIMENSION_COLS: { key: SortField; label: string; abbr: string }[] = [
  { key: "mplads_score", label: "MPLADS", abbr: "MPL" },
  { key: "criminal_score", label: "Criminal", abbr: "CRM" },
  { key: "attendance_score", label: "Attendance", abbr: "ATT" },
  { key: "participation_score", label: "Participation", abbr: "PRT" },
  { key: "asset_score", label: "Assets", abbr: "AST" },
  { key: "committee_score", label: "Committees", abbr: "CMT" },
  { key: "legislative_score", label: "Legislative", abbr: "LEG" },
  { key: "accessibility_score", label: "Accessibility", abbr: "ACC" },
];

export function LeaderboardTable({
  entries,
  stateSlug,
  showState = false,
  showPartyFilter = true,
  initialLimit = 50,
}: LeaderboardTableProps) {
  const [sortBy, setSortBy] = useState<SortField>("composite_score");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [partyFilter, setPartyFilter] = useState<string[]>([]);
  const [showAll, setShowAll] = useState(false);

  const parties = useMemo(
    () => [...new Set(entries.map((e) => e.party))].sort(),
    [entries]
  );

  const toggleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  const toggleParty = (party: string) => {
    setPartyFilter((prev) =>
      prev.includes(party) ? prev.filter((p) => p !== party) : [...prev, party]
    );
  };

  const sorted = useMemo(() => {
    let result = [...entries];
    if (partyFilter.length > 0) {
      result = result.filter((e) => partyFilter.includes(e.party));
    }
    result.sort((a, b) => {
      const aVal = a[sortBy];
      const bVal = b[sortBy];
      return sortDir === "desc"
        ? (bVal as number) - (aVal as number)
        : (aVal as number) - (bVal as number);
    });
    return result;
  }, [entries, partyFilter, sortBy, sortDir]);

  const displayed = showAll ? sorted : sorted.slice(0, initialLimit);
  const hasMore = sorted.length > initialLimit && !showAll;

  const SortHeader = ({
    field,
    label,
    abbr,
    className = "",
  }: {
    field: SortField;
    label: string;
    abbr: string;
    className?: string;
  }) => {
    const active = sortBy === field;
    return (
      <th
        onClick={() => toggleSort(field)}
        className={`px-2 py-2 text-xs font-bold uppercase tracking-wide cursor-pointer select-none hover:bg-highlight transition-colors ${
          active ? "bg-accent text-ink" : "text-text-muted"
        } ${className}`}
        title={`Sort by ${label}`}
      >
        <div className="flex items-center gap-1 justify-center">
          <span className="hidden lg:inline">{label}</span>
          <span className="lg:hidden">{abbr}</span>
          {active && (
            <span className="text-[10px]">
              {sortDir === "desc" ? "\u25BC" : "\u25B2"}
            </span>
          )}
        </div>
      </th>
    );
  };

  /** Mini score bar for table cells */
  const ScoreCell = ({ score, className = "" }: { score: number; className?: string }) => (
    <td className={`px-2 py-2 text-center ${className}`}>
      <div className="flex items-center gap-1">
        <div className="flex-1 h-1.5 bg-ink/10 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${score}%`,
              backgroundColor: getScoreColor(score),
            }}
          />
        </div>
        <span
          className="text-xs font-mono font-bold w-8 text-right"
          style={{ color: getScoreColor(score) }}
        >
          {Math.round(score)}
        </span>
      </div>
    </td>
  );

  return (
    <div className="space-y-4">
      {/* Party filter pills */}
      {showPartyFilter && parties.length > 1 && (
        <div className="flex flex-wrap gap-1">
          {parties.map((party) => (
            <button
              key={party}
              onClick={() => toggleParty(party)}
              className={`text-xs px-2 py-1 border-2 border-ink font-bold uppercase transition-colors ${
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
      )}

      {/* Results count */}
      <p className="text-sm text-text-muted">
        Showing {displayed.length} of {sorted.length} MPs
        {partyFilter.length > 0 && ` (filtered from ${entries.length})`}
      </p>

      {/* Table */}
      <div className="overflow-x-auto border-3 border-ink shadow-brutal">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-3 border-ink bg-surface">
              <th className="px-2 py-2 text-xs font-bold uppercase tracking-wide text-text-muted w-10 text-center">
                #
              </th>
              <th className="px-2 py-2 text-xs font-bold uppercase tracking-wide text-text-muted text-left min-w-[180px]">
                MP
              </th>
              {showState && (
                <th className="px-2 py-2 text-xs font-bold uppercase tracking-wide text-text-muted text-left hidden md:table-cell">
                  State
                </th>
              )}
              <SortHeader
                field="composite_score"
                label="Score"
                abbr="SCR"
                className="w-20"
              />
              {DIMENSION_COLS.map((col) => (
                <SortHeader
                  key={col.key}
                  field={col.key}
                  label={col.label}
                  abbr={col.abbr}
                  className="hidden sm:table-cell"
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {displayed.map((entry, i) => {
              const slug = entryToSlug(entry);
              const state =
                stateSlug || entry.state.replace(/\s+/g, "-").toLowerCase();
              const href = `/state/${state}/mp/${slug}`;
              const partyColor = getPartyColor(entry.party);
              const partyText = getPartyTextColor(entry.party);

              return (
                <tr
                  key={`${entry.mp_name}-${entry.constituency}`}
                  className="border-b border-ink/10 hover:bg-highlight transition-colors"
                >
                  {/* Rank */}
                  <td className="px-2 py-2 text-center font-mono font-bold text-text-muted">
                    {i + 1}
                  </td>

                  {/* MP info */}
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-2">
                      <Link href={href} className="flex-shrink-0">
                        {entry.photo_url ? (
                          <img
                            src={entry.photo_url}
                            alt=""
                            className="w-8 h-8 rounded-full border-2 border-ink object-cover"
                          />
                        ) : (
                          <div className="w-8 h-8 rounded-full border-2 border-ink bg-highlight flex items-center justify-center">
                            <span className="text-xs font-bold">
                              {entry.mp_name.charAt(0)}
                            </span>
                          </div>
                        )}
                      </Link>
                      <div className="min-w-0">
                        <Link
                          href={href}
                          className="font-bold text-ink hover:underline truncate block"
                        >
                          {entry.mp_name}
                        </Link>
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs text-text-muted truncate">
                            {entry.constituency}
                          </span>
                          <Link
                            href={`/party/${entry.party.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`}
                            className="text-[10px] font-bold px-1 py-0 border border-ink uppercase leading-tight hover:opacity-80 transition-opacity"
                            style={{
                              backgroundColor: partyColor,
                              color: partyText,
                            }}
                          >
                            {entry.party}
                          </Link>
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* State */}
                  {showState && (
                    <td className="px-2 py-2 text-xs text-text-muted capitalize hidden md:table-cell">
                      {entry.state}
                    </td>
                  )}

                  {/* Composite score */}
                  <td className="px-2 py-2 text-center">
                    <span
                      className="font-mono font-bold text-base"
                      style={{ color: getScoreColor(entry.composite_score) }}
                    >
                      {formatScore(entry.composite_score)}
                    </span>
                  </td>

                  {/* Dimension scores */}
                  {DIMENSION_COLS.map((col) => (
                    <ScoreCell
                      key={col.key}
                      score={entry[col.key] as number}
                      className="hidden sm:table-cell"
                    />
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Show more */}
      {hasMore && (
        <div className="text-center">
          <button
            onClick={() => setShowAll(true)}
            className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-6 py-2 font-bold uppercase text-ink text-sm"
          >
            Show All {sorted.length} MPs
          </button>
        </div>
      )}
    </div>
  );
}
