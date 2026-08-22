import { formatScore, formatPercent } from "@/lib/format";
import { getScoreColor } from "@/lib/colors";
import type { ScoreResult, ValidatedFindings } from "@/lib/types";
import { cn } from "@/lib/cn";

type StatusLevel = "exemplary" | "performing" | "average" | "underperforming" | "failing" | "red-flag";

interface StatusInfo {
  level: StatusLevel;
  label: string;
  tagline: string;
  accent: string;
  badgeBg: string;
  badgeText: string;
}

function getStatus(score: number, validated: ValidatedFindings | null): StatusInfo {
  const cr = validated?.findings?.criminal_record;
  const hasSerious = (cr?.serious_cases ?? 0) > 0;
  const hasConvictions = (cr?.convictions ?? 0) > 0;

  if (hasConvictions) {
    return {
      level: "red-flag",
      label: "Red Flag",
      tagline: "Convicted — serious accountability concerns",
      accent: "border-l-danger",
      badgeBg: "bg-danger",
      badgeText: "text-white",
    };
  }

  if (hasSerious && score < 50) {
    return {
      level: "red-flag",
      label: "Red Flag",
      tagline: "Serious criminal cases + poor performance",
      accent: "border-l-danger",
      badgeBg: "bg-danger",
      badgeText: "text-white",
    };
  }

  if (score >= 80) {
    return {
      level: "exemplary",
      label: "Exemplary",
      tagline: "Top-tier accountability — a rare find",
      accent: "border-l-emerald-600",
      badgeBg: "bg-emerald-600",
      badgeText: "text-white",
    };
  }

  if (score >= 60) {
    return {
      level: "performing",
      label: "Performing",
      tagline: "Meets basic standards — room to improve",
      accent: "border-l-success",
      badgeBg: "bg-success",
      badgeText: "text-white",
    };
  }

  if (score >= 40) {
    return {
      level: "average",
      label: "Average",
      tagline: "Below expectations — not delivering enough",
      accent: "border-l-warning",
      badgeBg: "bg-warning",
      badgeText: "text-ink",
    };
  }

  if (score >= 20) {
    return {
      level: "underperforming",
      label: "Underperforming",
      tagline: "Failing on multiple fronts — needs scrutiny",
      accent: "border-l-orange-600",
      badgeBg: "bg-orange-600",
      badgeText: "text-white",
    };
  }

  return {
    level: "failing",
    label: "Failing",
    tagline: "Critical failure across dimensions — accountability demanded",
    accent: "border-l-danger",
    badgeBg: "bg-danger",
    badgeText: "text-white",
  };
}

function getStrengths(score: ScoreResult, validated: ValidatedFindings | null): string[] {
  const strengths: string[] = [];
  const b = score.breakdown;

  if (b.attendance_score >= 80) strengths.push("High Parliament attendance");
  if (b.mplads_score >= 70) strengths.push("Strong MPLADS fund utilization");
  if (b.participation_score >= 70) strengths.push("Active in debates and questions");
  if (b.criminal_score >= 90) strengths.push("Clean criminal record");
  if (b.committee_score >= 60) strengths.push("Meaningful committee engagement");
  if (b.legislative_score >= 60) strengths.push("Active legislative participation");
  if (b.asset_score >= 70) strengths.push("Transparent asset declarations");

  const pa = validated?.findings?.parliament_activity;
  if (pa?.is_minister) strengths.push("Serving as Minister");

  return strengths.slice(0, 3);
}

function getConcerns(score: ScoreResult, validated: ValidatedFindings | null): string[] {
  const concerns: string[] = [];
  const b = score.breakdown;

  if (b.criminal_score < 70) {
    const cr = validated?.findings?.criminal_record;
    if (cr && cr.total_cases > 0) {
      concerns.push(`${cr.total_cases} criminal case${cr.total_cases > 1 ? "s" : ""} on record`);
    }
  }
  if (b.attendance_score < 50) concerns.push("Poor Parliament attendance");
  if (b.mplads_score < 40) concerns.push("Constituency funds not utilized");
  if (b.participation_score < 30) concerns.push("Rarely speaks or asks questions");
  if (b.committee_score === 0) concerns.push("No committee participation at all");
  if (b.accessibility_score < 30) concerns.push("Inaccessible to the public");

  const assets = validated?.findings?.assets;
  if (assets?.growth_ratio != null && assets.growth_ratio > 1) {
    concerns.push("Significant asset growth between elections");
  }

  return concerns.slice(0, 3);
}

