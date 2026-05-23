import Link from "next/link";
import { ScoreBadge } from "./ScoreBadge";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { getPartyColor, getPartyTextColor } from "@/lib/colors";
import { cn } from "@/lib/cn";
import { publicPath } from "@/lib/paths";
import type { LeaderboardEntry } from "@/lib/types";

interface MPCardProps {
  entry: LeaderboardEntry;
  stateSlug: string;
  mpSlug: string;
  className?: string;
}

export function MPCard({ entry, stateSlug, mpSlug, className }: MPCardProps) {
  const partyColor = getPartyColor(entry.party);
  const partyTextColor = getPartyTextColor(entry.party);

  return (
    <Link
      href={`/state/${stateSlug}/mp/${mpSlug}`}
      className={cn(
        "flex items-center gap-4 p-4 bg-surface border-3 border-ink shadow-brutal-sm brutal-press hover:bg-highlight",
        className
      )}
    >
      {/* Rank */}
      <div className="text-2xl font-bold font-mono text-text-muted w-10 text-center border-r-3 border-ink pr-3">
        {entry.rank}
      </div>

      {/* Score badge */}
      <ScoreBadge score={entry.composite_score} size="sm" />

      {/* Photo */}
      {entry.photo_url ? (
        <img
          src={publicPath(entry.photo_url)}
          alt={entry.mp_name}
          className="w-10 h-10 rounded-full border-2 border-ink object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-10 h-10 rounded-full border-2 border-ink bg-highlight flex items-center justify-center flex-shrink-0">
          <span className="text-sm font-bold text-ink">{entry.mp_name.charAt(0)}</span>
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-bold text-ink truncate">
            {entry.mp_name}
          </span>
          <span
            className="text-xs font-bold px-1.5 py-0.5 border-2 border-ink uppercase"
            style={{
              backgroundColor: partyColor,
              color: partyTextColor,
              boxShadow: "1px 1px 0 0 #000",
            }}
          >
            {entry.party}
          </span>
        </div>
        <div className="text-sm text-text-secondary truncate">
          {entry.constituency}
        </div>
      </div>

      {/* Confidence */}
      <ConfidenceBadge confidence={entry.data_confidence} />
    </Link>
  );
}
