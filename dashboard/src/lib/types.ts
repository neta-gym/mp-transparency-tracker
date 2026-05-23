// TypeScript types mirroring the Python Pydantic schemas

export type House = "lok_sabha" | "rajya_sabha";
export type EvidenceGrade = "A" | "B" | "C" | "D" | "E";
export type CaseStatus = "pending" | "disposed" | "convicted" | "acquitted" | "unknown";
export type Severity = "low" | "medium" | "high";
export type FlagSeverity = "info" | "warning" | "error";

export interface DataSource {
  url: string;
  source_name: string;
  grade: EvidenceGrade;
  fetched_at: string;
  notes: string;
}

export interface MPProfile {
  name: string;
  constituency: string;
  state: string;
  party: string;
  myneta_candidate_id?: number | null;
  slug: string;
  house?: House;
  sansad_member_id?: number | null;
  profile_url?: string | null;
  canonical_name?: string | null;
  name_aliases?: string[];
  education?: string | null;
  profession?: string | null;
  age?: number | null;
  photo_url?: string | null;
}

export interface CriminalCase {
  description: string;
  ipc_sections: string[];
  is_serious: boolean;
  is_convicted: boolean;
  status: CaseStatus;
  court: string;
}

export interface CriminalRecord {
  total_cases: number;
  serious_cases: number;
  convictions: number;
  pending_cases: number;
  disposed_cases: number;
  cases: CriminalCase[];
  source: string;
  confidence: number;
  sources?: DataSource[];
}

export interface AssetDeclaration {
  movable_assets: number | null;
  immovable_assets: number | null;
  total_assets: number | null;
  liabilities: number | null;
  net_worth: number | null;
  previous_total_assets: number | null;
  asset_year: number | null;
  previous_asset_year: number | null;
  source: string;
  confidence: number;
  growth_ratio: number | null;
  sources?: DataSource[];
  annual_income?: number | null;
  election_expenditure?: number | null;
  wealth_percentile?: number | null;
}

export interface MPLADSWork {
  work_id: string;
  description: string;
  sector: string;
  recommended_amount: number | null;
  sanctioned_amount: number | null;
  expended_amount: number | null;
  status: string;
  district: string;
  completion_date: string | null;
  source: DataSource;
}

export interface MPLADSFundPeriod {
  fiscal_year: string;
  entitled: number | null;
  released: number | null;
  expended: number | null;
  opening_balance: number | null;
  interest_earned: number | null;
}

export interface MPLADSFund {
  entitled: number | null;
  released: number | null;
  sanctioned: number | null;
  expended: number | null;
  source: string;
  confidence: number;
  utilization_rate: number | null;
  sources?: DataSource[];
  works?: MPLADSWork[];
  works_count?: number;
  esakshi_coverage_start?: string | null;
  period_data?: MPLADSFundPeriod[];
  cumulative_entitled?: number | null;
  cumulative_released?: number | null;
  cumulative_expended?: number | null;
  includes_covid_suspension?: boolean;
  data_period_note?: string;
}

export interface ParliamentActivity {
  attendance_percentage: number | null;
  questions_asked: number;
  debates_participated: number;
  private_bills_introduced: number;
  is_minister: boolean;
  source: string;
  confidence: number;
  sources?: DataSource[];
  focus_topics?: string[];
  notable_questions?: string[];
}

export interface NewsAllegation {
  headline: string;
  source: string;
  severity: Severity;
  verified: boolean;
  url: string;
}

export interface CAGFinding {
  report_title: string;
  report_number: string;
  year: number;
  finding: string;
  category: string;
  state: string;
  severity: string;
  source: DataSource;
}

export interface MPCompensation {
  salary_per_month: number;
  constituency_allowance_per_month: number;
  office_expense_allowance_per_month: number;
  sumptuary_allowance_per_month: number;
  total_monthly: number;
  total_annual: number;
  effective_from: string;
  source_notification: string;
  notes: string;
}

export interface SAGYAdoption {
  village_name: string;
  district: string;
  state: string;
  adopted_year: number | null;
  phase: string;
  source: DataSource;
}

export interface CommitteeMembership {
  committee_name: string;
  role: string;
  source?: string;
}

