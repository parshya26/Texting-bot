"""
Passive message tracker — runs for every message sent in the configured
main group chat (config.main_chat_id) and feeds it into the rank/XP/streak
system. Does nothing in private chats (those are handled by the form
routers) and does nothing until MAIN_CHAT_ID is configured.

This must be registered in bot.py so it only touches group messages
(commands still work independently via their own routers, aiogram allows
multiple handlers to see the same update).
"""
import logging
import random

from aiogram import Router, F
from aiogram.types import Message

from config import config
from database.db import db

router = Router(name="message_tracker")
logger = logging.getLogger(__name__)


@router.message(F.chat.id == config.main_chat_id, F.text, ~F.text.startswith("/"))
async def track_message(message: Message) -> None:
    if config.main_chat_id == 0:
        return
    try:
        await db.get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "")
        await db.register_message(
            telegram_id=message.from_user.id,
            chat_id=message.chat.id,
            xp_gain=random.randint(config.xp_per_message_min, config.xp_per_message_max),
            cooldown_seconds=config.xp_cooldown_seconds,
        )
    except Exception:
        # Never let a tracking hiccup take down message processing for
        # anything else the dispatcher needs to do with this update.
        logger.exception("Failed to register message for user %s", message.from_user.id)
