"use client";

import { getScoreColor } from "@/lib/colors";
import { formatScore } from "@/lib/format";

interface MapTooltipProps {
  show: boolean;
  x: number;
  y: number;
  content: {
    title: string;
    score: number | null;
    subtitle?: string;
  } | null;
}

export function MapTooltip({ show, x, y, content }: MapTooltipProps) {
  if (!show || !content) return null;

  return (
    <div
      className="fixed z-[100] pointer-events-none px-3 py-2 bg-surface border-3 border-ink shadow-brutal text-sm"
      style={{
        left: x + 12,
        top: y - 12,
      }}
    >
      <div className="font-bold text-ink">{content.title}</div>
      {content.score != null ? (
        <div className="flex items-center gap-2 mt-1">
          <div
            className="w-3 h-3 border border-ink"
            style={{ backgroundColor: getScoreColor(content.score) }}
          />
          <span className="text-text-secondary font-mono">
            Score: {formatScore(content.score)}
          </span>
        </div>
      ) : (
        <div className="text-text-muted">No data</div>
      )}
      {content.subtitle && (
        <div className="text-text-muted text-xs mt-0.5">{content.subtitle}</div>
      )}
    </div>
  );
}
