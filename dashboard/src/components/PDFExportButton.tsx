"use client";

import { MP_EXPAND_EVENT } from "./MPDetailSections";

export function PDFExportButton() {
  const handlePrint = () => {
    // Expand every collapsed detail section before printing so the exported
    // PDF contains the full findings, not just the header and score bars.
    window.dispatchEvent(new Event(MP_EXPAND_EVENT));
    setTimeout(() => window.print(), 100);
  };

  return (
    <button
      onClick={handlePrint}
      className="no-print border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
    >
      Download PDF
    </button>
  );
}
