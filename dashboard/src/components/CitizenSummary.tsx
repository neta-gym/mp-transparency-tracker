import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { formatCrore, formatPercent } from "@/lib/format";
import { publicPath } from "@/lib/paths";
import type { ScoreResult, ValidatedFindings } from "@/lib/types";

interface CitizenSummaryProps {
  score: ScoreResult;
  validated: ValidatedFindings | null;
  stateSlug: string;
}

function MoneyStat({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: string;
  tone?: "ink" | "danger" | "success" | "muted";
}) {
  const color =
    tone === "danger"
      ? "text-danger"
      : tone === "success"
      ? "text-success"
      : tone === "muted"
      ? "text-text-muted"
      : "text-ink";
  return (
    <div className="border-2 border-ink bg-surface p-3 text-center">
      <div className={`font-mono text-xl font-black ${color}`}>{value}</div>
      <div className="mt-1 text-[10px] font-bold uppercase tracking-wide text-text-muted">
        {label}
      </div>
    </div>
  );
}

function WorkStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-2 border-ink bg-white p-3 text-center">
      <div className="font-mono text-xl font-black text-ink">{value}</div>
      <div className="mt-1 text-[10px] font-bold uppercase tracking-wide text-text-muted">
        {label}
      </div>
    </div>
  );
}

/**
 * Plain-language summary for a citizen from the MP's constituency:
 * what the MP did, and how much fund money went unused.
 */
export function CitizenSummary({ score, validated, stateSlug }: CitizenSummaryProps) {
  const mp = score.mp;
  const f = validated?.findings;
  const mplads = f?.mplads;

  const entitled = mplads?.entitled ?? null;
  const released = mplads?.released ?? null;
  const expended = mplads?.expended ?? null;
  const base = released ?? entitled;
  const unspent =
    base != null && expended != null ? Math.max(0, base - expended) : null;
  const hasMoneyData = entitled != null || released != null || expended != null;

  const pa = f?.parliament_activity;
  const committees = f?.committees;
  const legislative = f?.legislative;
  const worksCompleted =
    mplads?.works?.filter((w) => w.status === "completed").length ?? null;

  const reportPath = `/data/${stateSlug}/reports/${mp.slug}.md`;

  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div>
          <h2 className="text-lg font-black uppercase text-ink">
            From {mp.constituency}? Here&apos;s the plain summary
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            What your MP did with the job — and the public money that came with it.
          </p>
        </div>

        {/* The money */}
        <div>
          <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-text-secondary">
            ₹5 crore/year MPLADS fund — money meant for your area
          </h3>
          {hasMoneyData ? (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <MoneyStat label="Entitled" value={formatCrore(entitled)} />
                <MoneyStat label="Released" value={formatCrore(released)} />
                <MoneyStat label="Actually spent" value={formatCrore(expended)} />
                <MoneyStat
                  label="Left unspent"
                  value={unspent != null ? formatCrore(unspent) : "—"}
                  tone={unspent != null && unspent > 0 ? "danger" : "success"}
                />
              </div>
              {mplads?.utilization_rate != null && (
                <div className="mt-3 flex items-center gap-3">
                  <div className="h-3 flex-1 border-2 border-ink bg-gray-100">
                    <div
                      className="h-full"
                      style={{
                        width: `${Math.min(100, Math.max(0, mplads.utilization_rate))}%`,
                        backgroundColor:
                          mplads.utilization_rate >= 80
                            ? "#00C853"
                            : mplads.utilization_rate >= 50
                            ? "#FFAB00"
                            : "#FF1744",
                      }}
                    />
                  </div>
                  <span className="whitespace-nowrap font-mono text-sm font-bold text-ink">
                    {formatPercent(mplads.utilization_rate)} used
                  </span>
                </div>
              )}
              {worksCompleted != null && (
                <p className="mt-2 text-xs text-text-secondary">
                  {worksCompleted} completed work{worksCompleted === 1 ? "" : "s"} on record.
                </p>
              )}
            </>
          ) : (
            <p className="border-2 border-dashed border-ink/40 bg-gray-50 p-3 text-sm text-text-secondary">
              Fund utilization data not available for this MP — in itself a transparency failure.
            </p>
          )}
        </div>

        {/* The job */}
        {(pa || committees || legislative) && (
          <div>
            <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-text-secondary">
              The job they were elected to do
            </h3>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <WorkStat
                label="Attendance"
                value={
                  pa?.attendance_percentage != null
                    ? `${Math.round(pa.attendance_percentage)}%`
                    : "—"
                }
              />
              <WorkStat
                label="Questions asked"
                value={pa ? String(pa.questions_asked) : "—"}
              />
              <WorkStat
                label="Debates"
                value={pa ? String(pa.debates_participated) : "—"}
              />
              <WorkStat
                label="Bills introduced"
                value={legislative ? String(legislative.bills_introduced) : "—"}
              />
              <WorkStat
                label="Committees"
                value={committees ? String(committees.total_committees) : "—"}
              />
            </div>
          </div>
        )}

        {/* Shareable / AI-friendly links */}
        <div className="flex flex-wrap gap-2 pt-1">
          <Link
            href={publicPath(reportPath)}
            className="border-2 border-ink bg-highlight px-2 py-1 text-xs font-bold uppercase text-ink shadow-brutal-sm hover:bg-accent"
          >
            📄 Full plain-text report
          </Link>
          <Link
            href={`/compare`}
            className="border-2 border-ink bg-surface px-2 py-1 text-xs font-bold uppercase text-ink shadow-brutal-sm hover:bg-highlight"
          >
            ⚖️ Compare with another MP
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
