import { getGradeColor } from "@/lib/colors";
import { cn } from "@/lib/cn";

interface GradeBadgeProps {
  grade: string;
  className?: string;
}

const GRADE_LABELS: Record<string, string> = {
  A: "Govt API",
  B: "Official Scrape",
  C: "News/Media",
  D: "Indirect",
  E: "LLM Knowledge",
};

export function GradeBadge({ grade, className }: GradeBadgeProps) {
  const color = getGradeColor(grade);
  const label = GRADE_LABELS[grade.toUpperCase()] ?? "Unknown";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-bold uppercase border-2 border-ink shadow-brutal-sm text-white",
        className
      )}
      style={{ backgroundColor: color }}
    >
      {grade.toUpperCase()}
      <span className="opacity-80">| {label}</span>
    </span>
  );
}
