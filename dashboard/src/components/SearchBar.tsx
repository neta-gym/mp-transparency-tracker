"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import type { SearchResult } from "@/lib/search-client";
import { searchMPs } from "@/lib/search-client";
import { formatScore } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";
import { publicPath } from "@/lib/paths";

interface SearchBarProps {
  allEntries: SearchResult[];
  /** "hero" renders the large, primary-entry variant used on the home page. */
  variant?: "default" | "hero";
  placeholder?: string;
}

export function SearchBar({
  allEntries,
  variant = "default",
  placeholder = "Search MPs...",
}: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hero = variant === "hero";

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim().length >= 2) {
        const found = searchMPs(query, allEntries);
        setResults(found);
        setIsOpen(found.length > 0);
        setSelectedIndex(-1);
      } else {
        setResults([]);
        setIsOpen(false);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [query, allEntries]);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, -1));
      } else if (e.key === "Escape") {
        setIsOpen(false);
        inputRef.current?.blur();
      } else if (e.key === "Enter" && selectedIndex >= 0 && results[selectedIndex]) {
        // Let the Link navigation happen via click simulation
        const el = containerRef.current?.querySelectorAll("a")[selectedIndex];
        (el as HTMLElement | undefined)?.click();
      }
    },
    [results, selectedIndex]
  );

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setIsOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label="Search for an MP by name, constituency, or district"
        className={
          hero
            ? "w-full border-3 border-ink bg-surface px-4 py-4 text-lg font-bold focus:outline-none focus:bg-highlight placeholder:font-normal placeholder:text-text-muted shadow-brutal-sm"
            : "w-full border-3 border-ink bg-surface px-3 py-1.5 text-sm font-mono focus:outline-none focus:bg-highlight placeholder:text-text-muted"
        }
      />

      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 border-3 border-ink bg-background shadow-brutal max-h-96 overflow-y-auto">
          {results.map((result, i) => {
            const houseTag = result.house === "lok_sabha" ? "LS" : "RS";
            return (
              <Link
                key={`${result.stateSlug}-${result.mpSlug}`}
                href={`/state/${result.stateSlug}/mp/${result.mpSlug}`}
                onClick={() => {
                  setIsOpen(false);
                  setQuery("");
                }}
                className={`flex items-center gap-3 px-3 py-3 min-h-[64px] border-b border-ink/20 hover:bg-highlight transition-colors ${
                  i === selectedIndex ? "bg-highlight" : ""
                }`}
              >
                {result.photoUrl ? (
                  <img
                    src={publicPath(result.photoUrl)}
                    alt=""
                    className="h-11 w-11 shrink-0 rounded-full border-2 border-ink object-cover"
                  />
                ) : (
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-ink bg-highlight font-bold text-ink">
                    {result.mpName.charAt(0)}
                  </span>
                )}
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate font-bold text-sm text-ink">
                      {result.mpName}
                      <span className="text-xs text-text-muted ml-2 font-mono">
                        [{houseTag}]
                      </span>
                    </span>
                    <span
                      className="shrink-0 font-bold font-mono text-sm"
                      style={{ color: getScoreColor(result.compositeScore) }}
                    >
                      {formatScore(result.compositeScore)}
                    </span>
                  </span>
                  <span className="block truncate text-xs text-text-secondary mt-0.5">
                    {result.constituency}, {result.state} · {result.party}
                  </span>
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
