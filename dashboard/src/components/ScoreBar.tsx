import { getScoreColor } from "@/lib/colors";
import { formatScore } from "@/lib/format";
import { cn } from "@/lib/cn";

interface ScoreBarProps {
  label: string;
  score: number;
  weight: number;
  className?: string;
}

export function ScoreBar({ label, score, weight, className }: ScoreBarProps) {
  const color = getScoreColor(score);
  const weightPct = Math.round(weight * 100);

  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink font-bold uppercase tracking-wide">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-text-muted text-xs font-mono">{weightPct}% weight</span>
          <span className="font-bold font-mono" style={{ color }}>
            {formatScore(score)}
          </span>
        </div>
      </div>
      <div className="h-4 bg-background border-2 border-ink overflow-hidden">
        <div
          className="h-full"
          style={{
            width: `${Math.min(score, 100)}%`,
            backgroundColor: color,
          }}
        />
      </div>
    </div>
  );
}
