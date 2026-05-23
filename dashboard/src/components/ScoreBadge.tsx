import { getScoreColor, getScoreLabel } from "@/lib/colors";
import { formatScore } from "@/lib/format";
import { cn } from "@/lib/cn";

interface ScoreBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

export function ScoreBadge({
  score,
  size = "md",
  showLabel = false,
  className,
}: ScoreBadgeProps) {
  const color = getScoreColor(score);
  const label = getScoreLabel(score);

  const sizeClasses = {
    sm: "w-8 h-8 text-xs",
    md: "w-12 h-12 text-sm",
    lg: "w-16 h-16 text-lg",
  };

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn(
          "flex items-center justify-center font-bold font-mono border-3 border-ink shadow-brutal-sm",
          score < 25 ? "text-white" : "text-ink",
          sizeClasses[size]
        )}
        style={{ backgroundColor: color }}
      >
        {formatScore(score)}
      </div>
      {showLabel && (
        <span className="text-sm text-text-secondary font-bold uppercase">{label}</span>
      )}
    </div>
  );
}
