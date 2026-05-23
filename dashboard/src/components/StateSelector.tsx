"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { StateManifest } from "@/lib/types";
import { cn } from "@/lib/cn";

interface StateSelectorProps {
  states: StateManifest[];
  currentSlug?: string;
  className?: string;
}

export function StateSelector({
  states,
  currentSlug,
  className,
}: StateSelectorProps) {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = states.filter((s) =>
    s.displayName.toLowerCase().includes(search.toLowerCase())
  );

  const statesWithData = filtered.filter((s) => s.hasData);
  const statesWithoutData = filtered.filter((s) => !s.hasData);

  return (
    <div className={cn("relative", className)}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-2 px-4 py-2.5 bg-surface border-3 border-ink text-ink shadow-brutal-sm brutal-press hover:bg-highlight text-sm font-bold"
      >
        <span>
          {currentSlug
            ? states.find((s) => s.slug === currentSlug)?.displayName ??
              "Select State"
            : "Select State"}
        </span>
        <span className="font-mono">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-80 overflow-auto border-3 border-ink shadow-brutal-lg bg-surface">
          <div className="sticky top-0 bg-surface p-2 border-b-3 border-ink">
            <input
              type="text"
              placeholder="Search states..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-1.5 bg-background border-2 border-ink text-ink text-sm placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
              autoFocus
            />
          </div>

          {statesWithData.length > 0 && (
            <div>
              <div className="px-3 py-1.5 text-xs font-bold uppercase tracking-wider bg-accent border-b-2 border-ink">
                Available
              </div>
              {statesWithData.map((state) => (
                <button
                  key={state.slug}
                  onClick={() => {
                    router.push(`/state/${state.slug}`);
                    setOpen(false);
                    setSearch("");
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 text-sm hover:bg-highlight flex justify-between border-b border-ink/10",
                    state.slug === currentSlug
                      ? "text-primary bg-highlight/30 font-bold"
                      : "text-ink"
                  )}
                >
                  <span>{state.displayName}</span>
                  <span className="text-text-muted font-mono">
                    {state.mpCount} MPs · Avg {state.avgScore?.toFixed(1)}
                  </span>
                </button>
              ))}
            </div>
          )}

          {statesWithoutData.length > 0 && (
            <div>
              <div className="px-3 py-1.5 text-xs font-bold uppercase tracking-wider bg-accent border-b-2 border-ink border-t-2">
                Coming Soon
              </div>
              {statesWithoutData.map((state) => (
                <div
                  key={state.slug}
                  className="px-3 py-2 text-sm text-text-muted cursor-not-allowed border-b border-ink/10"
                >
                  {state.displayName}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
