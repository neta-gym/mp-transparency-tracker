import { getScoreColor } from "@/lib/colors";
import { cn } from "@/lib/cn";

interface ColorLegendProps {
  className?: string;
}

const BLOCKS = [
  { score: 10, label: "0" },
  { score: 30, label: "20" },
  { score: 50, label: "40" },
  { score: 70, label: "60" },
  { score: 90, label: "80" },
];

export function ColorLegend({ className }: ColorLegendProps) {
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex justify-between text-xs text-text-muted font-bold uppercase tracking-wide">
        <span>Critical</span>
        <span>Excellent</span>
      </div>
      <div className="flex border-2 border-ink overflow-hidden">
        {BLOCKS.map((b) => (
          <div
            key={b.score}
            className="flex-1 h-4"
            style={{ backgroundColor: getScoreColor(b.score) }}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-text-muted font-mono">
        <span>0</span>
        <span>20</span>
        <span>40</span>
        <span>60</span>
        <span>80</span>
        <span>100</span>
      </div>
    </div>
  );
}
