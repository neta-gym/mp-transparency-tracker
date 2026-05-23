import { cn } from "@/lib/cn";
import { type HTMLAttributes } from "react";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "outline";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 text-xs border-2 border-ink font-bold uppercase tracking-wide",
        variant === "default" &&
          "bg-highlight text-ink shadow-brutal-sm",
        variant === "outline" &&
          "bg-surface text-ink",
        className
      )}
      {...props}
    />
  );
}
