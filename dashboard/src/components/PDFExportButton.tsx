"use client";

export function PDFExportButton() {
  return (
    <button
      onClick={() => window.print()}
      className="no-print border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
    >
      Download PDF
    </button>
  );
}
