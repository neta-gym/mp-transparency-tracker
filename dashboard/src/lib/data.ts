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

/** Leaderboard entry → slug (derived from mp_name) */
export function entryToSlug(entry: LeaderboardEntry): string {
  return entry.mp_name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
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

  return {
    totalMPs: allEntries.length,
    statesProcessed: statesWithData.length,
    totalStates: states.length,
    avgScore:
      allEntries.length > 0
        ? Math.round(
            (allEntries.reduce((s, e) => s + e.composite_score, 0) /
              allEntries.length) *
              10
          ) / 10
        : 0,
    topMPs: allEntries.slice(0, 5),
    bottomMPs: allEntries.slice(-5).reverse(),
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

function dashboardRiskScore(entry: LeaderboardEntry): number {
  return Math.round(
    (100 - entry.composite_score) * 0.35 +
      (100 - entry.criminal_score) * 0.25 +
      (100 - entry.attendance_score) * 0.15 +
      (100 - entry.participation_score) * 0.15 +
      (100 - entry.committee_score) * 0.1
  );
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function displayStateFromSlug(slug: string): string {
  return slug
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Front-page dashboard aggregates for state, party, and criminal-risk charts. */
export function getHomeDashboardStats() {
  const stateStats = getAllStateSlugs()
    .map((stateSlug) => {
      const leaderboard = getLeaderboard(stateSlug);
      const entries = leaderboard?.entries ?? [];
      const criminalTotals = entries.reduce(
        (acc, entry) => {
          const validated = getValidatedFindings(stateSlug, entryToSlug(entry));
          const criminal = validated?.findings?.criminal_record;
          acc.totalCases += criminal?.total_cases ?? 0;
          acc.seriousCases += criminal?.serious_cases ?? 0;
          acc.pendingCases += criminal?.pending_cases ?? 0;
          acc.mpsWithCases += (criminal?.total_cases ?? 0) > 0 ? 1 : 0;
          return acc;
        },
        { totalCases: 0, seriousCases: 0, pendingCases: 0, mpsWithCases: 0 }
      );

      const avg = (selector: (entry: LeaderboardEntry) => number) =>
        entries.length > 0
          ? Math.round((entries.reduce((sum, entry) => sum + selector(entry), 0) / entries.length) * 10) / 10
          : 0;

      const avgScore = avg((entry) => entry.composite_score);
      const avgRisk = avg(dashboardRiskScore);

      return {
        stateSlug,
        state: leaderboard?.state ?? displayStateFromSlug(stateSlug),
        displayState: displayStateFromSlug(stateSlug),
        mpCount: entries.length,
        avgScore,
        corruptionIndex: Math.round((100 - avgScore) * 0.55 + avgRisk * 0.45),
        avgCriminalRisk: Math.round((100 - avg((entry) => entry.criminal_score)) * 10) / 10,
        avgAttendanceRisk: Math.round((100 - avg((entry) => entry.attendance_score)) * 10) / 10,
        totalCases: criminalTotals.totalCases,
        seriousCases: criminalTotals.seriousCases,
        pendingCases: criminalTotals.pendingCases,
        mpsWithCases: criminalTotals.mpsWithCases,
      };
    })
    .filter((state) => state.mpCount > 0);

  const allEntries = getAllEntries();
  const partyMap = new Map<
    string,
    {
      entries: LeaderboardEntry[];
      totalCases: number;
      seriousCases: number;
      mpsWithCases: number;
    }
  >();

  for (const entry of allEntries) {
    const party = partyMap.get(entry.party) ?? {
      entries: [],
      totalCases: 0,
      seriousCases: 0,
      mpsWithCases: 0,
    };
    const stateSlug = slugify(entry.state);
    const validated = getValidatedFindings(stateSlug, entryToSlug(entry));
    const criminal = validated?.findings?.criminal_record;
    party.entries.push(entry);
    party.totalCases += criminal?.total_cases ?? 0;
    party.seriousCases += criminal?.serious_cases ?? 0;
    party.mpsWithCases += (criminal?.total_cases ?? 0) > 0 ? 1 : 0;
    partyMap.set(entry.party, party);
  }

  const partyStats = Array.from(partyMap.entries())
    .map(([party, data]) => {
      const avg = (selector: (entry: LeaderboardEntry) => number) =>
        Math.round((data.entries.reduce((sum, entry) => sum + selector(entry), 0) / data.entries.length) * 10) / 10;
      const avgScore = avg((entry) => entry.composite_score);
      return {
        party,
        mpCount: data.entries.length,
        avgScore,
        corruptionIndex: Math.round((100 - avgScore) * 0.55 + avg(dashboardRiskScore) * 0.45),
        avgCriminalRisk: Math.round((100 - avg((entry) => entry.criminal_score)) * 10) / 10,
        avgAttendanceRisk: Math.round((100 - avg((entry) => entry.attendance_score)) * 10) / 10,
        avgParticipationRisk: Math.round((100 - avg((entry) => entry.participation_score)) * 10) / 10,
        avgCommitteeRisk: Math.round((100 - avg((entry) => entry.committee_score)) * 10) / 10,
        totalCases: data.totalCases,
        seriousCases: data.seriousCases,
        mpsWithCases: data.mpsWithCases,
        caseRate: Math.round((data.mpsWithCases / data.entries.length) * 100),
      };
    })
    .sort((a, b) => b.mpCount - a.mpCount);

  const criminalCaseLeaders = allEntries
    .map((entry) => {
      const stateSlug = slugify(entry.state);
      const validated = getValidatedFindings(stateSlug, entryToSlug(entry));
      const criminal = validated?.findings?.criminal_record;
      return {
        mpName: entry.mp_name,
        party: entry.party,
        constituency: entry.constituency,
        state: displayStateFromSlug(stateSlug),
        stateSlug,
        href: `/state/${stateSlug}/mp/${entryToSlug(entry)}`,
        totalCases: criminal?.total_cases ?? 0,
        seriousCases: criminal?.serious_cases ?? 0,
        pendingCases: criminal?.pending_cases ?? 0,
        risk: dashboardRiskScore(entry),
      };
    })
    .filter((entry) => entry.totalCases > 0)
    .sort((a, b) => b.totalCases - a.totalCases || b.seriousCases - a.seriousCases)
    .slice(0, 10);

  return {
    stateRisk: [...stateStats].sort((a, b) => b.corruptionIndex - a.corruptionIndex).slice(0, 12),
    stateCriminalCases: [...stateStats].sort((a, b) => b.totalCases - a.totalCases).slice(0, 12),
    partyStats: partyStats.filter((party) => party.mpCount >= 2).slice(0, 14),
    criminalCaseLeaders,
  };
}
