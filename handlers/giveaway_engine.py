"""
Live Giveaway Engine (separate from the "Host a Giveaway" support-portal
button, which just points users to DM the host).

Admin flow: /creategiveaway (DM to the bot, admin-only)
  1. "What's the prize?"
  2. "Any conditions? (one per line, or type 'none')"
  3. "How long should it run? (e.g. '3d', '12h', '30m')"
  4. Review -> Confirm/Cancel -> bot posts the giveaway into the main group
     with a "🎉 Participate!" button and live entry count.

Participation: tapping Participate! adds an entry and edits the post's
caption in place to show the updated entry count. Re-tapping shows an alert:
"You have already entered this giveaway."

A background task (utils/giveaway_scheduler.py) ends giveaways whose timer
has elapsed and announces a randomly-picked winner.
"""
import datetime as dt
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config
from database.db import db
from callbacks.factories import GiveawayEntryCallback, GiveawayCheckCallback
from keyboards.giveaway_engine import participate_keyboard, requirements_keyboard
from keyboards.main_menu import confirm_cancel_keyboard
from callbacks.factories import FormActionCallback
from states.forms import CreateGiveawayForm
from utils.giveaway_format import format_giveaway_caption, format_requirements_message

router = Router(name="giveaway_engine")

DURATION_RE = re.compile(r"^(\d+)\s*([dhm])$", re.IGNORECASE)


def _parse_duration(text: str) -> dt.timedelta | None:
    match = DURATION_RE.match(text.strip())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2).lower()
    if unit == "d":
        return dt.timedelta(days=amount)
    if unit == "h":
        return dt.timedelta(hours=amount)
    return dt.timedelta(minutes=amount)


def _parse_channels(text: str) -> list[str]:
    if text.strip().lower() == "none":
        return []
    return [c.strip().lstrip("@") for c in text.split(",") if c.strip()]


async def _missing_channels(bot, user_id: int, channels: list[str]) -> list[str]:
    """Returns the subset of `channels` the user has NOT joined."""
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(f"@{ch}", user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:
            # Bot isn't an admin in that channel, or user not found -> treat as not-joined.
            missing.append(ch)
    return missing


async def _require_admin(message_or_call) -> bool:
    user = message_or_call.from_user
    return await db.is_admin(user.id)


@router.message(Command("creategiveaway"))
async def start_create_giveaway(message: Message, state: FSMContext):
    if not await _require_admin(message):
        await message.answer("🚫 You're not authorized to use this command.")
        return
    if config.main_chat_id == 0:
        await message.answer(
            "⚠️ MAIN_CHAT_ID isn't configured yet — set it in your .env so I know "
            "which group to post giveaways into."
        )
        return
    await state.set_state(CreateGiveawayForm.waiting_for_prize)
    await message.answer("🎉 <b>Create a Giveaway</b>\n\nWhat's the prize?")


@router.message(CreateGiveawayForm.waiting_for_prize)
async def giveaway_prize_received(message: Message, state: FSMContext):
    await state.update_data(prize=message.text.strip())
    await state.set_state(CreateGiveawayForm.waiting_for_conditions)
    await message.answer("Any conditions to enter? (one per line, or type 'none')")


@router.message(CreateGiveawayForm.waiting_for_conditions)
async def giveaway_conditions_received(message: Message, state: FSMContext):
    conditions = "" if message.text.strip().lower() == "none" else message.text.strip()
    await state.update_data(conditions=conditions)
    await state.set_state(CreateGiveawayForm.waiting_for_required_channels)
    await message.answer(
        "Which channels/groups must users join to enter? "
        "(comma-separated usernames, e.g. 'nfthatz, goalboss', or type 'none')\n\n"
        "⚠️ The bot must be an admin in those channels/groups to verify membership."
    )


@router.message(CreateGiveawayForm.waiting_for_required_channels)
async def giveaway_required_channels_received(message: Message, state: FSMContext):
    channels = _parse_channels(message.text)
    await state.update_data(required_channels=",".join(channels))
    await state.set_state(CreateGiveawayForm.waiting_for_duration)
    await message.answer("How long should it run? (e.g. '3d', '12h', '30m')")


@router.message(CreateGiveawayForm.waiting_for_duration)
async def giveaway_duration_received(message: Message, state: FSMContext):
    delta = _parse_duration(message.text)
    if delta is None:
        await message.answer("Please use a format like '3d', '12h', or '30m'.")
        return
    await state.update_data(duration_text=message.text.strip(), duration_seconds=int(delta.total_seconds()))
    await state.set_state(CreateGiveawayForm.waiting_for_confirmation)
    data = await state.get_data()
    channels_display = data["required_channels"] or "none"
    summary = (
        f"<b>Prize:</b> {data['prize']}\n"
        f"<b>Conditions:</b> {data['conditions'] or 'none'}\n"
        f"<b>Must join:</b> {channels_display}\n"
        f"<b>Duration:</b> {data['duration_text']}\n\n"
        "Post this giveaway to the group now?"
    )
    await message.answer(summary, reply_markup=confirm_cancel_keyboard("creategiveaway", allow_anonymous=False))


@router.callback_query(FormActionCallback.filter((F.form == "creategiveaway") & (F.action == "confirm")))
async def giveaway_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    ends_at = (dt.datetime.utcnow() + dt.timedelta(seconds=data["duration_seconds"])).isoformat()

    giveaway_id = await db.create_giveaway(
        chat_id=config.main_chat_id,
        prize=data["prize"],
        hosted_by_user_id=user["id"],
        conditions=data["conditions"],
        required_channels=data["required_channels"],
        ends_at=ends_at,
    )
    giveaway = await db.get_giveaway(giveaway_id)
    caption = format_giveaway_caption(giveaway, entry_count=0)
    sent = await call.bot.send_message(
        config.main_chat_id, caption, reply_markup=participate_keyboard(giveaway_id)
    )
    await db.set_giveaway_message_id(giveaway_id, sent.message_id)

    await call.message.edit_text(f"✅ Giveaway posted to the group! (id #{giveaway_id})")
    await state.clear()
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "creategiveaway") & (F.action == "cancel")))
async def giveaway_create_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Giveaway creation cancelled.")
    await call.answer()


