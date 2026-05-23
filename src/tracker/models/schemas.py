"""All Pydantic models — the contract between agents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# --- Enums ---

class House(str, Enum):
    LOK_SABHA = "lok_sabha"
    RAJYA_SABHA = "rajya_sabha"


class EvidenceGrade(str, Enum):
    """Data quality grade: A (authoritative govt API) to E (LLM knowledge)."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


# --- Data Source Provenance ---

class DataSource(BaseModel):
    """Tracks where a piece of data came from."""
    url: str = ""
    source_name: str = ""
    grade: EvidenceGrade = EvidenceGrade.E
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


# --- MP Profile ---

class MPProfile(BaseModel):
    """Core MP identity."""

    name: str
    constituency: str
    state: str
    party: str
    myneta_candidate_id: Optional[int] = None
    slug: str = ""
    house: House = House.LOK_SABHA
    sansad_member_id: Optional[int] = None
    profile_url: Optional[str] = None
    canonical_name: Optional[str] = None
    name_aliases: list[str] = Field(default_factory=list)

    # Phase 1: MyNeta enrichment
    education: Optional[str] = None
    profession: Optional[str] = None
    age: Optional[int] = None
    photo_url: Optional[str] = None

    def model_post_init(self, __context: object) -> None:
        if not self.slug:
            self.slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")


# --- Criminal ---

class CriminalCase(BaseModel):
    """Single criminal case."""

    description: str = ""
    ipc_sections: list[str] = Field(default_factory=list)
    is_serious: bool = False
    is_convicted: bool = False
    status: str = "unknown"  # pending / disposed / convicted / acquitted / unknown
    court: str = ""


class CriminalRecord(BaseModel):
    """Aggregate criminal record from MyNeta."""

    total_cases: int = 0
    serious_cases: int = 0
    convictions: int = 0
    pending_cases: int = 0
    disposed_cases: int = 0
    cases: list[CriminalCase] = Field(default_factory=list)
    source: str = "myneta"
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)


# --- Assets ---

class AssetDeclaration(BaseModel):
    """Asset and liability data from MyNeta affidavit."""

    movable_assets: Optional[float] = None
    immovable_assets: Optional[float] = None
    total_assets: Optional[float] = None
    liabilities: Optional[float] = None
    net_worth: Optional[float] = None
    previous_total_assets: Optional[float] = None
    asset_year: Optional[int] = None
    previous_asset_year: Optional[int] = None
    source: str = "myneta"
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)

    # Phase 1: MyNeta enrichment
    annual_income: Optional[float] = None
    election_expenditure: Optional[float] = None

    # Phase 5: Wealth percentile
    wealth_percentile: Optional[float] = None  # 0-100, among all MPs

    @computed_field
    @property
    def growth_ratio(self) -> Optional[float]:
        if self.total_assets is not None and self.previous_total_assets and self.previous_total_assets > 0:
            return (self.total_assets - self.previous_total_assets) / self.previous_total_assets
        return None


# --- MPLADS ---

class MPLADSWork(BaseModel):
    """Individual MPLADS work/project detail from eSAKSHI."""

    work_id: str = ""
    description: str = ""
    sector: str = ""  # education, health, infrastructure, etc.
    recommended_amount: Optional[float] = None
    sanctioned_amount: Optional[float] = None
    expended_amount: Optional[float] = None
    status: str = ""  # recommended, sanctioned, in_progress, completed
    district: str = ""
    completion_date: Optional[str] = None
    source: DataSource = Field(default_factory=DataSource)


class MPLADSFundPeriod(BaseModel):
    """MPLADS fund data for a specific fiscal year."""

    fiscal_year: str = ""  # e.g. "2024-25"
    entitled: Optional[float] = None
    released: Optional[float] = None
    expended: Optional[float] = None
    opening_balance: Optional[float] = None
    interest_earned: Optional[float] = None


