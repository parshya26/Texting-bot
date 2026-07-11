"""
Suggest flow — exact sequence confirmed against the reference bot:
  1. "Creating a suggestion" + "What's your giveaway or event idea?"
  2. -> "Idea: X" + "How would it work?"
  3. -> "How it works: Y" + "Suggested prize(s)? (if applicable, or type 'none')"
  4. -> "Prizes: Z" + "Why do you think the community would enjoy it?"
  5. -> "Why: W" + "Please review your answers. Submit to the admins?" [Confirm/Cancel] [Submit anonymously]
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from callbacks.factories import NavCallback, FormActionCallback
from keyboards.main_menu import confirm_cancel_keyboard
from states.forms import SuggestForm
from utils.session import is_locked, update_banner, update_banner_from_callback
from utils.admin_notify import notify_admins_new_suggestion

router = Router(name="suggest")


def _caption(idea=None, how_it_works=None, prizes=None, why=None, extra: str = "") -> str:
    lines = ["Creating a suggestion"]
    if idea is not None:
        lines.append(f"Idea: {idea}")
    if how_it_works is not None:
        lines.append(f"How it works: {how_it_works}")
    if prizes is not None:
        lines.append(f"Prizes: {prizes}")
    if why is not None:
        lines.append(f"Why: {why}")
    caption = "\n".join(lines)
    if extra:
        caption += f"\n\n{extra}"
    return caption


@router.callback_query(NavCallback.filter(F.target == "suggest"))
async def start_suggest(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    await state.set_state(SuggestForm.waiting_for_idea)
    caption = _caption(extra="What's your giveaway or event idea?")
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.update_data(
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )
    await call.answer()


@router.message(SuggestForm.waiting_for_idea)
async def suggest_idea_received(message: Message, state: FSMContext):
    idea = message.text.strip()
    await state.update_data(idea=idea)
    await state.set_state(SuggestForm.waiting_for_how_it_works)
    caption = _caption(idea=idea, extra="How would it work?")
    await update_banner(message.bot, state, caption)


@router.message(SuggestForm.waiting_for_how_it_works)
async def suggest_how_it_works_received(message: Message, state: FSMContext):
    how_it_works = message.text.strip()
    await state.update_data(how_it_works=how_it_works)
    await state.set_state(SuggestForm.waiting_for_prizes)
    data = await state.get_data()
    caption = _caption(
        idea=data["idea"], how_it_works=how_it_works,
        extra="Suggested prize(s)? (if applicable, or type 'none')",
    )
    await update_banner(message.bot, state, caption)


@router.message(SuggestForm.waiting_for_prizes)
async def suggest_prizes_received(message: Message, state: FSMContext):
    prizes = message.text.strip()
    await state.update_data(prizes=prizes)
    await state.set_state(SuggestForm.waiting_for_why)
    data = await state.get_data()
    caption = _caption(
        idea=data["idea"], how_it_works=data["how_it_works"], prizes=prizes,
        extra="Why do you think the community would enjoy it?",
    )
    await update_banner(message.bot, state, caption)


@router.message(SuggestForm.waiting_for_why)
async def suggest_why_received(message: Message, state: FSMContext):
    why = message.text.strip()
    await state.update_data(why=why)
    await state.set_state(SuggestForm.waiting_for_confirmation)
    data = await state.get_data()
    caption = _caption(
        idea=data["idea"], how_it_works=data["how_it_works"], prizes=data["prizes"], why=why,
        extra="Please review your answers. Submit to the admins?",
    )
    await update_banner(message.bot, state, caption, confirm_cancel_keyboard("suggest", allow_anonymous=True))


async def _submit_suggestion(call: CallbackQuery, state: FSMContext, anonymous: bool) -> None:
    data = await state.get_data()
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    suggestion_id = await db.add_suggestion(
        user_id=user["id"],
        idea=data["idea"], how_it_works=data["how_it_works"], prizes=data["prizes"], why=data["why"],
        anonymous=anonymous,
    )
    caption = _caption(
        idea=data["idea"], how_it_works=data["how_it_works"], prizes=data["prizes"], why=data["why"],
        extra="✅ Sent to the admins — thank you! Send /start to submit another.",
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await state.clear()

    suggestion = await db.get_suggestion(suggestion_id)
    await notify_admins_new_suggestion(call.bot, suggestion)


@router.callback_query(FormActionCallback.filter((F.form == "suggest") & (F.action == "confirm")))
async def suggest_confirm(call: CallbackQuery, state: FSMContext):
    await _submit_suggestion(call, state, anonymous=False)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "suggest") & (F.action == "anonymous")))
async def suggest_anonymous(call: CallbackQuery, state: FSMContext):
    await _submit_suggestion(call, state, anonymous=True)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "suggest") & (F.action == "cancel")))
async def suggest_cancel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    caption = data.get("banner_caption", "Creating a suggestion")
    caption += "\n\n❌ Cancelled. Send /start to begin again."
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.clear()
    await call.answer()
