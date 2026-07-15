"""
Async data-access layer over SQLite (aiosqlite).

Every method returns plain dicts/lists/primitives — no SQLite-specific
objects leak into handlers — so this file is the only thing that would
need rewriting if the project ever moves to PostgreSQL.

Connection strategy: a single persistent connection is opened once and
reused for the life of the process, with WAL journal mode + a busy_timeout.
Opening a brand-new SQLite connection for every single query (the previous
approach) causes contention under any real message volume — concurrent
opens can hit "database is locked" errors, which were being silently
swallowed by aiogram's error handling, making the bot intermittently not
reply at all. WAL mode lets reads and writes coexist without blocking each
other, and reusing one connection removes the open/close overhead entirely.
"""
import asyncio
import datetime as dt
import os
from pathlib import Path
from typing import Optional

import aiosqlite

from config import config

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _ensure_db_directory(path: str) -> None:
    """Creates the parent directory of the database file if it doesn't exist.
    This makes the app resilient to whatever exact volume mount path was
    configured on the hosting platform (Railway, etc.) — no more manual
    "is /data a file or a folder?" guessing."""
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


async def init_db() -> None:
    _ensure_db_directory(config.db_path)
    async with aiosqlite.connect(config.db_path) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            await conn.executescript(f.read())
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.commit()


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def _ensure_connected(self) -> aiosqlite.Connection:
        if self._conn is None:
            _ensure_db_directory(self.path)
            conn = await aiosqlite.connect(self.path)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA busy_timeout=5000;")
            await conn.execute("PRAGMA foreign_keys=ON;")
            await conn.commit()
            self._conn = conn
        return self._conn

    # ---------------- low-level helpers ----------------
    # A single asyncio.Lock serializes access to the one shared connection.
    # This is cheap (SQLite operations are fast) and completely avoids any
    # "database is locked" errors from overlapping writes.
    async def _fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        async with self._lock:
            conn = await self._ensure_connected()
            cur = await conn.execute(query, params)
            row = await cur.fetchone()
            return dict(row) if row else None

    async def _fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        async with self._lock:
            conn = await self._ensure_connected()
            cur = await conn.execute(query, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def _execute(self, query: str, params: tuple = ()) -> int:
        async with self._lock:
            conn = await self._ensure_connected()
            cur = await conn.execute(query, params)
            await conn.commit()
            return cur.lastrowid


    # ================= USERS =================
    async def get_or_create_user(self, telegram_id: int, username: str, first_name: str) -> dict:
        user = await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        if user:
            await self._execute(
                "UPDATE users SET username = ?, first_name = ?, last_seen = datetime('now') WHERE telegram_id = ?",
                (username, first_name, telegram_id),
            )
            return user
        user_id = await self._execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (telegram_id, username, first_name),
        )
        return await self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))

    async def is_admin(self, telegram_id: int) -> bool:
        if telegram_id in config.admin_ids:
            return True
        user = await self._fetchone("SELECT is_admin FROM users WHERE telegram_id = ?", (telegram_id,))
        return bool(user and user["is_admin"])

    # ================= SETTINGS (key/value) =================
    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self._fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self._execute(
            """INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')""",
            (key, value),
        )

    async def is_mod_applications_open(self) -> bool:
        return (await self.get_setting("apply_mod_open", "0")) == "1"

    async def set_mod_applications_open(self, open_: bool) -> None:
        await self.set_setting("apply_mod_open", "1" if open_ else "0")

    # ================= SUPPORT FORMS =================
    # --- Reports ---
    async def add_report(self, user_id: int, target_username: str, reason: str, proof: str, anonymous: bool) -> int:
        return await self._execute(
            """INSERT INTO reports (user_id, target_username, reason, proof, anonymous)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, target_username, reason, proof, int(anonymous)),
        )

    async def get_report(self, report_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT reports.*, users.username as submitter_username, users.telegram_id as submitter_telegram_id
               FROM reports JOIN users ON users.id = reports.user_id WHERE reports.id = ?""",
            (report_id,),
        )

    async def list_pending_reports(self) -> list[dict]:
        return await self._fetchall(
            """SELECT reports.*, users.username as submitter_username
               FROM reports JOIN users ON users.id = reports.user_id
               WHERE reports.status = 'pending' ORDER BY reports.created_at ASC"""
        )

    async def set_report_status(self, report_id: int, status: str, admin_reason: str = None) -> Optional[dict]:
        report = await self.get_report(report_id)
        if not report:
            return None
        await self._execute(
            "UPDATE reports SET status = ?, admin_reason = ?, resolved_at = datetime('now') WHERE id = ?",
            (status, admin_reason, report_id),
        )
        return report

    # --- Appeals ---
    async def add_appeal(self, user_id: int, appealing: str, reason: str, anything_else: str) -> int:
        return await self._execute(
            "INSERT INTO appeals (user_id, appealing, reason, anything_else) VALUES (?, ?, ?, ?)",
            (user_id, appealing, reason, anything_else),
        )

    async def get_appeal(self, appeal_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT appeals.*, users.username as submitter_username, users.telegram_id as submitter_telegram_id
               FROM appeals JOIN users ON users.id = appeals.user_id WHERE appeals.id = ?""",
            (appeal_id,),
        )

    async def list_pending_appeals(self) -> list[dict]:
        return await self._fetchall(
            """SELECT appeals.*, users.username as submitter_username
               FROM appeals JOIN users ON users.id = appeals.user_id
               WHERE appeals.status = 'pending' ORDER BY appeals.created_at ASC"""
        )

    async def set_appeal_status(self, appeal_id: int, status: str, admin_reason: str = None) -> Optional[dict]:
        appeal = await self.get_appeal(appeal_id)
        if not appeal:
            return None
        await self._execute(
            "UPDATE appeals SET status = ?, admin_reason = ?, resolved_at = datetime('now') WHERE id = ?",
            (status, admin_reason, appeal_id),
        )
        return appeal

    # --- Suggestions ---
    async def add_suggestion(self, user_id: int, idea: str, how_it_works: str, prizes: str, why: str, anonymous: bool) -> int:
        return await self._execute(
            """INSERT INTO suggestions (user_id, idea, how_it_works, prizes, why, anonymous)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, idea, how_it_works, prizes, why, int(anonymous)),
        )

    async def get_suggestion(self, suggestion_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT suggestions.*, users.username as submitter_username, users.telegram_id as submitter_telegram_id
               FROM suggestions JOIN users ON users.id = suggestions.user_id WHERE suggestions.id = ?""",
            (suggestion_id,),
        )

    async def list_pending_suggestions(self) -> list[dict]:
        return await self._fetchall(
            """SELECT suggestions.*, users.username as submitter_username
               FROM suggestions JOIN users ON users.id = suggestions.user_id
               WHERE suggestions.status = 'pending' ORDER BY suggestions.created_at ASC"""
        )

    async def set_suggestion_status(self, suggestion_id: int, status: str, admin_reason: str = None) -> Optional[dict]:
        suggestion = await self.get_suggestion(suggestion_id)
        if not suggestion:
            return None
        await self._execute(
            "UPDATE suggestions SET status = ?, admin_reason = ?, resolved_at = datetime('now') WHERE id = ?",
            (status, admin_reason, suggestion_id),
        )
        return suggestion

    # --- Feedback ---
    async def add_feedback(self, user_id: int, feedback_text: str, anonymous: bool) -> int:
        return await self._execute(
            "INSERT INTO feedback (user_id, feedback_text, anonymous) VALUES (?, ?, ?)",
            (user_id, feedback_text, int(anonymous)),
        )

    async def get_feedback(self, feedback_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT feedback.*, users.username as submitter_username, users.telegram_id as submitter_telegram_id
               FROM feedback JOIN users ON users.id = feedback.user_id WHERE feedback.id = ?""",
            (feedback_id,),
        )

    async def list_pending_feedback(self) -> list[dict]:
        return await self._fetchall(
            """SELECT feedback.*, users.username as submitter_username
               FROM feedback JOIN users ON users.id = feedback.user_id
               WHERE feedback.status = 'pending' ORDER BY feedback.created_at ASC"""
        )

    async def set_feedback_status(self, feedback_id: int, status: str, admin_reason: str = None) -> Optional[dict]:
        feedback = await self.get_feedback(feedback_id)
        if not feedback:
            return None
        await self._execute(
            "UPDATE feedback SET status = ?, admin_reason = ?, resolved_at = datetime('now') WHERE id = ?",
            (status, admin_reason, feedback_id),
        )
        return feedback

    # --- Mod Applications ---
    async def add_application(self, user_id: int, experience: str, availability: str, why_you: str) -> int:
        return await self._execute(
            "INSERT INTO applications (user_id, experience, availability, why_you) VALUES (?, ?, ?, ?)",
            (user_id, experience, availability, why_you),
        )

    async def get_application(self, application_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT applications.*, users.username as submitter_username, users.telegram_id as submitter_telegram_id
               FROM applications JOIN users ON users.id = applications.user_id WHERE applications.id = ?""",
            (application_id,),
        )

    async def list_pending_applications(self) -> list[dict]:
        return await self._fetchall(
            """SELECT applications.*, users.username as submitter_username
               FROM applications JOIN users ON users.id = applications.user_id
               WHERE applications.status = 'pending' ORDER BY applications.created_at ASC"""
        )

    async def set_application_status(self, application_id: int, status: str, admin_reason: str = None) -> Optional[dict]:
        application = await self.get_application(application_id)
        if not application:
            return None
        await self._execute(
            "UPDATE applications SET status = ?, admin_reason = ?, resolved_at = datetime('now') WHERE id = ?",
            (status, admin_reason, application_id),
        )
        return application

    # --- Giveaway host requests (support-portal form) ---
    async def add_giveaway_request(self, user_id: int, details: str) -> int:
        return await self._execute(
            "INSERT INTO giveaway_requests (user_id, details) VALUES (?, ?)",
            (user_id, details),
        )

    # ================= LIVE GIVEAWAY ENGINE =================
    async def create_giveaway(self, chat_id: int, prize: str, hosted_by_user_id: int, conditions: str,
                               required_channels: str, ends_at: str) -> int:
        return await self._execute(
            """INSERT INTO giveaways (chat_id, prize, hosted_by_user_id, conditions, required_channels, ends_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (chat_id, prize, hosted_by_user_id, conditions, required_channels, ends_at),
        )

    async def set_giveaway_message_id(self, giveaway_id: int, message_id: int) -> None:
        await self._execute("UPDATE giveaways SET message_id = ? WHERE id = ?", (message_id, giveaway_id))

    async def get_giveaway(self, giveaway_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT giveaways.*, users.username as host_username
               FROM giveaways JOIN users ON users.id = giveaways.hosted_by_user_id
               WHERE giveaways.id = ?""",
            (giveaway_id,),
        )

    async def list_active_giveaways(self) -> list[dict]:
        return await self._fetchall(
            """SELECT giveaways.*, users.username as host_username
               FROM giveaways JOIN users ON users.id = giveaways.hosted_by_user_id
               WHERE giveaways.status = 'active'"""
        )

    async def add_giveaway_entry(self, giveaway_id: int, user_id: int) -> bool:
        """Returns True if newly entered, False if already entered."""
        existing = await self._fetchone(
            "SELECT id FROM giveaway_entries WHERE giveaway_id = ? AND user_id = ?",
            (giveaway_id, user_id),
        )
        if existing:
            return False
        await self._execute(
            "INSERT INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
            (giveaway_id, user_id),
        )
        return True

    async def count_giveaway_entries(self, giveaway_id: int) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) as c FROM giveaway_entries WHERE giveaway_id = ?", (giveaway_id,)
        )
        return row["c"] if row else 0

    async def pick_giveaway_winner(self, giveaway_id: int) -> Optional[dict]:
        """Picks a random entrant, marks giveaway ended, returns the winner user row (or None if no entries)."""
        row = await self._fetchone(
            """SELECT users.* FROM giveaway_entries
               JOIN users ON users.id = giveaway_entries.user_id
               WHERE giveaway_entries.giveaway_id = ?
               ORDER BY RANDOM() LIMIT 1""",
            (giveaway_id,),
        )
        await self._execute(
            "UPDATE giveaways SET status = 'ended', winner_user_id = ? WHERE id = ?",
            (row["id"] if row else None, giveaway_id),
        )
        return row

    async def giveaway_leaderboard(self, limit: int = 10) -> list[dict]:
        """Users ranked by number of giveaways won."""
        return await self._fetchall(
            """SELECT users.telegram_id, users.username, COUNT(*) as wins
               FROM giveaways JOIN users ON users.id = giveaways.winner_user_id
               WHERE giveaways.status = 'ended' AND giveaways.winner_user_id IS NOT NULL
               GROUP BY giveaways.winner_user_id ORDER BY wins DESC LIMIT ?""",
            (limit,),
        )

    # ================= MODERATOR SYSTEM =================
    async def create_community(self, name: str, link: str, description: str, owner_name: str) -> int:
        return await self._execute(
            "INSERT INTO communities (name, link, description, owner_name) VALUES (?, ?, ?, ?)",
            (name, link, description, owner_name),
        )

    async def get_community(self, community_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM communities WHERE id = ?", (community_id,))

    async def create_moderator(self, **fields) -> int:
        cols = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        return await self._execute(
            f"INSERT INTO moderators ({cols}) VALUES ({placeholders})",
            tuple(fields.values()),
        )

    async def list_moderators(self, active_only: bool = True) -> list[dict]:
        if active_only:
            return await self._fetchall(
                "SELECT * FROM moderators WHERE active_status = 1 ORDER BY reputation_score DESC"
            )
        return await self._fetchall("SELECT * FROM moderators ORDER BY id")

    async def get_moderator(self, moderator_id: int) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM moderators WHERE id = ?", (moderator_id,))

    async def get_moderator_by_username(self, username: str) -> Optional[dict]:
        return await self._fetchone("SELECT * FROM moderators WHERE username = ?", (username.lstrip("@"),))

    async def set_moderator_verification(self, moderator_id: int, status: str) -> None:
        await self._execute("UPDATE moderators SET verification_status = ? WHERE id = ?", (status, moderator_id))

    async def set_moderator_active(self, moderator_id: int, active: bool) -> None:
        await self._execute("UPDATE moderators SET active_status = ? WHERE id = ?", (1 if active else 0, moderator_id))

    async def recalculate_reputation(self, moderator_id: int) -> None:
        row = await self._fetchone(
            "SELECT AVG(rating) as avg_rating FROM reviews WHERE moderator_id = ? AND status = 'approved'",
            (moderator_id,),
        )
        avg = row["avg_rating"] if row and row["avg_rating"] is not None else 0
        await self._execute("UPDATE moderators SET reputation_score = ? WHERE id = ?", (round(avg, 2), moderator_id))

    async def add_service(self, moderator_id: int, name: str, description: str = "") -> int:
        return await self._execute(
            "INSERT INTO services (moderator_id, name, description) VALUES (?, ?, ?)",
            (moderator_id, name, description),
        )

    async def list_services(self, moderator_id: int) -> list[dict]:
        return await self._fetchall("SELECT * FROM services WHERE moderator_id = ?", (moderator_id,))

    async def has_reviewed(self, user_id: int, moderator_id: int) -> bool:
        row = await self._fetchone(
            "SELECT id FROM reviews WHERE user_id = ? AND moderator_id = ? AND status != 'rejected'",
            (user_id, moderator_id),
        )
        return row is not None

    async def add_review(self, user_id: int, moderator_id: int, rating: int, text: str, category: str) -> int:
        return await self._execute(
            """INSERT INTO reviews (user_id, moderator_id, rating, review_text, service_category)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, moderator_id, rating, text, category),
        )

    async def list_reviews(self, moderator_id: int, status: str = "approved", limit: int = 10) -> list[dict]:
        return await self._fetchall(
            """SELECT reviews.*, users.username as reviewer_username
               FROM reviews JOIN users ON users.id = reviews.user_id
               WHERE moderator_id = ? AND status = ?
               ORDER BY reviews.created_at DESC LIMIT ?""",
            (moderator_id, status, limit),
        )

    async def count_reviews(self, moderator_id: int, status: str = "approved") -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) as c FROM reviews WHERE moderator_id = ? AND status = ?",
            (moderator_id, status),
        )
        return row["c"] if row else 0

    async def get_review_with_details(self, review_id: int) -> Optional[dict]:
        return await self._fetchone(
            """SELECT reviews.*, users.username as reviewer_username, moderators.display_name as mod_name
               FROM reviews JOIN users ON users.id = reviews.user_id
               JOIN moderators ON moderators.id = reviews.moderator_id WHERE reviews.id = ?""",
            (review_id,),
        )

    async def list_pending_reviews(self) -> list[dict]:
        return await self._fetchall(
            """SELECT reviews.*, users.username as reviewer_username, moderators.display_name as mod_name
               FROM reviews
               JOIN users ON users.id = reviews.user_id
               JOIN moderators ON moderators.id = reviews.moderator_id
               WHERE reviews.status = 'pending' ORDER BY reviews.created_at ASC"""
        )

    async def set_review_status(self, review_id: int, status: str) -> Optional[dict]:
        review = await self._fetchone("SELECT * FROM reviews WHERE id = ?", (review_id,))
        if not review:
            return None
        await self._execute("UPDATE reviews SET status = ? WHERE id = ?", (status, review_id))
        if status == "approved":
            await self.recalculate_reputation(review["moderator_id"])
        return review

    # ================= RANK / XP / STREAK =================
    async def register_message(self, telegram_id: int, chat_id: int, xp_gain: int, cooldown_seconds: int) -> bool:
        """
        Called on every group message. Increments total_messages and today's
        daily_activity row always; grants XP only if the per-user cooldown has
        elapsed. Returns True if XP was granted (i.e. not on cooldown).
        """
        now = dt.datetime.utcnow()
        today = now.strftime("%Y-%m-%d")

        row = await self._fetchone(
            "SELECT * FROM user_stats WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id)
        )
        xp_granted = True
        if row and row["last_xp_at"]:
            last_xp = dt.datetime.fromisoformat(row["last_xp_at"])
            if (now - last_xp).total_seconds() < cooldown_seconds:
                xp_granted = False

        if row is None:
            await self._execute(
                """INSERT INTO user_stats (telegram_id, chat_id, total_messages, xp, level, last_message_at, last_xp_at)
                   VALUES (?, ?, 1, ?, 0, ?, ?)""",
                (telegram_id, chat_id, xp_gain, now.isoformat(), now.isoformat()),
            )
        else:
            new_xp = row["xp"] + (xp_gain if xp_granted else 0)
            await self._execute(
                """UPDATE user_stats SET total_messages = total_messages + 1, xp = ?,
                   last_message_at = ?, last_xp_at = ? WHERE telegram_id = ? AND chat_id = ?""",
                (new_xp, now.isoformat(), now.isoformat() if xp_granted else row["last_xp_at"], telegram_id, chat_id),
            )

        # Daily activity (for leaderboards + streaks)
        existing_day = await self._fetchone(
            "SELECT id FROM daily_activity WHERE telegram_id = ? AND chat_id = ? AND activity_date = ?",
            (telegram_id, chat_id, today),
        )
        if existing_day:
            await self._execute(
                "UPDATE daily_activity SET message_count = message_count + 1 WHERE id = ?", (existing_day["id"],)
            )
        else:
            await self._execute(
                "INSERT INTO daily_activity (telegram_id, chat_id, activity_date, message_count) VALUES (?, ?, ?, 1)",
                (telegram_id, chat_id, today),
            )

        await self._update_streak(telegram_id, chat_id, today)
        return xp_granted

    async def _update_streak(self, telegram_id: int, chat_id: int, today: str) -> None:
        row = await self._fetchone(
            "SELECT * FROM streaks WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id)
        )
        if row is None:
            await self._execute(
                """INSERT INTO streaks (telegram_id, chat_id, current_streak, best_streak,
                   best_streak_start, best_streak_end, last_active_date)
                   VALUES (?, ?, 1, 1, ?, ?, ?)""",
                (telegram_id, chat_id, today, today, today),
            )
            return

        if row["last_active_date"] == today:
            return  # already counted today

        yesterday = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
        if row["last_active_date"] == yesterday:
            new_streak = row["current_streak"] + 1
            streak_start = row["best_streak_start"]
        else:
            new_streak = 1
            streak_start = today

        best_streak = row["best_streak"]
        best_start = row["best_streak_start"]
        best_end = row["best_streak_end"]
        if new_streak >= best_streak:
            best_streak = new_streak
            best_start = streak_start if new_streak > 1 else today
            best_end = today

        await self._execute(
            """UPDATE streaks SET current_streak = ?, best_streak = ?, best_streak_start = ?,
               best_streak_end = ?, last_active_date = ? WHERE telegram_id = ? AND chat_id = ?""",
            (new_streak, best_streak, best_start, best_end, today, telegram_id, chat_id),
        )

    async def get_user_stats(self, telegram_id: int, chat_id: int) -> Optional[dict]:
        return await self._fetchone(
            "SELECT * FROM user_stats WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id)
        )

    async def get_user_rank_position(self, telegram_id: int, chat_id: int) -> tuple[int, int]:
        """Returns (rank_position, total_ranked_users) ordered by total_messages desc."""
        rows = await self._fetchall(
            "SELECT telegram_id FROM user_stats WHERE chat_id = ? ORDER BY total_messages DESC", (chat_id,)
        )
        total = len(rows)
        for idx, r in enumerate(rows, start=1):
            if r["telegram_id"] == telegram_id:
                return idx, total
        return total + 1, total

    async def get_streak(self, telegram_id: int, chat_id: int) -> Optional[dict]:
        return await self._fetchone(
            "SELECT * FROM streaks WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id)
        )

    async def get_top_chatters(self, chat_id: int, start_date: str, end_date: str, limit: int = 3) -> list[dict]:
        return await self._fetchall(
            """SELECT daily_activity.telegram_id, users.username, users.first_name,
                      SUM(daily_activity.message_count) as total
               FROM daily_activity
               LEFT JOIN users ON users.telegram_id = daily_activity.telegram_id
               WHERE daily_activity.chat_id = ? AND daily_activity.activity_date BETWEEN ? AND ?
               GROUP BY daily_activity.telegram_id ORDER BY total DESC LIMIT ?""",
            (chat_id, start_date, end_date, limit),
        )

    # ================= REPUTATION =================
    async def can_give_rep(self, giver_telegram_id: int, chat_id: int, cooldown_hours: int) -> bool:
        row = await self._fetchone(
            """SELECT given_at FROM rep_log WHERE giver_telegram_id = ? AND chat_id = ?
               ORDER BY given_at DESC LIMIT 1""",
            (giver_telegram_id, chat_id),
        )
        if not row:
            return True
        last_given = dt.datetime.fromisoformat(row["given_at"])
        return (dt.datetime.utcnow() - last_given).total_seconds() >= cooldown_hours * 3600

    async def give_rep(self, giver_telegram_id: int, receiver_telegram_id: int, chat_id: int) -> int:
        await self._execute(
            "INSERT INTO rep_log (giver_telegram_id, receiver_telegram_id, chat_id) VALUES (?, ?, ?)",
            (giver_telegram_id, receiver_telegram_id, chat_id),
        )
        row = await self._fetchone(
            "SELECT * FROM reputation WHERE telegram_id = ? AND chat_id = ?", (receiver_telegram_id, chat_id)
        )
        if row:
            await self._execute(
                "UPDATE reputation SET rep_points = rep_points + 1 WHERE telegram_id = ? AND chat_id = ?",
                (receiver_telegram_id, chat_id),
            )
            return row["rep_points"] + 1
        await self._execute(
            "INSERT INTO reputation (telegram_id, chat_id, rep_points) VALUES (?, ?, 1)",
            (receiver_telegram_id, chat_id),
        )
        return 1

    async def get_reputation_leaderboard(self, chat_id: int, limit: int = 10) -> list[dict]:
        return await self._fetchall(
            """SELECT reputation.telegram_id, users.username, users.first_name, reputation.rep_points
               FROM reputation LEFT JOIN users ON users.telegram_id = reputation.telegram_id
               WHERE reputation.chat_id = ? ORDER BY reputation.rep_points DESC LIMIT ?""",
            (chat_id, limit),
        )

    async def get_user_reputation(self, telegram_id: int, chat_id: int) -> int:
        row = await self._fetchone(
            "SELECT rep_points FROM reputation WHERE telegram_id = ? AND chat_id = ?", (telegram_id, chat_id)
        )
        return row["rep_points"] if row else 0


db = Database(config.db_path)
