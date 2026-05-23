import fs from "fs";
import path from "path";
import type { Leaderboard } from "./types";

const DATA_DIR = path.join(process.cwd(), "..", "data");

export interface ScoreSnapshot {
  date: string;
  score: number;
  mplads: number;
  assets: number;
  criminal: number;
  attendance: number;
  participation: number;
}

/** Read all timestamped leaderboard snapshots and extract score history for an MP */
export function getMPScoreHistory(
  stateSlug: string,
  mpName: string
): ScoreSnapshot[] {
  const lbDir = path.join(DATA_DIR, stateSlug, "leaderboard");

  try {
    const files = fs
      .readdirSync(lbDir)
      .filter((f) => f.match(/^\d{8}_\d{6}\.json$/))
      .sort();

    const snapshots: ScoreSnapshot[] = [];

    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(lbDir, file), "utf-8");
        const lb: Leaderboard = JSON.parse(content);

        // Find the MP in this snapshot
        const entry = lb.entries.find(
          (e) => e.mp_name.toLowerCase() === mpName.toLowerCase()
        );

        if (entry) {
          // Extract date from filename (YYYYMMDD_HHMMSS.json)
          const dateStr = file.replace(".json", "");
          const year = dateStr.slice(0, 4);
          const month = dateStr.slice(4, 6);
          const day = dateStr.slice(6, 8);

          snapshots.push({
            date: `${year}-${month}-${day}`,
            score: entry.composite_score,
            mplads: entry.mplads_score,
            assets: entry.asset_score,
            criminal: entry.criminal_score,
            attendance: entry.attendance_score,
            participation: entry.participation_score,
          });
        }
      } catch {
        // Skip malformed snapshot files
      }
    }

    return snapshots;
  } catch {
    return [];
  }
}

/** Check if historical data exists for a state */
export function hasHistoricalData(stateSlug: string): boolean {
  const lbDir = path.join(DATA_DIR, stateSlug, "leaderboard");
  try {
    const files = fs
      .readdirSync(lbDir)
      .filter((f) => f.match(/^\d{8}_\d{6}\.json$/));
    return files.length >= 2; // Need at least 2 snapshots for a trend
  } catch {
    return false;
  }
}
