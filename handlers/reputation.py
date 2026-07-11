"""
/rep  -> reply to someone's message with /rep to give them +1 reputation.
         Enforced: no self-rep, 1 rep per giver per 24 hours.
/reps -> posts the reputation leaderboard image (gold/silver/bronze rows,
         crown on #1), scoped to config.main_chat_id.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from config import config
from database.db import db
from utils.rank_cards import render_reputation_leaderboard_card

router = Router(name="reputation")

COOLDOWN_MESSAGE = "You can only give 1 rep per 24 hours. Try again later."


async def _guard_wrong_chat(message: Message) -> bool:
    if config.main_chat_id == 0:
        await message.answer("⚠️ MAIN_CHAT_ID isn't configured yet.")
        return True
    if message.chat.id != config.main_chat_id:
        await message.answer("This command only works in the main group.")
        return True
    return False


@router.message(Command("rep"))
async def cmd_rep(message: Message):
    if await _guard_wrong_chat(message):
        return

    if not message.reply_to_message:
        await message.answer("Reply to someone's message with /rep to give them reputation.")
        return

    giver = message.from_user
    target = message.reply_to_message.from_user

    if target.id == giver.id:
        await message.answer("You can't give reputation to yourself.")
        return
    if target.is_bot:
        await message.answer("You can't give reputation to a bot.")
        return

    await db.get_or_create_user(giver.id, giver.username or "", giver.first_name or "")
    await db.get_or_create_user(target.id, target.username or "", target.first_name or "")

    can_give = await db.can_give_rep(giver.id, config.main_chat_id, config.rep_cooldown_hours)
    if not can_give:
        await message.answer(COOLDOWN_MESSAGE)
        return

    new_total = await db.give_rep(giver.id, target.id, config.main_chat_id)
    name = f"@{target.username}" if target.username else (target.first_name or "them")
    await message.answer(f"✅ +1 reputation to {name}! They now have {new_total} rep.")


@router.message(Command("reps"))
async def cmd_reps(message: Message):
    if await _guard_wrong_chat(message):
        return

    rows = await db.get_reputation_leaderboard(config.main_chat_id, limit=10)
    if not rows:
        await message.answer("No reputation has been given yet.")
        return

    entries = [
        {"name": r.get("username") or r.get("first_name") or "Member", "rep": r["rep_points"]}
        for r in rows
    ]
    image_bytes = render_reputation_leaderboard_card(entries)
    await message.answer_photo(BufferedInputFile(image_bytes, filename="reps.png"))
