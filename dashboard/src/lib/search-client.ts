/** Client-safe search utilities — no Node.js dependencies */

export interface SearchResult {
  mpName: string;
  constituency: string;
  party: string;
  state: string;
  stateSlug: string;
  mpSlug: string;
  compositeScore: number;
  house: string;
  dimensionScores?: Record<string, number>;
}

/** Normalize a string for fuzzy matching */
function normalize(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

/** Check if query tokens match a target string (fuzzy token match) */
function fuzzyMatch(query: string, target: string): number {
  const normQ = normalize(query);
  const normT = normalize(target);

  // Exact substring match gets highest score
  if (normT.includes(normQ)) return 1.0;

  // Token-based matching
  const queryTokens = normQ.split(" ").filter(Boolean);
  const targetTokens = normT.split(" ").filter(Boolean);

  if (queryTokens.length === 0) return 0;

  let matched = 0;
  for (const qt of queryTokens) {
    for (const tt of targetTokens) {
      if (tt.startsWith(qt) || qt.startsWith(tt)) {
        matched++;
        break;
      }
    }
  }

  return matched / queryTokens.length;
}

/** Search MPs by name, constituency, or party with fuzzy matching */
export function searchMPs(
  query: string,
  allEntries: SearchResult[],
  limit = 10
): SearchResult[] {
  if (!query || query.trim().length < 2) return [];

  const scored: { entry: SearchResult; score: number }[] = [];

  for (const entry of allEntries) {
    const nameScore = fuzzyMatch(query, entry.mpName) * 1.0;
    const constScore = fuzzyMatch(query, entry.constituency) * 0.8;
    const partyScore = fuzzyMatch(query, entry.party) * 0.6;
    const stateScore = fuzzyMatch(query, entry.state) * 0.5;

    const bestScore = Math.max(nameScore, constScore, partyScore, stateScore);
    if (bestScore > 0.4) {
      scored.push({ entry, score: bestScore });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, limit).map((s) => s.entry);
}
