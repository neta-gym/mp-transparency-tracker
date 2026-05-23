"use client";

import dynamic from "next/dynamic";
import type { ScoreBreakdown } from "@/lib/types";

const ScoreRadar = dynamic(
  () => import("@/components/ScoreRadar").then((m) => m.ScoreRadar),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-[320px] text-text-muted border-3 border-dashed border-ink font-mono uppercase tracking-widest">
        Loading chart...
      </div>
    ),
  }
);

export function ClientScoreRadar({
  breakdown,
  compositeScore,
}: {
  breakdown: ScoreBreakdown;
  compositeScore: number;
}) {
  return <ScoreRadar breakdown={breakdown} compositeScore={compositeScore} />;
}
