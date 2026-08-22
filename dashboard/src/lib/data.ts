import fs from "fs";
import path from "path";
import type {
  Leaderboard,
  LeaderboardEntry,
  ScoreResult,
  StateManifest,
  ValidatedFindings,
} from "./types";
import { STATES } from "./states";
import { entryToSlug, displayStateFromSlug } from "./slug";

// Path to the backend data directory (relative to dashboard root)
const DATA_DIR = path.join(process.cwd(), "..", "data");

function readJSON<T>(filePath: string): T | null {
  try {
    const content = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(content) as T;
  } catch {
    return null;
  }
}

/** Get the leaderboard for a state */
export function getLeaderboard(stateSlug: string): Leaderboard | null {
  const filePath = path.join(DATA_DIR, stateSlug, "leaderboard", "latest.json");
  return readJSON<Leaderboard>(filePath);
}

/** Get score result for one MP */
export function getScoreResult(
  stateSlug: string,
  mpSlug: string
): ScoreResult | null {
  const filePath = path.join(DATA_DIR, stateSlug, "scores", `${mpSlug}.json`);
  return readJSON<ScoreResult>(filePath);
}

/** Get validated findings for one MP */
export function getValidatedFindings(
  stateSlug: string,
  mpSlug: string
): ValidatedFindings | null {
  const filePath = path.join(
    DATA_DIR,
    stateSlug,
    "raw",
    `${mpSlug}_validated.json`
  );
  return readJSON<ValidatedFindings>(filePath);
}

/** Build manifest of all states with data availability info */
export function getAllStates(): StateManifest[] {
  return STATES.map((state) => {
    const leaderboard = getLeaderboard(state.slug);
    const hasData = leaderboard !== null && leaderboard.entries.length > 0;
    const avgScore = hasData
      ? leaderboard.entries.reduce((sum, e) => sum + e.composite_score, 0) /
        leaderboard.entries.length
      : null;

    return {
      slug: state.slug,
      displayName: state.displayName,
      hasData,
      mpCount: leaderboard?.total_mps ?? 0,
      avgScore: avgScore !== null ? Math.round(avgScore * 10) / 10 : null,
    };
  });
}

/** Get all state slugs that have data (for generateStaticParams) */
export function getAllStateSlugs(): string[] {
  return STATES.map((s) => s.slug).filter((slug) => {
    const lb = getLeaderboard(slug);
    return lb !== null && lb.entries.length > 0;
  });
}

/** Get all MP slugs for a state (for generateStaticParams) */
export function getAllMPSlugs(stateSlug: string): string[] {
  const scoreDir = path.join(DATA_DIR, stateSlug, "scores");
  try {
    return fs
      .readdirSync(scoreDir)
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(".json", ""));
  } catch {
    return [];
  }
}



