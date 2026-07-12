"""
Feedback flow — exact sequence confirmed against the reference bot:
  1. "Submitting feedback" + intro paragraph inviting feedback, ending "Send us your thoughts below."
  2. -> "Feedback: X" + "Please review your answers. Submit to the admins?" [Confirm/Cancel] [Submit anonymously]
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config
from database.db import db
from callbacks.factories import NavCallback, FormActionCallback
from keyboards.main_menu import confirm_cancel_keyboard
from states.forms import FeedbackForm
from utils.session import is_locked, update_banner, update_banner_from_callback, delete_user_message
from utils.admin_notify import notify_admins_new_feedback

router = Router(name="feedback")

INTRO = (
    f"Have feedback or an idea to improve {config.community_handle}?\n\n"
    "Whether it's something you love, something you'd like changed, or a new "
    "feature you'd like to see — we're listening. Every submission is reviewed "
    "by the team.\n\n"
    "Send us your thoughts below."
)


def _caption(feedback_text: str = None, extra: str = "") -> str:
    lines = ["Submitting feedback"]
    if feedback_text is not None:
        lines.append(f"Feedback: {feedback_text}")
    else:
        lines.append(INTRO)
    caption = "\n".join(lines)
    if extra:
        caption += f"\n\n{extra}"
    return caption


@router.callback_query(NavCallback.filter(F.target == "feedback"))
async def start_feedback(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    await state.set_state(FeedbackForm.waiting_for_text)
    caption = _caption()
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.update_data(
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )
    await call.answer()


@router.message(FeedbackForm.waiting_for_text)
async def feedback_text_received(message: Message, state: FSMContext):
    text = message.text.strip()
    await delete_user_message(message)
    await state.update_data(feedback_text=text)
    await state.set_state(FeedbackForm.waiting_for_confirmation)
    caption = _caption(feedback_text=text, extra="Please review your answers. Submit to the admins?")
    await update_banner(message.bot, state, caption, confirm_cancel_keyboard("feedback", allow_anonymous=True))


async def _submit_feedback(call: CallbackQuery, state: FSMContext, anonymous: bool) -> None:
    data = await state.get_data()
    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    feedback_id = await db.add_feedback(user_id=user["id"], feedback_text=data["feedback_text"], anonymous=anonymous)
    caption = _caption(
        feedback_text=data["feedback_text"],
        extra="✅ Sent to the admins — thank you! Send /start to submit another.",
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await state.clear()

    feedback = await db.get_feedback(feedback_id)
    await notify_admins_new_feedback(call.bot, feedback)


@router.callback_query(FormActionCallback.filter((F.form == "feedback") & (F.action == "confirm")))
async def feedback_confirm(call: CallbackQuery, state: FSMContext):
    await _submit_feedback(call, state, anonymous=False)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "feedback") & (F.action == "anonymous")))
async def feedback_anonymous(call: CallbackQuery, state: FSMContext):
    await _submit_feedback(call, state, anonymous=True)
    await call.answer()


@router.callback_query(FormActionCallback.filter((F.form == "feedback") & (F.action == "cancel")))
async def feedback_cancel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    caption = data.get("banner_caption", "Submitting feedback")
    caption += "\n\n❌ Cancelled. Send /start to begin again."
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await state.clear()
    await call.answer()
