"""Configuration for MP Transparency Tracker."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class ScoreWeights(BaseSettings):
    """Weights for composite transparency score (must sum to 1.0).

    Rebalanced v3.1: Reduced MPLADS weight (data quality concerns),
    increased criminal weight (most reliable data), improved accessibility.
    """

    mplads: float = 0.20
    asset: float = 0.15
    criminal: float = 0.20
    attendance: float = 0.15
    participation: float = 0.10
    committee: float = 0.05
    accessibility: float = 0.05
    legislative: float = 0.10

    @model_validator(mode="after")
    def _weights_must_sum_to_one(self) -> ScoreWeights:
        total = (
            self.mplads
            + self.asset
            + self.criminal
            + self.attendance
            + self.participation
            + self.committee
            + self.accessibility
            + self.legislative
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Score weights must sum to 1.0, got {total:.4f}")
        return self


class DataSourceURLs(BaseSettings):
    """URLs for data sources — state-agnostic templates."""

    myneta_candidate: str = "https://myneta.info/LokSabha2024/candidate.php?candidate_id={candidate_id}"
    myneta_state_winners: str = "https://myneta.info/LokSabha2024/index.php?action=show_winners&sort=state"
    myneta_state_constituencies: str = (
        "https://myneta.info/LokSabha2024/index.php?action=show_constituencies&state_id={state_id}"
    )
    prs_github_json: str = (
        "https://raw.githubusercontent.com/Vonter/india-representatives-activity/main/json/Lok%20Sabha/18th.json"
    )
    prs_github_csv: str = (
        "https://raw.githubusercontent.com/Vonter/india-representatives-activity/main/csv/Lok%20Sabha/18th.csv"
    )
    prs_mptrack_base: str = "https://prsindia.org/mptrack/18th-lok-sabha"
    mplads_csv: str = "https://dataful.in/datasets/18540/"
    sansad_ls_api: str = "https://www.sansad.in/api_ls/member"
    sansad_rs_api: str = "https://www.sansad.in/api_rs/member"
    doj_mp_mla_dashboard: str = "https://dashboard.doj.gov.in/mp-mla-special-court/index.php"

    # eSAKSHI — official MoSPI MPLADS dashboard (Grade A)
    esakshi_dashboard: str = "https://mplads.mospi.gov.in"
    esakshi_api: str = "https://mplads.mospi.gov.in/api"

    # data.gov.in — Open Government Data Platform (Grade B)
    mplads_datagov_api: str = "https://api.data.gov.in/resource/9e0e3220-3de0-4f10-924b-eca88a58b272"

    # Sansad Q&A — Parliament Question answers (Grade A)
    sansad_qa_search: str = "https://sansad.in/ls/questions/search"

    # India Budget — Union Budget documents
    india_budget: str = "https://www.indiabudget.gov.in"

    # SAGY portal
    sagy_portal: str = "https://saanjhi.gov.in"


# MyNeta state IDs for constituency pages (verified 2026-05-12 via live testing)
MYNETA_STATE_IDS: dict[str, int] = {
    "andaman and nicobar islands": 1,
    "andhra pradesh": 2,
    "arunachal pradesh": 3,
    "assam": 4,
    "bihar": 5,
    "chandigarh": 6,
    "chhattisgarh": 7,
    "dadra and nagar haveli and daman and diu": 8,
    "delhi": 9,
    "goa": 10,
    "gujarat": 11,
    "haryana": 12,
    "himachal pradesh": 13,
    "jammu and kashmir": 14,
    "jharkhand": 15,
    "karnataka": 16,
    "kerala": 17,
    "ladakh": 18,
    "lakshadweep": 19,
    "madhya pradesh": 20,
    "maharashtra": 21,
    "manipur": 22,
    "meghalaya": 23,
    "mizoram": 24,
    "nagaland": 25,
    "odisha": 26,
    "puducherry": 27,
    "punjab": 28,
    "rajasthan": 29,
    "sikkim": 30,
    "tamil nadu": 31,
    "telangana": 32,
    "tripura": 33,
    "uttarakhand": 34,
    "uttar pradesh": 35,
    "west bengal": 36,
}


class Settings(BaseSettings):
    """Main application settings, loaded from environment / .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # data.gov.in API key (optional, for higher rate limits)
    datagov_api_key: str = Field(default="", description="data.gov.in API key")

    # GLM-5.3 Flash (Z.ai) — optional LLM assist for MPLADS sector classification.
    # Keyword classification is the primary path; GLM-5.3 reclassifies works the
    # keywords miss. Disabled when no key is set. See src/tracker/utils/glm.py.
    glm_api_key: str = Field(default="", description="Z.ai API key for GLM-5.3 Flash")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key (fallback provider)")
    glm_base_url: str = Field(default="", description="Override GLM chat-completions base URL")
    glm_model: str = Field(default="", description="Override GLM model slug")
    glm_timeout: float = Field(default=30.0, description="GLM request timeout (seconds)")

    # Concurrency
    max_concurrent_mps: int = Field(default=3, description="Max MPs processed in parallel")

    # Paths
    database_path: str = Field(default="data/tracker.db", description="SQLite database path")
    data_dir: str = Field(default="data", description="Root data directory")

    # MP profile photos (local copies of public Sansad images, keyed by member ID)
    mp_photos_dir: str = Field(
        default="dashboard/public/mp-photos",
        description="Directory holding local MP photos as {sansad_member_id}.jpg",
    )
    mp_photos_url_prefix: str = Field(
        default="/mp-photos",
        description="Root-relative URL prefix for locally hosted MP photos",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Retry
    max_retries: int = Field(default=3, description="Max retries for HTTP/API calls")
    retry_base_delay: float = Field(default=2.0, description="Base delay for exponential backoff (seconds)")

    # Rate limiting
    scrape_delay: float = Field(default=1.0, description="Delay between scrape requests (seconds)")

    # Cache freshness
    cache_max_age_days: int = Field(
        default=15, description="Max age (days) for cached research data before re-fetching"
    )

    # Scoring
    weights: ScoreWeights = ScoreWeights()
    urls: DataSourceURLs = DataSourceURLs()


# Singleton
settings = Settings()
