"use client";

import dynamic from "next/dynamic";
import type { LeaderboardEntry } from "@/lib/types";

const StateMap = dynamic(
  () => import("@/components/StateMap").then((m) => m.StateMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-[500px] text-text-muted border-3 border-dashed border-ink font-mono uppercase tracking-widest">
        Loading constituency map...
      </div>
    ),
  }
);

export function ClientStateMap({
  stateSlug,
  entries,
}: {
  stateSlug: string;
  entries: LeaderboardEntry[];
}) {
  return <StateMap stateSlug={stateSlug} entries={entries} />;
}
