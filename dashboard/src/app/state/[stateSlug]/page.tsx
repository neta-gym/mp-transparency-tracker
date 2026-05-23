import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAllStates,
  getAllStateSlugs,
  getLeaderboard,
  entryToSlug,
} from "@/lib/data";
import { getStateBySlug } from "@/lib/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ColorLegend } from "@/components/ColorLegend";
import { LeaderboardTable } from "@/components/LeaderboardTable";
import { StateSelector } from "@/components/StateSelector";
import { ClientStateMap } from "@/components/ClientStateMap";
import { NoDataState } from "@/components/NoDataState";
import { formatScore } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";

export function generateStaticParams() {
  // Generate pages for states with data + also generate for all states (show no-data message)
  return getAllStateSlugs().map((stateSlug) => ({ stateSlug }));
}

interface PageProps {
  params: Promise<{ stateSlug: string }>;
}

export default async function StatePage({ params }: PageProps) {
  const { stateSlug } = await params;
  const stateInfo = getStateBySlug(stateSlug);

  if (!stateInfo) {
    notFound();
  }

  const leaderboard = getLeaderboard(stateSlug);
  const allStates = getAllStates();

  if (!leaderboard || leaderboard.entries.length === 0) {
    return (
      <div>
        <div className="flex items-center gap-4 mb-6">
          <Link
            href="/"
            className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
          >
            BACK
          </Link>
          <h1 className="text-3xl font-bold uppercase">{stateInfo.displayName}</h1>
        </div>
        <NoDataState />
      </div>
    );
  }

  const entries = leaderboard.entries;
  const avgScore =
    entries.reduce((sum, e) => sum + e.composite_score, 0) / entries.length;
  const highestScore = Math.max(...entries.map((e) => e.composite_score));
  const lowestScore = Math.min(...entries.map((e) => e.composite_score));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
          >
            BACK
          </Link>
          <div>
            <h1 className="text-3xl font-bold uppercase">{stateInfo.displayName}</h1>
            <p className="text-text-secondary text-sm">
              {entries.length} MPs · Average Score{" "}
              <span className="font-mono font-bold" style={{ color: getScoreColor(avgScore) }}>
                {formatScore(avgScore)}
              </span>
            </p>
          </div>
        </div>
        <StateSelector
          states={allStates}
          currentSlug={stateSlug}
          className="w-64"
        />
      </div>

      {/* Stats + Map row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="text-center p-3 border-3 border-ink shadow-brutal bg-surface">
          <div className="text-2xl font-bold font-mono text-ink">
            {entries.length}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">
            MPs Scored
          </div>
        </div>
        <div
          className="text-center p-3 border-3 border-ink shadow-brutal bg-surface"
        >
          <div
            className="text-2xl font-bold font-mono"
            style={{ color: getScoreColor(highestScore) }}
          >
            {formatScore(highestScore)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">
            Highest
          </div>
        </div>
        <div className="text-center p-3 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-2xl font-bold font-mono"
            style={{ color: getScoreColor(avgScore) }}
          >
            {formatScore(avgScore)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">
            Average
          </div>
        </div>
        <div className="text-center p-3 border-3 border-ink shadow-brutal bg-surface">
          <div
            className="text-2xl font-bold font-mono"
            style={{ color: getScoreColor(lowestScore) }}
          >
            {formatScore(lowestScore)}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">
            Lowest
          </div>
        </div>
      </div>

      {/* Map (collapsible on smaller screens) */}
      <details className="group" open>
        <summary className="cursor-pointer border-3 border-ink bg-surface shadow-brutal-sm px-4 py-2 font-bold uppercase text-sm text-ink hover:bg-highlight transition-colors select-none">
          Constituency Map
          <span className="ml-2 text-text-muted group-open:rotate-90 inline-block transition-transform">
            &#9654;
          </span>
        </summary>
        <div className="border-3 border-t-0 border-ink bg-surface p-4">
          <ClientStateMap stateSlug={stateSlug} entries={entries} />
          <ColorLegend className="mt-4 max-w-sm mx-auto" />
        </div>
      </details>

      {/* Full-width Leaderboard Table */}
      <Card>
        <CardHeader>
          <CardTitle>MP Rankings</CardTitle>
        </CardHeader>
        <CardContent>
          <LeaderboardTable
            entries={entries}
            stateSlug={stateSlug}
            showState={false}
            showPartyFilter={true}
            initialLimit={50}
          />
        </CardContent>
      </Card>
    </div>
  );
}
