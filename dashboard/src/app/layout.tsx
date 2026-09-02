import type { Metadata } from "next";
import Link from "next/link";
import { SearchBarWrapper } from "@/components/SearchBarWrapper";
import "./globals.css";

const siteUrl = "https://neta-gym.github.io/mp-transparency-tracker";
const siteTitle = "MP Transparency Tracker";
const siteDescription =
  "Interactive dashboard tracking transparency scores of Indian Members of Parliament";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: siteTitle,
  description: siteDescription,
  openGraph: {
    title: siteTitle,
    description: siteDescription,
    type: "website",
    siteName: siteTitle,
    images: [
      {
        url: "/og-card.png",
        width: 1200,
        height: 630,
        alt: "MP Transparency Tracker - public report cards for India's 540 MPs",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteTitle,
    description: siteDescription,
  },
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
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 py-2 sm:h-14 sm:py-0 sm:flex-nowrap">
              <Link
                href="/"
                className="flex items-center gap-2 text-ink"
              >
                <span className="text-base sm:text-xl font-bold uppercase tracking-tight">
                  MP Transparency Tracker
                </span>
              </Link>
              <div className="flex items-center gap-2 sm:gap-4 text-xs sm:text-sm">
                <div className="hidden sm:block w-56">
                  <SearchBarWrapper />
                </div>
                <Link
                  href="/"
                  className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-2 py-1 sm:px-3 sm:py-1.5 font-bold uppercase text-ink"
                >
                  Dashboard
                </Link>
                <Link
                  href="/national"
                  className="border-3 border-ink bg-primary text-white shadow-brutal-sm brutal-press hover:bg-primary/90 px-2 py-1 sm:px-3 sm:py-1.5 font-bold uppercase"
                >
                  Leaderboard
                </Link>
                <Link
                  href="/compare"
                  className="border-3 border-ink bg-surface shadow-brutal-sm brutal-press hover:bg-highlight px-2 py-1 sm:px-3 sm:py-1.5 font-bold uppercase text-ink"
                >
                  Compare
                </Link>
                <span className="hidden sm:inline font-mono border-2 border-ink bg-accent px-2 py-0.5 text-xs font-bold">
                  v3.1
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
                Methodology v3.1 · MPLADS 20%, Assets 15%, Criminal 20%,
                Attendance 15%, Participation 10%, Committees 5%, Legislative
                10%, Accessibility 5%
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
