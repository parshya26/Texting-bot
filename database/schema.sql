-- ============================================================================
-- TEXTING SUPPORT BOT — FULL DATABASE SCHEMA (SQLite)
-- ============================================================================
-- Design notes:
--  - Runs on SQLite with zero external server (single file: bot.db).
--  - All timestamps stored as TEXT in ISO format via datetime('now').
--  - Booleans stored as INTEGER (0/1).
--  - Every table uses AUTOINCREMENT ids so foreign keys stay stable.
--  - This file is idempotent (safe to run every startup) via IF NOT EXISTS.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- CORE: USERS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER UNIQUE NOT NULL,
    username        TEXT,
    first_name      TEXT,
    is_admin        INTEGER NOT NULL DEFAULT 0,
    is_banned       INTEGER NOT NULL DEFAULT 0,
    first_seen      TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);


-- ----------------------------------------------------------------------------
-- SETTINGS: simple key/value store for admin-toggleable config
-- (e.g. apply_mod_open = "1"/"0", giveaway_contact_username = "hoepium")
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ----------------------------------------------------------------------------
-- SUPPORT FORMS: report / appeal / suggestion / feedback / application
-- Each row stores the full multi-step answers as separate columns so the
-- admin queue can render them exactly like the on-screen review step.
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    target_username TEXT NOT NULL,
    reason          TEXT NOT NULL,
    proof           TEXT NOT NULL DEFAULT 'none',
    anonymous       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    admin_reason    TEXT,                               -- explanation shown to user on reject
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS appeals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    appealing       TEXT NOT NULL,      -- 'Mute' | 'Warning' | 'Ban'
    reason          TEXT NOT NULL,
    anything_else   TEXT NOT NULL DEFAULT 'none',
    status          TEXT NOT NULL DEFAULT 'pending',
    admin_reason    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    idea            TEXT NOT NULL,
    how_it_works    TEXT NOT NULL,
    prizes          TEXT NOT NULL DEFAULT 'none',
    why             TEXT NOT NULL,
    anonymous       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending',
    admin_reason    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    feedback_text   TEXT NOT NULL,
    anonymous       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending',
    admin_reason    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    experience      TEXT NOT NULL,
    availability    TEXT NOT NULL,
    why_you         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    admin_reason    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);


-- ----------------------------------------------------------------------------
-- GIVEAWAY REQUEST (the support-portal form; distinct from the live engine below)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS giveaway_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    details         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ----------------------------------------------------------------------------
-- LIVE GIVEAWAY ENGINE: actual running giveaways posted in the group
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS giveaways (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id             INTEGER NOT NULL,
    message_id          INTEGER,                    -- the posted giveaway message (for editing entry count)
    prize               TEXT NOT NULL,
    hosted_by_user_id   INTEGER NOT NULL REFERENCES users(id),
    conditions          TEXT,                        -- free text, one condition per line
    required_channels   TEXT,                        -- comma-separated usernames (no @) users must join to enter
    ends_at             TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',  -- active | ended | cancelled
    winner_user_id      INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS giveaway_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    giveaway_id     INTEGER NOT NULL REFERENCES giveaways(id) ON DELETE CASCADE,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    entered_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(giveaway_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_giveaway_entries_giveaway ON giveaway_entries(giveaway_id);


-- ----------------------------------------------------------------------------
-- MODERATOR SYSTEM: communities, moderators, services, reviews
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS communities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    link            TEXT NOT NULL,
    description     TEXT,
    owner_name      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS moderators (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER UNIQUE,
    username            TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    role                TEXT NOT NULL DEFAULT 'Moderator',
    bio                 TEXT,
    community_id        INTEGER REFERENCES communities(id),
    contact_username    TEXT,
    reputation_score    REAL NOT NULL DEFAULT 0,
    verification_status TEXT NOT NULL DEFAULT 'unverified',  -- unverified | verified | trusted
    active_status       INTEGER NOT NULL DEFAULT 1,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_moderators_username ON moderators(username);

CREATE TABLE IF NOT EXISTS services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    moderator_id    INTEGER NOT NULL REFERENCES moderators(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT
);
CREATE INDEX IF NOT EXISTS idx_services_moderator ON services(moderator_id);

CREATE TABLE IF NOT EXISTS reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    moderator_id        INTEGER NOT NULL REFERENCES moderators(id) ON DELETE CASCADE,
    rating              INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text         TEXT NOT NULL,
    service_category    TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reviews_moderator ON reviews(moderator_id, status);
CREATE INDEX IF NOT EXISTS idx_reviews_user_mod ON reviews(user_id, moderator_id);


-- ----------------------------------------------------------------------------
-- RANK / XP / STREAK SYSTEM (per-group activity tracking, Texting-only data)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_stats (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id         INTEGER NOT NULL,
    chat_id             INTEGER NOT NULL,
    total_messages      INTEGER NOT NULL DEFAULT 0,
    xp                  INTEGER NOT NULL DEFAULT 0,
    level               INTEGER NOT NULL DEFAULT 0,
    last_message_at     TEXT,
    last_xp_at          TEXT,          -- used for the anti-spam XP cooldown
    UNIQUE(telegram_id, chat_id)
);
CREATE INDEX IF NOT EXISTS idx_user_stats_chat ON user_stats(chat_id, total_messages DESC);

-- One row per user per chat per calendar day; powers daily/weekly/monthly
-- leaderboards via SUM(message_count) over a date range, and also drives streaks.
CREATE TABLE IF NOT EXISTS daily_activity (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER NOT NULL,
    chat_id         INTEGER NOT NULL,
    activity_date   TEXT NOT NULL,      -- 'YYYY-MM-DD'
    message_count   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(telegram_id, chat_id, activity_date)
);
CREATE INDEX IF NOT EXISTS idx_daily_activity_lookup ON daily_activity(chat_id, activity_date);

CREATE TABLE IF NOT EXISTS streaks (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id             INTEGER NOT NULL,
    chat_id                 INTEGER NOT NULL,
    current_streak          INTEGER NOT NULL DEFAULT 0,
    best_streak             INTEGER NOT NULL DEFAULT 0,
    best_streak_start       TEXT,
    best_streak_end         TEXT,
    last_active_date        TEXT,        -- 'YYYY-MM-DD', used to detect streak breaks
    UNIQUE(telegram_id, chat_id)
);


-- ----------------------------------------------------------------------------
-- REPUTATION SYSTEM (/rep, /reps)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reputation (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     INTEGER NOT NULL,
    chat_id         INTEGER NOT NULL,
    rep_points      INTEGER NOT NULL DEFAULT 0,
    UNIQUE(telegram_id, chat_id)
);
CREATE INDEX IF NOT EXISTS idx_reputation_chat ON reputation(chat_id, rep_points DESC);

-- Logs every successful /rep so we can enforce "1 rep per giver per 24h".
CREATE TABLE IF NOT EXISTS rep_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    giver_telegram_id      INTEGER NOT NULL,
    receiver_telegram_id   INTEGER NOT NULL,
    chat_id                INTEGER NOT NULL,
    given_at                TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rep_log_giver ON rep_log(giver_telegram_id, chat_id, given_at);