@router.callback_query(GiveawayEntryCallback.filter())
async def giveaway_participate(call: CallbackQuery, callback_data: GiveawayEntryCallback):
    giveaway = await db.get_giveaway(callback_data.giveaway_id)
    if not giveaway or giveaway["status"] != "active":
        await call.answer("This giveaway has ended.", show_alert=True)
        return

    required = [c for c in (giveaway.get("required_channels") or "").split(",") if c]
    if required:
        missing = await _missing_channels(call.bot, call.from_user.id, required)
        if missing:
            await call.message.answer(
                format_requirements_message(missing),
                reply_markup=requirements_keyboard(giveaway["id"], missing),
            )
            await call.answer()
            return

    await _enter_giveaway(call, giveaway)


@router.callback_query(GiveawayCheckCallback.filter())
async def giveaway_recheck(call: CallbackQuery, callback_data: GiveawayCheckCallback):
    giveaway = await db.get_giveaway(callback_data.giveaway_id)
    if not giveaway or giveaway["status"] != "active":
        await call.answer("This giveaway has ended.", show_alert=True)
        return

    required = [c for c in (giveaway.get("required_channels") or "").split(",") if c]
    missing = await _missing_channels(call.bot, call.from_user.id, required)
    if missing:
        await call.answer("You still haven't joined all required channels/groups.", show_alert=True)
        try:
            await call.message.edit_text(
                format_requirements_message(missing),
                reply_markup=requirements_keyboard(giveaway["id"], missing),
            )
        except Exception:
            pass
        return

    try:
        await call.message.delete()
    except Exception:
        pass
    await _enter_giveaway(call, giveaway)


async def _enter_giveaway(call: CallbackQuery, giveaway: dict) -> None:
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    newly_entered = await db.add_giveaway_entry(giveaway["id"], user["id"])

    if not newly_entered:
        await call.answer("You have already entered this giveaway.", show_alert=True)
        return

    entry_count = await db.count_giveaway_entries(giveaway["id"])
    caption = format_giveaway_caption(giveaway, entry_count=entry_count)
    if giveaway.get("message_id"):
        try:
            await call.bot.edit_message_text(
                chat_id=giveaway["chat_id"], message_id=giveaway["message_id"],
                text=caption, reply_markup=participate_keyboard(giveaway["id"]),
            )
        except Exception:
            pass
    await call.answer("✅ You're entered! Good luck!")
