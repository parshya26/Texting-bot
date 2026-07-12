"""
Apply for Mod flow:
  - If admin has applications CLOSED (default): shows the static reference-bot
    message and does NOT open any form.
      "We're currently not looking for new moderators.
       Send /start to choose something else."
  - If admin has applications OPEN: runs a 3-step form (experience,
    availability, why-you) ending in the usual Confirm/Cancel review step
    (no anonymous option — mod applications should be identifiable).
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from callbacks.factories import NavCallback, FormActionCallback
from keyboards.main_menu import confirm_cancel_keyboard
from states.forms import ApplyModForm
from utils.session import is_locked, update_banner, update_banner_from_callback, delete_user_message
from utils.admin_notify import notify_admins_new_application

router = Router(name="apply_mod")

CLOSED_TEXT = (
    "We're currently not looking for new moderators.\n\n"
    "Send /start to choose something else."
)


def _caption(experience=None, availability=None, why_you=None, extra: str = "") -> str:
    lines = ["Applying to become a moderator"]
    if experience is not None:
        lines.append(f"Experience: {experience}")
    if availability is not None:
        lines.append(f"Availability: {availability}")
    if why_you is not None:
        lines.append(f"Why you: {why_you}")
    caption = "\n".join(lines)
    if extra:
        caption += f"\n\n{extra}"
    return caption


@router.callback_query(NavCallback.filter(F.target == "apply_mod"))
async def start_apply_mod(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return

    if not await db.is_mod_applications_open():
        await call.message.edit_caption(caption=CLOSED_TEXT, reply_markup=None)
        await call.answer()
        return

    await state.set_state(ApplyModForm.waiting_for_experience)
    caption = _caption(extra="Tell us about your moderation experience (previous groups, roles, etc.):")
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.update_data(
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )
    await call.answer()


@router.message(ApplyModForm.waiting_for_experience)
async def apply_experience_received(message: Message, state: FSMContext):
    experience = message.text.strip()
    await delete_user_message(message)
    await state.update_data(experience=experience)
    await state.set_state(ApplyModForm.waiting_for_availability)
    caption = _caption(experience=experience, extra="What's your availability (hours/timezone)?")
    await update_banner(message.bot, state, caption)


@router.message(ApplyModForm.waiting_for_availability)
async def apply_availability_received(message: Message, state: FSMContext):
    availability = message.text.strip()
    await delete_user_message(message)
    await state.update_data(availability=availability)
    await state.set_state(ApplyModForm.waiting_for_why_you)
    data = await state.get_data()
    caption = _caption(
        experience=data["experience"], availability=availability,
        extra="Why would you be a good fit for the team?",
    )
    await update_banner(message.bot, state, caption)


@router.message(ApplyModForm.waiting_for_why_you)
async def apply_why_you_received(message: Message, state: FSMContext):
    why_you = message.text.strip()
    await delete_user_message(message)
    await state.update_data(why_you=why_you)
    await state.set_state(ApplyModForm.waiting_for_confirmation)
    data = await state.get_data()
    caption = _caption(
        experience=data["experience"], availability=data["availability"], why_you=why_you,
        extra="Please review your answers. Submit to the admins?",
    )
    await update_banner(message.bot, state, caption, confirm_cancel_keyboard("apply_mod", allow_anonymous=False))


@router.callback_query(FormActionCallback.filter((F.form == "apply_mod") & (F.action == "confirm")))
async def apply_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    application_id = await db.add_application(
        user_id=user["id"],
        experience=data["experience"], availability=data["availability"], why_you=data["why_you"],
    )
    caption = _caption(
        experience=data["experience"], availability=data["availability"], why_you=data["why_you"],
        extra="✅ Sent to the admins — thank you! Send /start to submit another.",
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await state.clear()

    application = await db.get_application(application_id)
    await notify_admins_new_application(call.bot, application)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "apply_mod") & (F.action == "cancel")))
async def apply_cancel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    caption = data.get("banner_caption", "Applying to become a moderator")
    caption += "\n\n❌ Cancelled. Send /start to begin again."
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.clear()
    await call.answer()
