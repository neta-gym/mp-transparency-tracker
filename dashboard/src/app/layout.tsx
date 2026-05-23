import type { Metadata } from "next";
import Link from "next/link";
import { SearchBarWrapper } from "@/components/SearchBarWrapper";
import "./globals.css";

export const metadata: Metadata = {
  title: "MP Transparency Tracker",
  description:
    "Interactive dashboard tracking transparency scores of Indian Members of Parliament",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-text-primary antialiased">
        {/* Navigation */}
        <nav className="sticky top-0 z-40 border-b-3 border-ink bg-background">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-14">
              <Link
                href="/"
                className="flex items-center gap-2 text-ink"
              >
                <span className="text-xl font-bold uppercase tracking-tight">
                  MP Transparency Tracker
                </span>
              </Link>
              <div className="flex items-center gap-4 text-sm">
                <div className="hidden sm:block w-56">
                  <SearchBarWrapper />
                </div>
                <Link
                  href="/"
                  className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink"
                >
                  Dashboard
                </Link>
                <Link
                  href="/national"
                  className="border-3 border-ink bg-primary text-white shadow-brutal-sm brutal-press hover:bg-primary/90 px-3 py-1.5 font-bold uppercase"
                >
                  Leaderboard
                </Link>
                <Link
                  href="/compare"
                  className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-3 py-1.5 font-bold uppercase text-ink"
                >
                  Compare
                </Link>
                <span className="font-mono border-2 border-ink bg-accent px-2 py-0.5 text-xs font-bold">
                  v3.0
                </span>
              </div>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>

        {/* Footer */}
        <footer className="border-t-3 border-ink bg-surface mt-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-text-muted">
              <p>
                MP Transparency Tracker — Data sourced from eSAKSHI, data.gov.in, MyNeta, PRS India, MPLADS, Sansad, CAG
              </p>
              <p className="font-mono">
                Methodology v3.0 · MPLADS 25%, Assets 15%, Criminal 15%,
                Attendance 10%, Participation 10%, Committees 10%, Legislative
                10%, Accessibility 5%
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