class MPLADSFund(BaseModel):
    """MPLADS fund utilization data."""

    entitled: Optional[float] = None
    released: Optional[float] = None
    sanctioned: Optional[float] = None
    expended: Optional[float] = None
    source: str = "mplads"
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)

    # eSAKSHI work-level detail
    works: list[MPLADSWork] = Field(default_factory=list)
    works_count: int = 0
    esakshi_coverage_start: Optional[str] = None  # e.g. "2023-04-01"

    # Multi-year / cumulative fields
    period_data: list[MPLADSFundPeriod] = Field(default_factory=list)
    cumulative_entitled: Optional[float] = None
    cumulative_released: Optional[float] = None
    cumulative_expended: Optional[float] = None
    includes_covid_suspension: bool = False
    data_period_note: str = ""

    @computed_field
    @property
    def utilization_rate(self) -> Optional[float]:
        if self.released and self.released > 0 and self.expended is not None:
            return (self.expended / self.released) * 100
        return None


# --- Parliament Activity ---

class VoteRecord(BaseModel):
    """A single division vote record for an MP."""

    bill_name: str
    date: str
    vote: str  # yes, no, abstain, absent
    bill_passed: bool = True
    source: DataSource = Field(default_factory=DataSource)


class ParliamentActivity(BaseModel):
    """Parliament participation data from PRS India."""

    attendance_percentage: Optional[float] = None
    questions_asked: int = 0
    debates_participated: int = 0
    private_bills_introduced: int = 0
    is_minister: bool = False
    source: str = "prs"
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)

    # Phase 3: Focus areas
    focus_topics: list[str] = Field(default_factory=list)
    notable_questions: list[str] = Field(default_factory=list)

    # Phase 8: Voting record
    voting_record: list[VoteRecord] = Field(default_factory=list)


# --- Committee Memberships (Phase 2) ---

class CommitteeMembership(BaseModel):
    """A single committee membership."""

    committee_name: str
    role: str = "member"  # member, chairperson, vice-chairperson
    committee_type: str = ""  # standing, joint, select
    source: DataSource = Field(default_factory=DataSource)


class CommitteeEngagement(BaseModel):
    """Aggregate committee engagement data."""

    memberships: list[CommitteeMembership] = Field(default_factory=list)
    total_committees: int = 0
    leadership_roles: int = 0  # chair/vice-chair counts
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)


# --- Social Media (Phase 6) ---

class SocialMediaProfile(BaseModel):
    """A single social media profile."""

    platform: str  # twitter, facebook, instagram, youtube
    handle: str = ""
    url: str = ""
    followers: Optional[int] = None
    verified: bool = False
    active: bool = False  # posted in last 30 days


class PublicAccessibility(BaseModel):
    """Public accessibility via social media presence."""

    profiles: list[SocialMediaProfile] = Field(default_factory=list)
    total_platforms: int = 0
    total_followers: int = 0
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)


# --- News ---

class NewsAllegation(BaseModel):
    """A news item or allegation about the MP."""

    headline: str
    source: str = ""
    severity: str = "low"  # low, medium, high
    verified: bool = False
    url: str = ""
    sentiment: str = ""  # positive, negative, neutral


# --- News Sentiment (Phase 7) ---

class NewsSentiment(BaseModel):
    """Aggregated news sentiment analysis."""

    total_articles: int = 0
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    top_headlines: list[NewsAllegation] = Field(default_factory=list)
    sentiment_summary: str = ""
    confidence: float = 0.0


# --- Legislative Record (Phase 9) ---

class LegislativeRecord(BaseModel):
    """Legislative effectiveness metrics."""

    bills_introduced: int = 0
    bills_passed: int = 0
    private_member_bills: int = 0
    zero_hour_mentions: int = 0
    special_mentions: int = 0
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)


# --- Constituency Context (Phase 10) ---

class ConstituencyContext(BaseModel):
    """Constituency-level development indicators."""

    population: Optional[int] = None
    literacy_rate: Optional[float] = None
    urban_percentage: Optional[float] = None
    district: str = ""


# --- CAG Audit Findings ---

class CAGFinding(BaseModel):
    """A finding from a CAG audit report on MPLADS."""

    report_title: str = ""
    report_number: str = ""
    year: int = 0
    finding: str = ""
    category: str = ""  # idle_funds, bogus_ucs, incomplete_works
    state: str = ""
    severity: str = "medium"  # low, medium, high
    source: DataSource = Field(default_factory=DataSource)


# --- MP Compensation ---

