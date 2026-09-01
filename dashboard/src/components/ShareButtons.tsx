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
  const [copied, setCopied] = useState(false);

  const text = `${mpName} (${party}, ${constituency}) scores ${score}/100 on public transparency records - MPLADS funds, attendance, criminal cases, assets. Every one of India's 540 MPs has a public report card:`;
  const xIntent = `https://x.com/intent/post?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked (permissions policy); leave the button state unchanged.
    }
  };

  return (
    <div className="no-print flex gap-2">
      <a
        href={xIntent}
        target="_blank"
        rel="noopener noreferrer"
        className="border-3 border-ink bg-ink text-surface shadow-brutal-sm brutal-press hover:bg-danger px-3 py-1.5 font-bold uppercase text-sm"
      >
        Share on X
      </a>
      <button
        onClick={copyLink}
        className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink text-sm"
      >
        {copied ? "Copied!" : "Copy link"}
      </button>
    </div>
  );
}
