import { cn } from "@/lib/cn";

interface NoDataStateProps {
  title?: string;
  message?: string;
  className?: string;
}

export function NoDataState({
  title = "No Data Yet",
  message = "Run the transparency pipeline for this state to generate scores.",
  className,
}: NoDataStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 px-4 text-center border-3 border-dashed border-ink bg-surface",
        className
      )}
    >
      <div className="w-16 h-16 bg-highlight border-3 border-ink shadow-brutal flex items-center justify-center mb-4">
        <span className="text-2xl text-ink font-bold">?</span>
      </div>
      <h3 className="text-lg font-bold uppercase text-ink mb-2">{title}</h3>
      <p className="text-sm text-text-secondary max-w-md">{message}</p>
      <code className="mt-4 px-4 py-2 bg-ink text-background border-3 shadow-brutal text-xs font-mono">
        python -m tracker --state &lt;state-name&gt;
      </code>
    </div>
  );
}