class MPCompensation(BaseModel):
    """MP salary and allowances (informational, not scored)."""

    salary_per_month: float = 0.0
    constituency_allowance_per_month: float = 0.0
    office_expense_allowance_per_month: float = 0.0
    sumptuary_allowance_per_month: float = 0.0
    total_monthly: float = 0.0
    total_annual: float = 0.0
    effective_from: str = ""
    source_notification: str = ""  # e.g. "MPA 2018, Gazette notification..."
    notes: str = ""


# --- SAGY ---

class SAGYAdoption(BaseModel):
    """Sansad Adarsh Gram Yojana village adoption record."""

    village_name: str = ""
    district: str = ""
    state: str = ""
    adopted_year: Optional[int] = None
    phase: str = ""  # Phase-I, Phase-II, Phase-III
    source: DataSource = Field(default_factory=DataSource)


# --- Voting Analysis (Phase 1.1) ---

class VotingAnalysis(BaseModel):
    """Analysis of MP's voting patterns and party alignment."""

    total_votes: int = 0
    votes_with_party: int = 0
    votes_against_party: int = 0
    abstentions: int = 0
    absences: int = 0
    party_loyalty_pct: Optional[float] = None
    cross_party_votes: list[VoteRecord] = Field(default_factory=list)
    key_bills_missed: list[str] = Field(default_factory=list)
    confidence: float = 0.0


# --- Question Quality (Phase 1.2) ---

class QuestionQuality(BaseModel):
    """Quality analysis of parliamentary questions asked by an MP."""

    total_questions: int = 0
    starred_questions: int = 0
    unstarred_questions: int = 0
    short_notice_questions: int = 0
    unique_topics: int = 0
    constituency_relevant: int = 0
    follow_up_rate: float = 0.0
    quality_score: float = 0.0  # weighted composite
    confidence: float = 0.0


# --- Conflict of Interest (Phase 1.3) ---

class ConflictOfInterest(BaseModel):
    """Potential conflict of interest detection results."""

    mp_businesses: list[str] = Field(default_factory=list)
    committee_sectors: list[str] = Field(default_factory=list)
    question_sectors: list[str] = Field(default_factory=list)
    overlaps: list[str] = Field(default_factory=list)
    severity: str = "none"  # none, low, medium, high
    analysis_notes: str = ""
    confidence: float = 0.0


# --- Attendance Pattern (Phase 1.4) ---

class AttendancePattern(BaseModel):
    """Detailed attendance pattern analysis beyond a single percentage."""

    overall_pct: Optional[float] = None
    session_breakdown: dict[str, float] = Field(default_factory=dict)  # {"Budget 2024": 85.0}
    consecutive_absences: int = 0
    attended_key_debates: bool = True
    zero_hour_presence: Optional[float] = None
    pattern_label: str = ""  # "Consistent", "Monsoon slumper", "Key debate skipper"
    confidence: float = 0.0


# --- MGNREGA Constituency Data (Phase 2.3) ---

class MGNREGAData(BaseModel):
    """MGNREGA constituency-level data (informational, not scored)."""

    employment_days_generated: Optional[int] = None
    total_expenditure: Optional[float] = None
    works_completed: Optional[int] = None
    works_in_progress: Optional[int] = None
    avg_wage_per_day: Optional[float] = None
    financial_year: str = ""
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)


# --- PM-KISAN Constituency Data (Phase 2.3) ---

class PMKisanData(BaseModel):
    """PM-KISAN constituency-level data (informational, not scored)."""

    total_beneficiaries: Optional[int] = None
    amount_disbursed: Optional[float] = None
    installment_number: Optional[int] = None
    financial_year: str = ""
    confidence: float = 0.0
    sources: list[DataSource] = Field(default_factory=list)


# --- Research Findings (Researcher output) ---

