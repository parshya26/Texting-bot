"""
/rank    -> current level, XP progress bar, rank position, message count
/streak  -> current streak, best streak, best streak date range
/daily /weekly /monthly -> Top 3 Chatters podium image for that period

All numbers are scoped to config.main_chat_id only (no cross-group/global
data), matching what was specified. Every command works when used in the
group itself; running it elsewhere returns a friendly notice.
"""
import datetime as dt
import math

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from config import config
from database.db import db
from utils.rank_cards import render_rank_card, render_streak_card, render_leaderboard_card
from utils.telegram_helpers import fetch_avatar_bytes

router = Router(name="rank")


def _compute_level(xp: int) -> tuple[int, int, int]:
    """Returns (level, xp_into_current_level, xp_needed_for_next_level)."""
    divisor = config.xp_curve_divisor
    level = int(math.sqrt(xp / divisor)) if xp > 0 else 0
    xp_at_level = (level ** 2) * divisor
    xp_at_next = ((level + 1) ** 2) * divisor
    return level, xp - xp_at_level, xp_at_next - xp_at_level


async def _guard_wrong_chat(message: Message) -> bool:
    if config.main_chat_id == 0:
        await message.answer("⚠️ MAIN_CHAT_ID isn't configured yet.")
        return True
    if message.chat.id != config.main_chat_id:
        await message.answer("This command only works in the main group.")
        return True
    return False


@router.message(Command("rank"))
async def cmd_rank(message: Message):
    if await _guard_wrong_chat(message):
        return

    user = message.from_user
    stats = await db.get_user_stats(user.id, config.main_chat_id)
    if not stats:
        await message.answer("You haven't sent any messages here yet — say something first!")
        return

    level, xp_into, xp_next = _compute_level(stats["xp"])
    rank_pos, total = await db.get_user_rank_position(user.id, config.main_chat_id)
    reputation = await db.get_user_reputation(user.id, config.main_chat_id)
    avatar_bytes = await fetch_avatar_bytes(message.bot, user.id)

    image_bytes = render_rank_card(
        display_name=user.first_name or user.username or "Member",
        username=user.username or "",
        level=level,
        xp_into_level=xp_into,
        xp_for_next_level=xp_next,
        rank_position=rank_pos,
        total_ranked=total,
        total_messages=stats["total_messages"],
        reputation=reputation,
        avatar_bytes=avatar_bytes,
    )
    await message.answer_photo(BufferedInputFile(image_bytes, filename="rank.png"))


@router.message(Command("streak"))
async def cmd_streak(message: Message):
    if await _guard_wrong_chat(message):
        return

    user = message.from_user
    streak = await db.get_streak(user.id, config.main_chat_id)
    if not streak:
        await message.answer("No activity recorded yet — say something first!")
        return

    if streak["best_streak_start"] and streak["best_streak_end"]:
        start = dt.date.fromisoformat(streak["best_streak_start"]).strftime("%b. %-d")
        end = dt.date.fromisoformat(streak["best_streak_end"]).strftime("%b. %-d")
        streak_range = f"{start} - {end}"
    else:
        streak_range = "—"

    stats = await db.get_user_stats(user.id, config.main_chat_id)
    total_messages = stats["total_messages"] if stats else 0

    avatar_bytes = await fetch_avatar_bytes(message.bot, user.id)
    image_bytes = render_streak_card(
        display_name=user.first_name or user.username or "Member",
        username=user.username or "",
        current_streak=streak["current_streak"],
        best_streak=streak["best_streak"],
        best_streak_range=streak_range,
        total_messages=total_messages,
        avatar_bytes=avatar_bytes,
    )
    await message.answer_photo(BufferedInputFile(image_bytes, filename="streak.png"))


async def _leaderboard(message: Message, days: int, label: str) -> None:
    if await _guard_wrong_chat(message):
        return

    end_date = dt.date.today()
    start_date = end_date - dt.timedelta(days=days - 1)
    top = await db.get_top_chatters(config.main_chat_id, start_date.isoformat(), end_date.isoformat(), limit=3)
    if not top:
        await message.answer("No activity recorded for this period yet.")
        return

    entries = []
    for row in top:
        avatar_bytes = await fetch_avatar_bytes(message.bot, row["telegram_id"])
        name = row.get("username") or row.get("first_name") or "Member"
        entries.append({"name": name, "username": row.get("username"), "value": row["total"], "avatar_bytes": avatar_bytes})

    subtitle = f"{start_date.strftime('%b. %-d, %Y')} - {end_date.strftime('%b. %-d, %Y')}"
    image_bytes = render_leaderboard_card(f"Top 3 Chatters ({label})", subtitle, entries)
    await message.answer_photo(BufferedInputFile(image_bytes, filename="leaderboard.png"))


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    await _leaderboard(message, days=1, label="Daily")


@router.message(Command("weekly"))
async def cmd_weekly(message: Message):
    await _leaderboard(message, days=7, label="Weekly")


@router.message(Command("monthly"))
async def cmd_monthly(message: Message):
    await _leaderboard(message, days=30, label="Monthly")
