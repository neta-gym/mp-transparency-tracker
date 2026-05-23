"use client";

import { useState } from "react";
import { GradeBadge } from "./GradeBadge";
import type { DataSource } from "@/lib/types";

interface SourceCitationProps {
  sources?: DataSource[];
}

export function SourceCitation({ sources }: SourceCitationProps) {
  const [showDetail, setShowDetail] = useState(false);

  if (!sources || sources.length === 0) return null;

  const primary = sources[0];

  return (
    <span className="relative inline-flex items-center gap-1">
      <button
        onClick={() => setShowDetail(!showDetail)}
        className="inline-flex items-center gap-1 text-xs border border-ink/40 bg-surface px-1.5 py-0.5 hover:bg-highlight cursor-pointer"
        title={`Source: ${primary.source_name} (Grade ${primary.grade})`}
      >
        <GradeBadge grade={primary.grade} />
        <span className="font-mono text-text-muted truncate max-w-[80px]">
          {primary.source_name}
        </span>
      </button>

      {showDetail && (
        <div className="absolute bottom-full left-0 z-50 mb-1 w-72 p-3 border-3 border-ink bg-background shadow-brutal text-xs">
          <h4 className="font-bold uppercase tracking-wide mb-2">Data Sources</h4>
          {sources.map((src, i) => (
            <div key={i} className="mb-2 last:mb-0 p-2 border border-ink/30 bg-surface">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold">{src.source_name}</span>
                <GradeBadge grade={src.grade} />
              </div>
              {src.notes && (
                <p className="text-text-muted">{src.notes}</p>
              )}
              {src.url && (
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline mt-1 block truncate"
                >
                  {src.url}
                </a>
              )}
              {src.fetched_at && (
                <p className="text-text-muted mt-1 font-mono">
                  Fetched: {new Date(src.fetched_at).toLocaleDateString("en-IN")}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </span>
  );
}
