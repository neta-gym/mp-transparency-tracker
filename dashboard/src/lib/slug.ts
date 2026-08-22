import type { LeaderboardEntry } from "@/lib/types";

/** Leaderboard entry → URL slug (derived from mp_name) */
export function entryToSlug(entry: LeaderboardEntry): string {
  return entry.mp_name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Convert slug to display name (e.g. "andhra-pradesh" → "Andhra Pradesh") */
export function displayStateFromSlug(slug: string): string {
  return slug
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