export interface CommitteeEngagement {
  memberships: CommitteeMembership[];
  total_committees: number;
  leadership_roles: number;
  confidence: number;
  sources?: DataSource[];
}

export interface SocialMediaProfile {
  platform: string;
  handle: string;
  url?: string;
  followers?: number;
  verified?: boolean;
  active?: boolean;
}

export interface PublicAccessibility {
  profiles: SocialMediaProfile[];
  total_platforms: number;
  total_followers: number;
  confidence: number;
  sources?: DataSource[];
}

export interface NewsHeadline {
  headline: string;
  source: string;
  severity: string;
  verified: boolean;
  url?: string;
  sentiment: string;
}

export interface NewsSentiment {
  total_articles: number;
  positive: number;
  negative: number;
  neutral: number;
  top_headlines: NewsHeadline[];
  sentiment_summary: string;
  confidence: number;
  sources?: DataSource[];
}

export interface LegislativeRecord {
  bills_introduced: number;
  bills_passed: number;
  private_member_bills: number;
  zero_hour_mentions: number;
  special_mentions: number;
  confidence: number;
  sources?: DataSource[];
}

export interface ConstituencyContext {
  population?: number;
  literacy_rate?: number;
  urban_percentage?: number;
  district?: string;
}

export interface ResearchFindings {
  mp: MPProfile;
  criminal_record: CriminalRecord;
  assets: AssetDeclaration;
  mplads: MPLADSFund;
  parliament_activity: ParliamentActivity;
  news_allegations: NewsAllegation[];
  raw_notes: string;
  sources_consulted: string[];
  collected_at: string;
  evidence_summary: Record<string, string>;
  cag_findings?: CAGFinding[];
  compensation?: MPCompensation | null;
  sagy?: SAGYAdoption[];
  committees?: CommitteeEngagement | null;
  social_media?: PublicAccessibility | null;
  news_sentiment?: NewsSentiment | null;
  legislative?: LegislativeRecord | null;
  constituency_context?: ConstituencyContext | null;
}

export interface ValidationFlag {
  field: string;
  issue: string;
  severity: FlagSeverity;
  suggestion: string;
}

export interface ValidatedFindings {
  mp: MPProfile;
  findings: ResearchFindings;
  overall_confidence: number;
  flags: ValidationFlag[];
  cross_reference_notes: string;
  validated_at: string;
}

export interface ScoreBreakdown {
  mplads_score: number;
  asset_score: number;
  criminal_score: number;
  attendance_score: number;
  participation_score: number;
  committee_score: number;
  accessibility_score: number;
  legislative_score: number;
}

export interface ScoreResult {
  mp: MPProfile;
  composite_score: number;
  breakdown: ScoreBreakdown;
  data_confidence: number;
  qualitative_assessment: string;
  key_finding: string;
  scored_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  mp_name: string;
  constituency: string;
  party: string;
  state: string;
  composite_score: number;
  mplads_score: number;
  asset_score: number;
  criminal_score: number;
  attendance_score: number;
  participation_score: number;
  committee_score: number;
  accessibility_score: number;
  legislative_score: number;
  data_confidence: number;
  key_finding: string;
  house: string;
  avg_evidence_grade: string;
  photo_url?: string | null;
}

export interface Leaderboard {
  state: string;
  generated_at: string;
  methodology_version: string;
  total_mps: number;
  entries: LeaderboardEntry[];
}

// Dashboard-specific types

export interface StateManifest {
  slug: string;
  displayName: string;
  hasData: boolean;
  mpCount: number;
  avgScore: number | null;
}

export interface ScoreComponent {
  key: keyof ScoreBreakdown;
  label: string;
  weight: number;
}

export const SCORE_COMPONENTS: ScoreComponent[] = [
  { key: "mplads_score", label: "MPLADS", weight: 0.25 },
  { key: "asset_score", label: "Assets", weight: 0.15 },
  { key: "criminal_score", label: "Criminal", weight: 0.15 },
  { key: "attendance_score", label: "Attendance", weight: 0.10 },
  { key: "participation_score", label: "Participation", weight: 0.10 },
  { key: "committee_score", label: "Committees", weight: 0.10 },
  { key: "accessibility_score", label: "Accessibility", weight: 0.05 },
  { key: "legislative_score", label: "Legislative", weight: 0.10 },
];
