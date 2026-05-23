import ReactMarkdown from "react-markdown";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getAllStateSlugs,
  getAllMPSlugs,
  getScoreResult,
  getValidatedFindings,
} from "@/lib/data";
import { getStateBySlug } from "@/lib/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBadge } from "@/components/ScoreBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { ClientScoreRadar } from "@/components/ClientScoreRadar";
import {
  CriminalSection,
  AssetsSection,
  MPLADSSection,
  ParliamentSection,
  ValidationSection,
  NewsSection,
  CompensationSection,
  SAGYSection,
  CommitteeSection,
  LegislativeSection,
  SocialMediaSection,
  ConstituencySection,
  NewsSentimentSection,
} from "@/components/MPDetailSections";
import { RTITemplate } from "@/components/RTITemplate";
import { CAGSection } from "@/components/CAGSection";
import { PDFExportButton } from "@/components/PDFExportButton";
import { TrendChart } from "@/components/TrendChart";
import { getMPScoreHistory } from "@/lib/trends";
import { SCORE_COMPONENTS } from "@/lib/types";
import { getPartyColor, getPartyTextColor, getScoreColor } from "@/lib/colors";
import { formatDate } from "@/lib/format";
import { publicPath } from "@/lib/paths";

export function generateStaticParams() {
  const params: { stateSlug: string; mpSlug: string }[] = [];
  for (const stateSlug of getAllStateSlugs()) {
    for (const mpSlug of getAllMPSlugs(stateSlug)) {
      params.push({ stateSlug, mpSlug });
    }
  }
  return params;
}

interface PageProps {
  params: Promise<{ stateSlug: string; mpSlug: string }>;
}

export default async function MPDetailPage({ params }: PageProps) {
  const { stateSlug, mpSlug } = await params;
  const stateInfo = getStateBySlug(stateSlug);
  const score = getScoreResult(stateSlug, mpSlug);
  const validated = getValidatedFindings(stateSlug, mpSlug);

  if (!stateInfo || !score) {
    notFound();
  }

  const mp = score.mp;
  const partyColor = getPartyColor(mp.party);
  const partyTextColor = getPartyTextColor(mp.party);
  const scoreHistory = getMPScoreHistory(stateSlug, mp.name);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <Link href="/" className="hover:text-primary font-bold underline decoration-2">
          Dashboard
        </Link>
        <span className="text-text-muted font-mono">/</span>
        <Link
          href={`/state/${stateSlug}`}
          className="hover:text-primary font-bold underline decoration-2"
        >
          {stateInfo.displayName}
        </Link>
        <span className="text-text-muted font-mono">/</span>
        <span className="text-ink font-bold">{mp.name}</span>
      </div>

      {/* MP Profile Header */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
            {/* Score */}
            <ScoreBadge score={score.composite_score} size="lg" />

            {/* Photo */}
            {mp.photo_url ? (
              <img
                src={publicPath(mp.photo_url)}
                alt={mp.name}
                className="w-24 h-24 rounded-full border-3 border-ink object-cover shadow-brutal-sm"
              />
            ) : (
              <div className="w-24 h-24 rounded-full border-3 border-ink bg-highlight flex items-center justify-center shadow-brutal-sm">
                <span className="text-3xl font-bold text-ink">
                  {mp.name.charAt(0)}
                </span>
              </div>
            )}

            {/* Info */}
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl font-bold uppercase text-ink">
                  {mp.name}
                </h1>
                <span
                  className="text-sm font-bold px-2.5 py-1 border-2 border-ink uppercase"
                  style={{
                    backgroundColor: partyColor,
                    color: partyTextColor,
                    boxShadow: "1px 1px 0 0 #000",
                  }}
                >
                  {mp.party}
                </span>
              </div>
              <p className="text-text-secondary">
                {mp.constituency}, {stateInfo.displayName}
              </p>
              <p className="text-sm text-text-muted mt-1">
                {score.key_finding}
              </p>
            </div>

            {/* Confidence + Export */}
            <div className="flex flex-col items-end gap-2">
              <ConfidenceBadge confidence={score.data_confidence} />
              <span className="text-xs text-text-muted font-mono">
                Scored {formatDate(score.scored_at)}
              </span>
              <PDFExportButton />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Score Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Score Radar</CardTitle>
          </CardHeader>
          <CardContent>
            <ClientScoreRadar
              breakdown={score.breakdown}
              compositeScore={score.composite_score}
            />
          </CardContent>
        </Card>

        {/* Score Bars */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Score Breakdown</CardTitle>
              <div className="text-right">
                <span
                  className="text-3xl font-bold font-mono"
                  style={{ color: getScoreColor(score.composite_score) }}
                >
                  {score.composite_score.toFixed(1)}
                </span>
                <span className="text-text-muted text-sm font-mono"> / 100</span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {SCORE_COMPONENTS.map((comp) => (
                <ScoreBar
                  key={comp.key}
                  label={comp.label}
                  score={score.breakdown[comp.key]}
                  weight={comp.weight}
                />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Qualitative Assessment */}
      {score.qualitative_assessment && (
        <Card>
          <CardHeader>
            <CardTitle>Qualitative Assessment</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-text-secondary leading-relaxed">
              {score.qualitative_assessment}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Executive Summary */}
      {validated?.cross_reference_notes && (
        <Card className="executive-summary">
          <CardHeader className="bg-highlight">
            <CardTitle>Executive Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose max-w-none text-text-secondary">
              <ReactMarkdown>{validated.cross_reference_notes}</ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Historical Trend Chart */}
      {scoreHistory.length >= 2 && (
        <TrendChart data={scoreHistory} mpName={mp.name} />
      )}

      {/* Detailed Sections */}
      {validated && (
        <div className="space-y-4">
          <h2 className="text-xl font-bold uppercase border-b-3 border-ink pb-2">
            Detailed Findings
          </h2>
          <CriminalSection validated={validated} />
          <AssetsSection validated={validated} />
          <MPLADSSection validated={validated} />
          <ParliamentSection validated={validated} />
          <CommitteeSection validated={validated} />
          <LegislativeSection validated={validated} />
          <SocialMediaSection validated={validated} />
          <ConstituencySection validated={validated} />
          <CompensationSection validated={validated} />
          <SAGYSection validated={validated} />
          <CAGSection validated={validated} />
          <NewsSentimentSection validated={validated} />
          <NewsSection validated={validated} />
          <ValidationSection validated={validated} />
          <RTITemplate mp={validated.findings.mp} mplads={validated.findings.mplads} />
        </div>
      )}
    </div>
  );
}
