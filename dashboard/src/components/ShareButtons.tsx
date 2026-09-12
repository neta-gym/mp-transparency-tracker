"use client";

import { useState } from "react";

interface ShareButtonsProps {
  mpName: string;
  party: string;
  constituency: string;
  score: number;
  /** Absolute URL of this MP's report card page. */
  url: string;
}

export function ShareButtons({ mpName, party, constituency, score, url }: ShareButtonsProps) {
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedSummary, setCopiedSummary] = useState(false);

  const summary = `${mpName} (${party}, ${constituency}) scores ${score}/100 on public transparency records - MPLADS funds, attendance, criminal cases, assets. See the full report card:`;
  const xIntent = `https://x.com/intent/post?text=${encodeURIComponent(summary)}&url=${encodeURIComponent(url)}`;
  const waIntent = `https://wa.me/?text=${encodeURIComponent(`${summary} ${url}`)}`;

  const copy = async (text: string, mark: (v: boolean) => void) => {
    try {
      await navigator.clipboard.writeText(text);
      mark(true);
      setTimeout(() => mark(false), 2000);
    } catch {
      // Clipboard blocked (permissions policy); leave the button state unchanged.
    }
  };

  return (
    <div className="no-print flex flex-wrap gap-2">
      <a
        href={waIntent}
        target="_blank"
        rel="noopener noreferrer"
        className="border-3 border-ink bg-success text-white shadow-brutal-sm brutal-press hover:brightness-90 px-3 py-1.5 font-bold uppercase text-sm"
      >
        WhatsApp
      </a>
      <a
        href={xIntent}
        target="_blank"
        rel="noopener noreferrer"
        className="border-3 border-ink bg-ink text-surface shadow-brutal-sm brutal-press hover:bg-danger px-3 py-1.5 font-bold uppercase text-sm"
      >
        Share on X
      </a>
      <button
        onClick={() => copy(`${summary} ${url}`, setCopiedSummary)}
        className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
      >
        {copiedSummary ? "Copied!" : "Copy summary"}
      </button>
      <button
        onClick={() => copy(url, setCopiedLink)}
        className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
      >
        {copiedLink ? "Copied!" : "Copy link"}
      </button>
    </div>
  );
}
