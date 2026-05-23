"use client";

import { cn } from "@/lib/cn";
import { useState, type ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Tooltip({ content, children, className }: TooltipProps) {
  const [show, setShow] = useState(false);

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <div
          className={cn(
            "absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-sm",
            "bg-surface border-3 border-ink text-ink shadow-brutal",
            "whitespace-nowrap pointer-events-none",
            className
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}
