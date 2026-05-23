"""SQLite schema migrations with version tracking."""

# Current schema version — increment when adding new migrations
CURRENT_SCHEMA_VERSION = 2

# Base tables (version 1) — created on first run
TABLES = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL,
        applied_at TEXT DEFAULT (datetime('now')),
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS mps (
        slug TEXT NOT NULL,
        state TEXT NOT NULL,
        name TEXT NOT NULL,
        constituency TEXT NOT NULL,
        party TEXT NOT NULL,
        myneta_candidate_id INTEGER,
        house TEXT DEFAULT 'lok_sabha',
        sansad_member_id INTEGER,
        profile_url TEXT,
        canonical_name TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (slug, state)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mp_slug TEXT NOT NULL,
        state TEXT NOT NULL,
        findings_json TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS validated_findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mp_slug TEXT NOT NULL,
        state TEXT NOT NULL,
        validated_json TEXT NOT NULL,
        overall_confidence REAL DEFAULT 0.0,
        num_flags INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mp_slug TEXT NOT NULL,
        state TEXT NOT NULL,
        composite_score REAL NOT NULL,
        mplads_score REAL,
        asset_score REAL,
        criminal_score REAL,
        attendance_score REAL,
        participation_score REAL,
        data_confidence REAL,
        score_json TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leaderboards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT NOT NULL,
        leaderboard_json TEXT NOT NULL,
        methodology_version TEXT DEFAULT '1.0',
        num_mps INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """,
]

# ALTER TABLE statements for existing databases that lack new columns.
# Wrapped in try/except at execution time since SQLite has no IF NOT EXISTS for ALTER.
ALTER_STATEMENTS = [
    "ALTER TABLE mps ADD COLUMN house TEXT DEFAULT 'lok_sabha'",
    "ALTER TABLE mps ADD COLUMN sansad_member_id INTEGER",
    "ALTER TABLE mps ADD COLUMN profile_url TEXT",
    "ALTER TABLE mps ADD COLUMN canonical_name TEXT",
    "ALTER TABLE scores ADD COLUMN committee_score REAL",
    "ALTER TABLE scores ADD COLUMN accessibility_score REAL",
    "ALTER TABLE scores ADD COLUMN legislative_score REAL",
]

# Versioned migrations — applied incrementally based on schema_version table
MIGRATIONS = {
    2: {
        "description": "Add score_history table for trend tracking",
        "statements": [
            """
            CREATE TABLE IF NOT EXISTS score_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mp_slug TEXT NOT NULL,
                state TEXT NOT NULL,
                composite_score REAL NOT NULL,
                score_json TEXT NOT NULL,
                run_timestamp TEXT DEFAULT (datetime('now')),
                methodology_version TEXT DEFAULT '3.0'
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_score_history_mp ON score_history (mp_slug, state)",
            "CREATE INDEX IF NOT EXISTS idx_score_history_ts ON score_history (state, run_timestamp)",
        ],
    },
}
