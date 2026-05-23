import { getConfidenceColor, getConfidenceLevel } from "@/lib/colors";
import { formatConfidence } from "@/lib/format";
import { cn } from "@/lib/cn";

interface ConfidenceBadgeProps {
  confidence: number;
  className?: string;
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const level = getConfidenceLevel(confidence);
  const color = getConfidenceColor(confidence);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold border-2 border-ink",
        className
      )}
      style={{
        backgroundColor: color,
        color: "#FFFFFF",
      }}
    >
      <span
        className="w-2 h-2 border border-white"
        style={{ backgroundColor: "#FFFFFF" }}
      />
      {level} ({formatConfidence(confidence)})
    </span>
  );
}