class ResearchFindings(BaseModel):
    """Combined output from the Researcher agent for one MP."""

    mp: MPProfile
    criminal_record: CriminalRecord = CriminalRecord()
    assets: AssetDeclaration = AssetDeclaration()
    mplads: MPLADSFund = MPLADSFund()
    parliament_activity: ParliamentActivity = ParliamentActivity()
    news_allegations: list[NewsAllegation] = Field(default_factory=list)
    raw_notes: str = ""
    sources_consulted: list[str] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_summary: dict[str, str] = Field(default_factory=dict)

    # Existing enrichment
    cag_findings: list[CAGFinding] = Field(default_factory=list)
    compensation: Optional[MPCompensation] = None
    sagy: list[SAGYAdoption] = Field(default_factory=list)

    # Phase 2: Committee engagement
    committees: CommitteeEngagement = Field(default_factory=CommitteeEngagement)

    # Phase 6: Social media / public accessibility
    social_media: PublicAccessibility = Field(default_factory=PublicAccessibility)

    # Phase 7: News sentiment
    news_sentiment: NewsSentiment = Field(default_factory=NewsSentiment)

    # Phase 9: Legislative record
    legislative: LegislativeRecord = Field(default_factory=LegislativeRecord)

    # Phase 10: Constituency context
    constituency_context: ConstituencyContext = Field(default_factory=ConstituencyContext)

    # Phase 1.1: Voting analysis
    voting_analysis: VotingAnalysis = Field(default_factory=VotingAnalysis)

    # Phase 1.2: Question quality
    question_quality: QuestionQuality = Field(default_factory=QuestionQuality)

    # Phase 1.3: Conflict of interest
    conflict_of_interest: ConflictOfInterest = Field(default_factory=ConflictOfInterest)

    # Phase 1.4: Attendance patterns
    attendance_pattern: AttendancePattern = Field(default_factory=AttendancePattern)

    # Phase 2.3: Cross-scheme data
    mgnrega: MGNREGAData = Field(default_factory=MGNREGAData)
    pm_kisan: PMKisanData = Field(default_factory=PMKisanData)


# --- Validation ---

class ValidationFlag(BaseModel):
    """A flag raised during validation."""

    field: str
    issue: str
    severity: str = "warning"  # info, warning, error
    suggestion: str = ""


class ValidatedFindings(BaseModel):
    """Validator output: research findings + confidence + flags."""

    mp: MPProfile
    findings: ResearchFindings
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    flags: list[ValidationFlag] = Field(default_factory=list)
    cross_reference_notes: str = ""
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Scoring ---

class ScoreBreakdown(BaseModel):
    """Per-component score breakdown."""

    mplads_score: float = 50.0
    asset_score: float = 50.0
    criminal_score: float = 100.0
    attendance_score: float = 50.0
    participation_score: float = 50.0
    committee_score: float = 50.0
    accessibility_score: float = 50.0
    legislative_score: float = 50.0


class ScoreResult(BaseModel):
    """Full scoring result for one MP."""

    mp: MPProfile
    composite_score: float = 0.0
    breakdown: ScoreBreakdown = ScoreBreakdown()
    data_confidence: float = 0.0
    qualitative_assessment: str = ""
    key_finding: str = ""
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Leaderboard ---

class LeaderboardEntry(BaseModel):
    """One row in the leaderboard."""

    rank: int
    mp_name: str
    constituency: str
    party: str
    state: str
    composite_score: float
    mplads_score: float
    asset_score: float
    criminal_score: float
    attendance_score: float
    participation_score: float
    committee_score: float = 50.0
    accessibility_score: float = 50.0
    legislative_score: float = 50.0
    data_confidence: float
    key_finding: str = ""
    house: str = "lok_sabha"
    avg_evidence_grade: str = "E"
    photo_url: Optional[str] = None
    # Trend tracking (Phase 4.1)
    delta: Optional[float] = None  # change from previous run
    previous_score: Optional[float] = None


class Leaderboard(BaseModel):
    """Full leaderboard for a state (or national)."""

    state: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    methodology_version: str = "3.0"
    total_mps: int = 0
    entries: list[LeaderboardEntry] = Field(default_factory=list)


class NationalLeaderboard(BaseModel):
    """Aggregated national leaderboard across all states."""

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    methodology_version: str = "3.0"
    total_mps: int = 0
    states_included: list[str] = Field(default_factory=list)
    top_n: int = 50
    entries: list[LeaderboardEntry] = Field(default_factory=list)


# --- Score Delta (Phase 4.1) ---

class ScoreDelta(BaseModel):
    """Score change between two pipeline runs for one MP."""

    mp_name: str
    mp_slug: str
    state: str
    current_score: float
    previous_score: float
    delta: float
    dimension_deltas: dict[str, float] = Field(default_factory=dict)
    run_date_current: str = ""
    run_date_previous: str = ""
