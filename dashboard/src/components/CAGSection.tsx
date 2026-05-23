"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ValidatedFindings } from "@/lib/types";

interface CAGSectionProps {
  validated: ValidatedFindings;
}

export function CAGSection({ validated }: CAGSectionProps) {
  const findings = validated.findings.cag_findings ?? [];
  const [isOpen, setIsOpen] = useState(false);

  if (findings.length === 0) return null;

  const severityStyle: Record<string, string> = {
    high: "bg-danger text-white border-2 border-ink",
    medium: "bg-warning text-ink border-2 border-ink",
    low: "bg-surface text-ink border-2 border-ink",
  };

  return (
    <Card>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="w-7 h-7 flex items-center justify-center border-2 border-ink bg-highlight font-bold font-mono text-sm">
              {isOpen ? "−" : "+"}
            </span>
            <CardTitle>CAG Audit Context</CardTitle>
          </div>
          <Badge className="bg-info text-white border-2 border-ink text-xs">
            {findings.length} findings
          </Badge>
        </div>
      </CardHeader>
      {isOpen && (
        <CardContent>
          <p className="text-sm text-text-secondary mb-3">
            State-level findings from CAG performance audits of MPLADS.
            These are contextual — they apply to the state/national level, not to this specific MP.
          </p>
          <div className="space-y-2">
            {findings.map((f, i) => (
              <div
                key={i}
                className="p-3 border-2 border-ink bg-surface"
              >
                <div className="flex items-start gap-2">
                  <Badge className={severityStyle[f.severity] ?? severityStyle.medium}>
                    {f.severity}
                  </Badge>
                  <div className="flex-1">
                    <p className="text-sm text-ink">{f.finding}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-text-muted font-mono">
                      <span>Report No. {f.report_number}</span>
                      <span>({f.year})</span>
                      <span className="uppercase">{f.category.replace(/_/g, " ")}</span>
                    </div>
                    {f.source?.url && (
                      <a
                        href={f.source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary underline mt-1 block"
                      >
                        View Report
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
