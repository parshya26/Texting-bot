"""
Background loop that checks every 30 seconds for giveaways whose timer has
run out, picks a random winner from the entrants, edits the original post to
show "Ended", and sends a winner announcement into the group.
"""
import asyncio
import datetime as dt
import logging

from aiogram import Bot

from database.db import db
from utils.giveaway_format import format_giveaway_caption, format_winner_announcement
from keyboards.giveaway_engine import participate_keyboard

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30


async def _end_giveaway(bot: Bot, giveaway: dict) -> None:
    winner = await db.pick_giveaway_winner(giveaway["id"])
    entry_count = await db.count_giveaway_entries(giveaway["id"])

    if giveaway.get("message_id"):
        ended_caption = format_giveaway_caption(giveaway, entry_count=entry_count, ended=True)
        try:
            await bot.edit_message_text(
                chat_id=giveaway["chat_id"],
                message_id=giveaway["message_id"],
                text=ended_caption,
                reply_markup=None,
            )
        except Exception:
            logger.exception("Failed to edit ended giveaway message %s", giveaway["id"])

    try:
        await bot.send_message(giveaway["chat_id"], format_winner_announcement(giveaway, winner))
    except Exception:
        logger.exception("Failed to announce winner for giveaway %s", giveaway["id"])


async def giveaway_watcher(bot: Bot) -> None:
    """Run forever as a background asyncio task started alongside polling."""
    while True:
        try:
            active = await db.list_active_giveaways()
            now = dt.datetime.utcnow()
            for giveaway in active:
                ends_at = dt.datetime.fromisoformat(giveaway["ends_at"])
                if now >= ends_at:
                    await _end_giveaway(bot, giveaway)
        except Exception:
            logger.exception("Error in giveaway_watcher loop")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
