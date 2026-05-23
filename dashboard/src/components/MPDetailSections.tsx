"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GradeBadge } from "./GradeBadge";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Badge } from "@/components/ui/badge";
import { formatINR, formatCrore, formatPercent, formatGrowth } from "@/lib/format";
import type { ValidatedFindings, ValidationFlag, MPLADSWork, DataSource, CommitteeMembership } from "@/lib/types";
import { cn } from "@/lib/cn";
import { SourceCitation } from "./SourceCitation";

interface MPDetailSectionsProps {
  validated: ValidatedFindings;
}

function SectionToggle({
  title,
  grade,
  confidence,
  defaultOpen = false,
  children,
}: {
  title: string;
  grade?: string;
  confidence?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Card>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="w-7 h-7 flex items-center justify-center border-2 border-ink bg-highlight font-bold font-mono text-sm">
              {open ? "−" : "+"}
            </span>
            <CardTitle>{title}</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {grade && <GradeBadge grade={grade} />}
            {confidence != null && (
              <ConfidenceBadge confidence={confidence} />
            )}
          </div>
        </div>
      </CardHeader>
      {open && <CardContent>{children}</CardContent>}
    </Card>
  );
}

function StatRow({
  label,
  value,
  highlight,
  sources,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  sources?: DataSource[];
}) {
  return (
    <div className="flex justify-between items-center py-2 border-b-2 border-ink last:border-0">
      <span className="text-text-secondary text-sm uppercase tracking-wide">{label}</span>
      <span className="flex items-center gap-2">
        {sources && sources.length > 0 && <SourceCitation sources={sources} />}
        <span
          className={cn(
            "font-bold font-mono",
            highlight ? "text-ink" : "text-text-secondary"
          )}
        >
          {value}
        </span>
      </span>
    </div>
  );
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="h-4 bg-background border-2 border-ink overflow-hidden">
      <div
        className="h-full"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

export function CriminalSection({ validated }: MPDetailSectionsProps) {
  const cr = validated.findings.criminal_record;
  const hasCases = cr.total_cases > 0;

  return (
    <SectionToggle
      title="Criminal Record"
      confidence={cr.confidence}
      defaultOpen={hasCases}
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-ink">
              {cr.total_cases}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Total Cases</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-danger">
              {cr.serious_cases}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Serious</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-text-secondary">
              {cr.pending_cases}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Pending</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-danger">
              {cr.convictions}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Convictions</div>
          </div>
        </div>

        {cr.cases.length > 0 && (
          <div className="space-y-2 mt-4">
            <h4 className="text-sm font-bold uppercase tracking-wide text-text-secondary">
              Case Details
            </h4>
            {cr.cases.map((c, i) => (
              <div key={i} className="p-3 border-2 border-ink bg-surface text-sm">
                <div className="flex items-center gap-2 mb-1">
                  <Badge
                    className={cn(
                      c.is_serious
                        ? "bg-danger text-white border-2 border-ink"
                        : "bg-surface text-ink border-2 border-ink"
                    )}
                  >
                    {c.status}
                  </Badge>
                  {c.is_serious && (
                    <Badge className="bg-danger text-white border-2 border-ink">Serious</Badge>
                  )}
                </div>
                {c.description && (
                  <p className="text-text-secondary">{c.description}</p>
                )}
                {c.ipc_sections.length > 0 && (
                  <p className="text-text-muted text-xs mt-1 font-mono">
                    IPC: {c.ipc_sections.join(", ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {!hasCases && (
          <p className="text-text-secondary text-sm text-center py-4">
            No criminal cases on record
          </p>
        )}
      </div>
    </SectionToggle>
  );
}

export function AssetsSection({ validated }: MPDetailSectionsProps) {
  const assets = validated.findings.assets;
  const hasData = assets.total_assets != null;

  return (
    <SectionToggle title="Asset Declaration" confidence={assets.confidence}>
      <div className="space-y-2">
        <StatRow
          label="Total Assets"
          value={formatINR(assets.total_assets)}
          highlight
          sources={assets.sources}
        />
        <StatRow
          label="Movable Assets"
          value={formatINR(assets.movable_assets)}
        />
        <StatRow
          label="Immovable Assets"
          value={formatINR(assets.immovable_assets)}
        />
        <StatRow label="Liabilities" value={formatINR(assets.liabilities)} />
        <StatRow label="Net Worth" value={formatINR(assets.net_worth)} highlight />
        {assets.previous_total_assets != null && (
          <>
            <StatRow
              label="Previous Assets"
              value={formatINR(assets.previous_total_assets)}
            />
            <StatRow
              label="Growth"
              value={formatGrowth(assets.growth_ratio)}
              highlight
            />
          </>
        )}
        {assets.annual_income != null && (
          <StatRow label="Annual Income" value={formatINR(assets.annual_income)} />
        )}
        {assets.election_expenditure != null && (
          <StatRow label="Election Expenditure" value={formatINR(assets.election_expenditure)} />
        )}
        {assets.wealth_percentile != null && (
          <StatRow
            label="Wealth Percentile"
            value={`${assets.wealth_percentile.toFixed(0)}th`}
            highlight
          />
        )}
        {assets.asset_year && (
          <StatRow
            label="Declaration Year"
            value={`${assets.asset_year}${
              assets.previous_asset_year
                ? ` (prev: ${assets.previous_asset_year})`
                : ""
            }`}
          />
        )}
        {!hasData && (
          <p className="text-text-muted text-sm text-center py-2">
            Detailed asset data not available
          </p>
        )}
      </div>
    </SectionToggle>
  );
}

export function MPLADSSection({ validated }: MPDetailSectionsProps) {
  const mplads = validated.findings.mplads;
  const hasData = mplads.entitled != null || mplads.released != null;
  const works = mplads.works ?? [];
  const [showWorks, setShowWorks] = useState(false);

  // Group works by sector for breakdown
  const sectorCounts: Record<string, number> = {};
  for (const w of works) {
    const sector = w.sector || "other";
    sectorCounts[sector] = (sectorCounts[sector] || 0) + 1;
  }

  return (
    <SectionToggle title="MPLADS Fund Utilization" confidence={mplads.confidence}>
      <div className="space-y-3">
        <StatRow label="Entitled" value={formatCrore(mplads.entitled)} />
        <StatRow label="Released" value={formatCrore(mplads.released)} />
        <StatRow label="Sanctioned" value={formatCrore(mplads.sanctioned)} />
        <StatRow label="Expended" value={formatCrore(mplads.expended)} highlight sources={mplads.sources} />

        {mplads.utilization_rate != null && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-text-secondary uppercase tracking-wide">Utilization Rate</span>
              <span className="font-bold font-mono text-ink">
                {formatPercent(mplads.utilization_rate)}
              </span>
            </div>
            <ProgressBar
              value={mplads.utilization_rate}
              max={100}
              color={
                mplads.utilization_rate >= 80
                  ? "#00C853"
                  : mplads.utilization_rate >= 50
                  ? "#FFAB00"
                  : "#FF1744"
              }
            />
          </div>
        )}

        {/* MPLADS source / availability notes */}
        {(mplads.includes_covid_suspension || mplads.data_period_note) && (
          <div className="p-3 border-2 border-ink bg-warning/10 text-sm space-y-1">
            {mplads.includes_covid_suspension && (
              <p>
                <span className="font-bold">COVID note:</span> MPLADS was suspended Apr 2020 – Nov 2021.
              </p>
            )}
            {mplads.data_period_note && (
              <p>
                <span className="font-bold">Data note:</span> {mplads.data_period_note}
              </p>
            )}
          </div>
        )}

        {/* Year-wise breakdown */}
        {mplads.period_data && mplads.period_data.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-bold uppercase tracking-wide text-text-secondary mb-2">
              Year-wise Breakdown
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-2 border-ink">
                <thead>
                  <tr className="bg-surface border-b-2 border-ink">
                    <th className="text-left p-2 font-bold">Fiscal Year</th>
                    <th className="text-right p-2 font-bold">Entitled</th>
                    <th className="text-right p-2 font-bold">Released</th>
                    <th className="text-right p-2 font-bold">Expended</th>
                  </tr>
                </thead>
                <tbody>
                  {mplads.period_data.map((p, i) => (
                    <tr key={i} className="border-b border-ink/30">
                      <td className="p-2 font-mono">{p.fiscal_year}</td>
                      <td className="p-2 text-right font-mono">{formatCrore(p.entitled)}</td>
                      <td className="p-2 text-right font-mono">{formatCrore(p.released)}</td>
                      <td className="p-2 text-right font-mono">{formatCrore(p.expended)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Sector-wise breakdown from works */}
        {Object.keys(sectorCounts).length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-bold uppercase tracking-wide text-text-secondary mb-2">
              Works by Sector ({works.length} total)
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(sectorCounts)
                .sort(([, a], [, b]) => b - a)
                .map(([sector, count]) => (
                  <div key={sector} className="text-center p-2 border-2 border-ink bg-surface text-sm">
                    <div className="font-bold font-mono">{count}</div>
                    <div className="text-xs text-text-muted uppercase">{sector}</div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Collapsible work-level table */}
        {works.length > 0 && (
          <div className="mt-4">
            <button
              onClick={() => setShowWorks(!showWorks)}
              className="w-full flex items-center justify-between p-2 border-2 border-ink bg-surface hover:bg-highlight text-sm font-bold uppercase"
            >
              <span>Work Details ({works.length} works)</span>
              <span className="font-mono">{showWorks ? "−" : "+"}</span>
            </button>
            {showWorks && (
              <div className="overflow-x-auto border-x-2 border-b-2 border-ink">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-surface border-b-2 border-ink">
                      <th className="text-left p-2">Description</th>
                      <th className="text-left p-2">Sector</th>
                      <th className="text-right p-2">Sanctioned</th>
                      <th className="text-right p-2">Expended</th>
                      <th className="text-center p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {works.map((w: MPLADSWork, i: number) => (
                      <tr key={i} className="border-b border-ink/30">
                        <td className="p-2 max-w-[200px] truncate">{w.description || "—"}</td>
                        <td className="p-2">{w.sector || "—"}</td>
                        <td className="p-2 text-right font-mono">{formatINR(w.sanctioned_amount)}</td>
                        <td className="p-2 text-right font-mono">{formatINR(w.expended_amount)}</td>
                        <td className="p-2 text-center">
                          <Badge className={cn(
                            "text-xs border border-ink",
                            w.status === "completed" ? "bg-success text-white" :
                            w.status === "in_progress" ? "bg-warning text-ink" :
                            "bg-surface text-ink"
                          )}>
                            {w.status || "unknown"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {!hasData && (
          <p className="text-text-muted text-sm text-center py-2">
            MPLADS data not available
          </p>
        )}
      </div>
    </SectionToggle>
  );
}

export function CompensationSection({ validated }: MPDetailSectionsProps) {
  const compensation = validated.findings.compensation;
  if (!compensation) return null;

  return (
    <SectionToggle title="Compensation">
      <div className="space-y-2">
        <StatRow label="Salary" value={formatINR(compensation.salary_per_month)} />
        <StatRow
          label="Constituency Allowance"
          value={formatINR(compensation.constituency_allowance_per_month)}
        />
        <StatRow
          label="Office Expense Allowance"
          value={formatINR(compensation.office_expense_allowance_per_month)}
        />
        <StatRow
          label="Sumptuary Allowance"
          value={formatINR(compensation.sumptuary_allowance_per_month)}
        />
        <StatRow label="Total Monthly" value={formatINR(compensation.total_monthly)} highlight />
        <StatRow label="Total Annual" value={formatINR(compensation.total_annual)} highlight />
        {compensation.effective_from && (
          <StatRow label="Effective From" value={compensation.effective_from} />
        )}
        {compensation.notes && (
          <p className="text-xs text-text-muted mt-2 p-2 border border-ink/30 bg-surface">
            {compensation.notes}
          </p>
        )}
        <p className="text-xs text-text-muted italic">
          Source: {compensation.source_notification}
        </p>
      </div>
    </SectionToggle>
  );
}

export function ParliamentSection({ validated }: MPDetailSectionsProps) {
  const pa = validated.findings.parliament_activity;

  return (
    <SectionToggle
      title="Parliament Activity"
      confidence={pa.confidence}
    >
      <div className="space-y-3">
        <StatRow
          label="Attendance"
          value={formatPercent(pa.attendance_percentage)}
          highlight
        />
        <StatRow
          label="Questions Asked"
          value={pa.questions_asked.toString()}
        />
        <StatRow
          label="Debates Participated"
          value={pa.debates_participated.toString()}
        />
        <StatRow
          label="Private Bills Introduced"
          value={pa.private_bills_introduced.toString()}
        />
        {pa.is_minister && (
          <Badge className="bg-info text-white border-2 border-ink">Minister</Badge>
        )}
        {pa.focus_topics && pa.focus_topics.length > 0 && (
          <div className="mt-3">
            <h4 className="text-sm font-bold uppercase tracking-wide text-text-secondary mb-2">
              Focus Topics
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {pa.focus_topics.map((topic, i) => (
                <Badge
                  key={i}
                  className="bg-surface text-ink border-2 border-ink text-xs"
                >
                  {topic}
                </Badge>
              ))}
            </div>
          </div>
        )}
        {pa.notable_questions && pa.notable_questions.length > 0 && (
          <div className="mt-3">
            <h4 className="text-sm font-bold uppercase tracking-wide text-text-secondary mb-2">
              Notable Questions
            </h4>
            <ul className="space-y-1">
              {pa.notable_questions.map((q, i) => (
                <li key={i} className="text-sm text-text-secondary pl-3 border-l-2 border-ink">
                  {q}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </SectionToggle>
  );
}

export function ValidationSection({ validated }: MPDetailSectionsProps) {
  const flags = validated.flags;
  if (flags.length === 0) return null;

  const severityStyle: Record<string, string> = {
    error: "bg-danger text-white border-2 border-ink",
    warning: "bg-warning text-ink border-2 border-ink",
    info: "bg-info text-white border-2 border-ink",
  };

  return (
    <SectionToggle title="Validation Flags" defaultOpen={flags.length > 0}>
      <div className="space-y-2">
        {flags.map((flag: ValidationFlag, i: number) => (
          <div key={i} className="flex items-start gap-3 p-3 border-2 border-ink bg-surface">
            <Badge className={severityStyle[flag.severity] ?? severityStyle.info}>
              {flag.severity}
            </Badge>
            <div className="flex-1">
              <p className="text-sm text-ink">
                <span className="font-bold">{flag.field}:</span> {flag.issue}
              </p>
              {flag.suggestion && (
                <p className="text-xs text-text-muted mt-1">
                  {flag.suggestion}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </SectionToggle>
  );
}

export function SAGYSection({ validated }: MPDetailSectionsProps) {
  const sagy = validated.findings.sagy ?? [];
  if (sagy.length === 0) return null;

  return (
    <SectionToggle title="SAGY Village Adoption">
      <div className="space-y-2">
        <p className="text-sm text-text-secondary">
          Villages adopted under Sansad Adarsh Gram Yojana (informational, not scored).
        </p>
        {sagy.map((adoption, i) => (
          <div key={i} className="p-3 border-2 border-ink bg-surface">
            <div className="flex justify-between items-center">
              <div>
                <span className="font-bold text-sm">{adoption.village_name || "Unknown Village"}</span>
                {adoption.district && (
                  <span className="text-xs text-text-muted ml-2">
                    {adoption.district}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                {adoption.phase && (
                  <Badge className="bg-surface text-ink border border-ink">{adoption.phase}</Badge>
                )}
                {adoption.adopted_year && (
                  <span className="text-text-muted">{adoption.adopted_year}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </SectionToggle>
  );
}

export function NewsSection({ validated }: MPDetailSectionsProps) {
  const news = validated.findings.news_allegations;
  if (news.length === 0) return null;

  const severityStyle: Record<string, string> = {
    high: "bg-danger text-white border-2 border-ink",
    medium: "bg-warning text-ink border-2 border-ink",
    low: "bg-surface text-ink border-2 border-ink",
  };

  return (
    <SectionToggle title="News & Allegations">
      <div className="space-y-2">
        {news.map((item, i) => (
          <div key={i} className="p-3 border-2 border-ink bg-surface">
            <div className="flex items-start gap-2">
              <Badge className={severityStyle[item.severity] ?? severityStyle.low}>
                {item.severity}
              </Badge>
              <div>
                <p className="text-sm text-ink">{item.headline}</p>
                <p className="text-xs text-text-muted mt-1 font-mono">
                  Source: {item.source}
                  {item.verified && " · Verified"}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </SectionToggle>
  );
}

export function CommitteeSection({ validated }: MPDetailSectionsProps) {
  const committees = validated.findings.committees;
  if (!committees || committees.total_committees === 0) return null;

  return (
    <SectionToggle title="Committee Engagement" confidence={committees.confidence}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-ink">
              {committees.total_committees}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Committees</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-ink">
              {committees.leadership_roles}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Leadership Roles</div>
          </div>
        </div>

        {committees.memberships.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-2 border-ink">
              <thead>
                <tr className="bg-surface border-b-2 border-ink">
                  <th className="text-left p-2 font-bold">Committee</th>
                  <th className="text-left p-2 font-bold">Role</th>
                </tr>
              </thead>
              <tbody>
                {committees.memberships.map((m: CommitteeMembership, i: number) => (
                  <tr key={i} className="border-b border-ink/30">
                    <td className="p-2">{m.committee_name}</td>
                    <td className="p-2">
                      <Badge
                        className={cn(
                          "text-xs border border-ink",
                          m.role.toLowerCase().includes("chair") || m.role.toLowerCase().includes("head")
                            ? "bg-primary text-white"
                            : "bg-surface text-ink"
                        )}
                      >
                        {m.role}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </SectionToggle>
  );
}

export function LegislativeSection({ validated }: MPDetailSectionsProps) {
  const leg = validated.findings.legislative;
  if (!leg) return null;

  const hasData =
    leg.bills_introduced > 0 ||
    leg.bills_passed > 0 ||
    leg.private_member_bills > 0 ||
    leg.zero_hour_mentions > 0 ||
    leg.special_mentions > 0;

  if (!hasData) return null;

  return (
    <SectionToggle title="Legislative Record" confidence={leg.confidence}>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
          <div className="text-2xl font-bold font-mono text-ink">
            {leg.bills_introduced}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">Bills Introduced</div>
        </div>
        <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
          <div className="text-2xl font-bold font-mono text-ink">
            {leg.bills_passed}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">Bills Passed</div>
        </div>
        <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
          <div className="text-2xl font-bold font-mono text-ink">
            {leg.private_member_bills}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">Private Member Bills</div>
        </div>
        <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
          <div className="text-2xl font-bold font-mono text-ink">
            {leg.zero_hour_mentions}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">Zero Hour Mentions</div>
        </div>
        <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
          <div className="text-2xl font-bold font-mono text-ink">
            {leg.special_mentions}
          </div>
          <div className="text-xs text-text-muted uppercase tracking-wide">Special Mentions</div>
        </div>
      </div>
    </SectionToggle>
  );
}

export function SocialMediaSection({ validated }: MPDetailSectionsProps) {
  const sm = validated.findings.social_media;
  if (!sm || sm.profiles.length === 0) return null;

  return (
    <SectionToggle title="Public Accessibility" confidence={sm.confidence}>
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-ink">
              {sm.total_platforms}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Platforms</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-ink">
              {sm.total_followers.toLocaleString()}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Total Followers</div>
          </div>
        </div>

        <div className="space-y-2">
          {sm.profiles.map((profile, i) => (
            <div key={i} className="flex items-center justify-between p-3 border-2 border-ink bg-surface">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm uppercase">{profile.platform}</span>
                <span className="text-sm text-text-secondary font-mono">@{profile.handle}</span>
                {profile.verified && (
                  <Badge className="bg-info text-white border border-ink text-xs">Verified</Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                {profile.followers != null && (
                  <span className="text-xs text-text-muted font-mono">
                    {profile.followers.toLocaleString()} followers
                  </span>
                )}
                <Badge
                  className={cn(
                    "text-xs border border-ink",
                    profile.active !== false
                      ? "bg-success text-white"
                      : "bg-surface text-text-muted"
                  )}
                >
                  {profile.active !== false ? "Active" : "Inactive"}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </div>
    </SectionToggle>
  );
}

export function NewsSentimentSection({ validated }: MPDetailSectionsProps) {
  const ns = validated.findings.news_sentiment;
  if (!ns || ns.total_articles === 0) return null;

  return (
    <SectionToggle title="News Sentiment" confidence={ns.confidence}>
      <div className="space-y-3">
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-success">
              {ns.positive}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Positive</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-text-secondary">
              {ns.neutral}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Neutral</div>
          </div>
          <div className="text-center p-3 border-3 border-ink shadow-brutal-sm bg-surface">
            <div className="text-2xl font-bold font-mono text-danger">
              {ns.negative}
            </div>
            <div className="text-xs text-text-muted uppercase tracking-wide">Negative</div>
          </div>
        </div>

        {ns.sentiment_summary && (
          <p className="text-sm text-text-secondary p-3 border-2 border-ink bg-surface">
            {ns.sentiment_summary}
          </p>
        )}

        {ns.top_headlines.length > 0 && (
          <div>
            <h4 className="text-sm font-bold uppercase tracking-wide text-text-secondary mb-2">
              Top Headlines ({ns.total_articles} articles)
            </h4>
            <ul className="space-y-1">
              {ns.top_headlines.map((item, i) => (
                <li key={i} className="text-sm text-text-secondary pl-3 border-l-2 border-ink">
                  {item.headline}
                  <span className="text-xs text-text-muted ml-2">— {item.source}</span>
                  <Badge
                    className={cn(
                      "ml-2 text-xs border border-ink",
                      item.sentiment === "positive"
                        ? "bg-success text-white"
                        : item.sentiment === "negative"
                        ? "bg-danger text-white"
                        : "bg-surface text-ink"
                    )}
                  >
                    {item.sentiment}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </SectionToggle>
  );
}

export function ConstituencySection({ validated }: MPDetailSectionsProps) {
  const ctx = validated.findings.constituency_context;
  if (!ctx) return null;

  const hasData = ctx.district || ctx.population != null || ctx.literacy_rate != null || ctx.urban_percentage != null;
  if (!hasData) return null;

  return (
    <SectionToggle title="Constituency Context">
      <div className="space-y-2">
        {ctx.district && (
          <StatRow label="District" value={ctx.district} />
        )}
        {ctx.population != null && (
          <StatRow label="Population" value={ctx.population.toLocaleString()} />
        )}
        {ctx.literacy_rate != null && (
          <StatRow label="Literacy Rate" value={formatPercent(ctx.literacy_rate)} />
        )}
        {ctx.urban_percentage != null && (
          <StatRow label="Urban Population" value={formatPercent(ctx.urban_percentage)} />
        )}
        <p className="text-xs text-text-muted italic mt-2">
          Source: Census 2011
        </p>
      </div>
    </SectionToggle>
  );
}
