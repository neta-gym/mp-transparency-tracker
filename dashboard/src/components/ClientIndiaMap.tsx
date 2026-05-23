"use client";

import dynamic from "next/dynamic";
import type { StateManifest } from "@/lib/types";

const IndiaMap = dynamic(
  () => import("@/components/IndiaMap").then((m) => m.IndiaMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-[600px] text-text-muted border-3 border-dashed border-ink font-mono uppercase tracking-widest">
        Loading map...
      </div>
    ),
  }
);

export function ClientIndiaMap({ states }: { states: StateManifest[] }) {
  return <IndiaMap states={states} />;
}
