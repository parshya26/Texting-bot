"""
Report flow — exact sequence confirmed against the reference bot:
  1. "Creating a report" + "What is the username of the member or admin you're reporting?"
  2. -> "Username: X" + "What is the reason for the report?"
  3. -> "Reason: Y" + "Any screenshots or proof? (optional, but recommended — paste links, or type 'none')"
  4. -> "Proof: Z" + "Please review your answers. Submit to the admins?" [Confirm/Cancel] [Submit anonymously]
  5. Confirm -> sent to admin queue. Anonymous -> same, but submitter identity hidden from admin view.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from callbacks.factories import NavCallback, FormActionCallback
from keyboards.main_menu import confirm_cancel_keyboard, back_to_home_keyboard
from states.forms import ReportForm
from utils.session import is_locked, warn_locked, start_banner, update_banner, update_banner_from_callback, delete_user_message
from utils.admin_notify import notify_admins_new_report

router = Router(name="report")


def _caption(username: str = None, reason: str = None, proof: str = None, extra: str = "") -> str:
    lines = ["Creating a report"]
    if username is not None:
        lines.append(f"Username: {username}")
    if reason is not None:
        lines.append(f"Reason: {reason}")
    if proof is not None:
        lines.append(f"Proof: {proof}")
    caption = "\n".join(lines)
    if extra:
        caption += f"\n\n{extra}"
    return caption


@router.callback_query(NavCallback.filter(F.target == "report"))
async def start_report(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    await state.set_state(ReportForm.waiting_for_username)
    caption = _caption(extra="What is the username of the member or admin you're reporting?")
    # The report starts from the home screen's photo message, so we edit it in place.
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.update_data(
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )
    await call.answer()


@router.message(ReportForm.waiting_for_username)
async def report_username_received(message: Message, state: FSMContext):
    username = message.text.strip()
    await delete_user_message(message)
    await state.update_data(username=username)
    await state.set_state(ReportForm.waiting_for_reason)
    caption = _caption(username=username, extra="What is the reason for the report?")
    await update_banner(message.bot, state, caption)


@router.message(ReportForm.waiting_for_reason)
async def report_reason_received(message: Message, state: FSMContext):
    reason = message.text.strip()
    await delete_user_message(message)
    await state.update_data(reason=reason)
    await state.set_state(ReportForm.waiting_for_proof)
    data = await state.get_data()
    caption = _caption(
        username=data["username"], reason=reason,
        extra="Any screenshots or proof? (optional, but recommended — paste links, or type 'none')",
    )
    await update_banner(message.bot, state, caption)


@router.message(ReportForm.waiting_for_proof)
async def report_proof_received(message: Message, state: FSMContext):
    proof = message.text.strip()
    await delete_user_message(message)
    await state.update_data(proof=proof)
    await state.set_state(ReportForm.waiting_for_confirmation)
    data = await state.get_data()
    caption = _caption(
        username=data["username"], reason=data["reason"], proof=proof,
        extra="Please review your answers. Submit to the admins?",
    )
    await update_banner(message.bot, state, caption, confirm_cancel_keyboard("report", allow_anonymous=True))


async def _submit_report(call: CallbackQuery, state: FSMContext, anonymous: bool) -> None:
    data = await state.get_data()
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    report_id = await db.add_report(
        user_id=user["id"],
        target_username=data["username"],
        reason=data["reason"],
        proof=data["proof"],
        anonymous=anonymous,
    )
    caption = _caption(
        username=data["username"], reason=data["reason"], proof=data["proof"],
        extra="✅ Sent to the admins — thank you! Send /start to submit another.",
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await state.clear()

    report = await db.get_report(report_id)
    await notify_admins_new_report(call.bot, report)


@router.callback_query(FormActionCallback.filter((F.form == "report") & (F.action == "confirm")))
async def report_confirm(call: CallbackQuery, state: FSMContext):
    await _submit_report(call, state, anonymous=False)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "report") & (F.action == "anonymous")))
async def report_anonymous(call: CallbackQuery, state: FSMContext):
    await _submit_report(call, state, anonymous=True)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "report") & (F.action == "cancel")))
async def report_cancel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    caption = data.get("banner_caption", "Creating a report")
    caption += "\n\n❌ Cancelled. Send /start to begin again."
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.clear()
    await call.answer()
