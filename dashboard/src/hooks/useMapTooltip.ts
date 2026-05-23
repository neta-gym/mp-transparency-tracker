"use client";

import { useState, useCallback } from "react";

interface TooltipState {
  show: boolean;
  x: number;
  y: number;
  content: {
    title: string;
    score: number | null;
    subtitle?: string;
  } | null;
}

export function useMapTooltip() {
  const [tooltip, setTooltip] = useState<TooltipState>({
    show: false,
    x: 0,
    y: 0,
    content: null,
  });

  const showTooltip = useCallback(
    (
      event: React.MouseEvent,
      content: { title: string; score: number | null; subtitle?: string }
    ) => {
      setTooltip({
        show: true,
        x: event.clientX,
        y: event.clientY,
        content,
      });
    },
    []
  );

  const moveTooltip = useCallback((event: React.MouseEvent) => {
    setTooltip((prev) => ({
      ...prev,
      x: event.clientX,
      y: event.clientY,
    }));
  }, []);

  const hideTooltip = useCallback(() => {
    setTooltip({ show: false, x: 0, y: 0, content: null });
  }, []);

  return { tooltip, showTooltip, moveTooltip, hideTooltip };
}
