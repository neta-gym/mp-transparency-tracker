/** Server-side search utilities — uses Node.js fs via data.ts */

import { getAllStates, getLeaderboard, entryToSlug } from "./data";

// Re-export client-safe types and functions
export type { SearchResult } from "./search-client";
export { searchMPs } from "./search-client";
import type { SearchResult } from "./search-client";

/** Build a flat list of all MP entries across all state leaderboards (server-only) */
export function getAllMPEntries(): SearchResult[] {
  const states = getAllStates();
  const results: SearchResult[] = [];

  for (const state of states) {
    if (!state.hasData) continue;
    const lb = getLeaderboard(state.slug);
    if (!lb) continue;

    for (const entry of lb.entries) {
      results.push({
        mpName: entry.mp_name,
        constituency: entry.constituency,
        party: entry.party,
        state: state.displayName,
        stateSlug: state.slug,
        mpSlug: entryToSlug(entry),
        compositeScore: entry.composite_score,
        house: entry.house,
        dimensionScores: {
          mplads_score: entry.mplads_score,
          asset_score: entry.asset_score,
          criminal_score: entry.criminal_score,
          attendance_score: entry.attendance_score,
          participation_score: entry.participation_score,
          committee_score: entry.committee_score,
          accessibility_score: entry.accessibility_score,
          legislative_score: entry.legislative_score,
        },
      });
    }
  }

  return results;
}