function getStatusDescription(score: ScoreResult, validated: ValidatedFindings | null): string {
  const b = score.breakdown;
  const parts: string[] = [];

  const attPct = validated?.findings?.parliament_activity?.attendance_percentage;
  if (attPct != null) {
    parts.push(`attended ${formatPercent(attPct)} of sessions`);
  }

  const cr = validated?.findings?.criminal_record;
  if (cr && cr.total_cases > 0) {
    parts.push(`${cr.total_cases} criminal case${cr.total_cases > 1 ? "s" : ""}${cr.pending_cases > 0 ? ` (${cr.pending_cases} pending)` : ""}`);
  }

  if (b.mplads_score < 40) {
    parts.push("MPLADS funds poorly utilized");
  } else if (b.mplads_score >= 70) {
    parts.push("MPLADS funds well utilized");
  }

  if (b.committee_score === 0) {
    parts.push("zero committee work");
  }

  if (b.participation_score < 30) {
    parts.push("rarely participates in Parliament");
  }

  if (parts.length === 0) {
    return `Scored ${formatScore(score.composite_score)} across 8 accountability dimensions.`;
  }

  return parts.join(" · ");
}

interface MPStatusSummaryProps {
  score: ScoreResult;
  validated: ValidatedFindings | null;
}

export function MPStatusSummary({ score, validated }: MPStatusSummaryProps) {
  const status = getStatus(score.composite_score, validated);
  const strengths = getStrengths(score, validated);
  const concerns = getConcerns(score, validated);
  const description = getStatusDescription(score, validated);
  const scoreColor = getScoreColor(score.composite_score);

  return (
    <div className={cn(
      "border-2 border-ink border-l-[5px] bg-surface shadow-brutal p-5",
      status.accent
    )}>
      <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
        {/* Status Badge */}
        <div className={cn(
          "px-4 py-2 border-2 border-ink shadow-brutal-sm",
          status.badgeBg,
          status.badgeText
        )}>
          <div className="text-[10px] font-black uppercase tracking-[0.15em] opacity-80">Status</div>
          <div className="text-xl font-black uppercase">{status.label}</div>
        </div>

        {/* Main Info */}
        <div className="flex-1">
          <p className="text-sm font-bold text-ink">
            {status.tagline}
          </p>
          <p className="text-xs mt-1 text-text-secondary">
            {description}
          </p>
        </div>

        {/* Score */}
        <div className="text-right">
          <div
            className="font-mono text-4xl font-black"
            style={{ color: scoreColor }}
          >
            {score.composite_score.toFixed(1)}
          </div>
          <div className="text-[10px] font-black uppercase text-text-muted">/ 100</div>
        </div>
      </div>

      {/* Strengths + Concerns */}
      {(strengths.length > 0 || concerns.length > 0) && (
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {strengths.length > 0 && (
            <div className="border-2 border-ink border-l-[3px] border-l-success bg-surface p-3">
              <div className="text-[10px] font-black uppercase tracking-wide text-success mb-2">
                What&apos;s Working
              </div>
              <ul className="space-y-1">
                {strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <span className="mt-0.5 text-success">✓</span>
                    <span className="text-ink">{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {concerns.length > 0 && (
            <div className="border-2 border-ink border-l-[3px] border-l-danger bg-surface p-3">
              <div className="text-[10px] font-black uppercase tracking-wide text-danger mb-2">
                Concerns
              </div>
              <ul className="space-y-1">
                {concerns.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <span className="mt-0.5 text-danger">✗</span>
                    <span className="text-ink">{c}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
