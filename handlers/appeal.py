"""
Appeal flow — exact sequence confirmed against the reference bot:
  1. "Creating an appeal" + "What are you appealing?" [Mute] [Warning] [Ban]
  2. -> "Appealing: X" + "Why do you believe the punishment should be removed or reduced?"
  3. -> "Reason: Y" + "Is there anything else you'd like the staff to know? (or type 'none')"
  4. -> "Anything else: Z" + "Please review your answers. Submit to the admins?" [Confirm/Cancel]
     (no "Submit anonymously" option for appeals)
  5. Confirm -> sent to admin queue.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from callbacks.factories import NavCallback, FormActionCallback, AppealTypeCallback
from keyboards.main_menu import confirm_cancel_keyboard
from keyboards.appeal import appeal_type_keyboard
from states.forms import AppealForm
from utils.session import is_locked, update_banner, update_banner_from_callback
from utils.admin_notify import notify_admins_new_appeal

router = Router(name="appeal")


def _caption(appealing: str = None, reason: str = None, anything_else: str = None, extra: str = "") -> str:
    lines = ["Creating an appeal"]
    if appealing is not None:
        lines.append(f"Appealing: {appealing}")
    if reason is not None:
        lines.append(f"Reason: {reason}")
    if anything_else is not None:
        lines.append(f"Anything else: {anything_else}")
    caption = "\n".join(lines)
    if extra:
        caption += f"\n\n{extra}"
    return caption


@router.callback_query(NavCallback.filter(F.target == "appeal"))
async def start_appeal(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    await state.set_state(AppealForm.waiting_for_appealing)
    caption = _caption(extra="What are you appealing?")
    await call.message.edit_caption(caption=caption, reply_markup=appeal_type_keyboard())
    await state.update_data(
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )
    await call.answer()


@router.callback_query(AppealForm.waiting_for_appealing, AppealTypeCallback.filter())
async def appeal_type_chosen(call: CallbackQuery, callback_data: AppealTypeCallback, state: FSMContext):
    await state.update_data(appealing=callback_data.kind)
    await state.set_state(AppealForm.waiting_for_reason)
    caption = _caption(
        appealing=callback_data.kind,
        extra="Why do you believe the punishment should be removed or reduced?",
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await call.answer()


@router.message(AppealForm.waiting_for_reason)
async def appeal_reason_received(message: Message, state: FSMContext):
    reason = message.text.strip()
    await state.update_data(reason=reason)
    await state.set_state(AppealForm.waiting_for_anything_else)
    data = await state.get_data()
    caption = _caption(
        appealing=data["appealing"], reason=reason,
        extra="Is there anything else you'd like the staff to know? (or type 'none')",
    )
    await update_banner(message.bot, state, caption)


@router.message(AppealForm.waiting_for_anything_else)
async def appeal_anything_else_received(message: Message, state: FSMContext):
    anything_else = message.text.strip()
    await state.update_data(anything_else=anything_else)
    await state.set_state(AppealForm.waiting_for_confirmation)
    data = await state.get_data()
    caption = _caption(
        appealing=data["appealing"], reason=data["reason"], anything_else=anything_else,
        extra="Please review your answers. Submit to the admins?",
    )
    await update_banner(message.bot, state, caption, confirm_cancel_keyboard("appeal", allow_anonymous=False))


@router.callback_query(FormActionCallback.filter((F.form == "appeal") & (F.action == "confirm")))
async def appeal_confirm(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    appeal_id = await db.add_appeal(
        user_id=user["id"],
        appealing=data["appealing"],
        reason=data["reason"],
        anything_else=data["anything_else"],
    )
    caption = _caption(
        appealing=data["appealing"], reason=data["reason"], anything_else=data["anything_else"],
        extra="✅ Sent to the admins — thank you! Send /start to submit another.",
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await state.clear()

    appeal = await db.get_appeal(appeal_id)
    await notify_admins_new_appeal(call.bot, appeal)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "appeal") & (F.action == "cancel")))
async def appeal_cancel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    caption = data.get("banner_caption", "Creating an appeal")
    caption += "\n\n❌ Cancelled. Send /start to begin again."
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.clear()
    await call.answer()