/** Get national stats from all available leaderboards */
export function getNationalStats() {
  const states = getAllStates();
  const statesWithData = states.filter((s) => s.hasData);
  const allEntries: LeaderboardEntry[] = [];

  for (const state of statesWithData) {
    const lb = getLeaderboard(state.slug);
    if (lb) allEntries.push(...lb.entries);
  }

  allEntries.sort((a, b) => b.composite_score - a.composite_score);

  const total = allEntries.length;
  const avg = (fn: (e: LeaderboardEntry) => number) =>
    total > 0
      ? Math.round((allEntries.reduce((s, e) => s + fn(e), 0) / total) * 10) / 10
      : 0;

  const avgScore = avg((e) => e.composite_score);

  // Score distribution
  const distribution = {
    critical: allEntries.filter((e) => e.composite_score < 20).length,
    poor: allEntries.filter((e) => e.composite_score >= 20 && e.composite_score < 40).length,
    average: allEntries.filter((e) => e.composite_score >= 40 && e.composite_score < 60).length,
    good: allEntries.filter((e) => e.composite_score >= 60 && e.composite_score < 80).length,
    excellent: allEntries.filter((e) => e.composite_score >= 80).length,
  };

  // Systemic red flags
  const mpsWithLowAttendance = allEntries.filter((e) => e.attendance_score < 50).length;
  const mpsWithLowParticipation = allEntries.filter((e) => e.participation_score < 30).length;
  const mpsWithCriminalFlags = allEntries.filter((e) => e.criminal_score < 70).length;
  const mpsWithNoCommittee = allEntries.filter((e) => e.committee_score === 0).length;
  const mpsWithLowMplads = allEntries.filter((e) => e.mplads_score < 30).length;
  const mpsWithInaccessible = allEntries.filter((e) => e.accessibility_score <= 10).length;

  // Dimension averages
  const dimensions = {
    mplads: avg((e) => e.mplads_score),
    assets: avg((e) => e.asset_score),
    criminal: avg((e) => e.criminal_score),
    attendance: avg((e) => e.attendance_score),
    participation: avg((e) => e.participation_score),
    committee: avg((e) => e.committee_score),
    accessibility: avg((e) => e.accessibility_score),
    legislative: avg((e) => e.legislative_score),
  };

  // Party averages (for parties with 2+ MPs)
  const partyMap = new Map<string, { total: number; count: number }>();
  for (const e of allEntries) {
    const existing = partyMap.get(e.party) ?? { total: 0, count: 0 };
    existing.total += e.composite_score;
    existing.count += 1;
    partyMap.set(e.party, existing);
  }
  const partyAverages = Array.from(partyMap.entries())
    .filter(([, d]) => d.count >= 2)
    .map(([name, d]) => ({ name, avgScore: Math.round((d.total / d.count) * 10) / 10, mpCount: d.count }))
    .sort((a, b) => b.avgScore - a.avgScore);

  // State averages
  const stateEntries = statesWithData
    .map((s) => {
      const lb = getLeaderboard(s.slug);
      const entries = lb?.entries ?? [];
      if (entries.length === 0) return null;
      const stateAvg = entries.reduce((sum, e) => sum + e.composite_score, 0) / entries.length;
      return { slug: s.slug, displayName: s.displayName, avgScore: Math.round(stateAvg * 10) / 10, mpCount: entries.length };
    })
    .filter(Boolean) as { slug: string; displayName: string; avgScore: number; mpCount: number }[];

  stateEntries.sort((a, b) => b.avgScore - a.avgScore);

  return {
    totalMPs: total,
    statesProcessed: statesWithData.length,
    totalStates: states.length,
    avgScore,
    topMPs: allEntries.slice(0, 5),
    bottomMPs: allEntries.slice(-5).reverse(),
    distribution,
    mpsWithLowAttendance,
    mpsWithLowParticipation,
    mpsWithCriminalFlags,
    mpsWithNoCommittee,
    mpsWithLowMplads,
    mpsWithInaccessible,
    dimensions,
    partyAverages,
    bestStates: stateEntries.slice(0, 3),
    worstStates: stateEntries.slice(-3).reverse(),
  };
}

/** Get ALL MP entries across all states (for national leaderboard) */
export function getAllEntries(): LeaderboardEntry[] {
  const states = getAllStates();
  const allEntries: LeaderboardEntry[] = [];

  for (const state of states.filter((s) => s.hasData)) {
    const lb = getLeaderboard(state.slug);
    if (lb) allEntries.push(...lb.entries);
  }

  // Re-rank by composite score
  allEntries.sort((a, b) => b.composite_score - a.composite_score);
  allEntries.forEach((e, i) => (e.rank = i + 1));

  return allEntries;
}

/** Get party-level aggregation across all states */
export function getPartyStats() {
  const allEntries = getAllEntries();
  const partyMap = new Map<
    string,
    { entries: LeaderboardEntry[]; totalScore: number }
  >();

  for (const e of allEntries) {
    if (!partyMap.has(e.party)) {
      partyMap.set(e.party, { entries: [], totalScore: 0 });
    }
    const party = partyMap.get(e.party)!;
    party.entries.push(e);
    party.totalScore += e.composite_score;
  }

  return Array.from(partyMap.entries())
    .map(([name, data]) => ({
      name,
      mpCount: data.entries.length,
      avgScore:
        Math.round((data.totalScore / data.entries.length) * 10) / 10,
      entries: data.entries,
      avgMplads:
        Math.round(
          (data.entries.reduce((s, e) => s + e.mplads_score, 0) /
            data.entries.length) *
            10
        ) / 10,
      avgCriminal:
        Math.round(
          (data.entries.reduce((s, e) => s + e.criminal_score, 0) /
            data.entries.length) *
            10
        ) / 10,
      avgAttendance:
        Math.round(
          (data.entries.reduce((s, e) => s + e.attendance_score, 0) /
            data.entries.length) *
            10
        ) / 10,
    }))
    .sort((a, b) => b.mpCount - a.mpCount);
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
