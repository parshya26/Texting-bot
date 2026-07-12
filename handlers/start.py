"""
Core entry-point handlers:
  /start   -> shows the banner + home menu (blocked if a form is in progress)
  /cancel  -> cancels whatever form is active
  home nav -> "🏠 Back to Home" button everywhere routes back here
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config
from database.db import db
from keyboards.main_menu import home_keyboard, back_to_home_keyboard
from callbacks.factories import NavCallback
from utils.session import is_locked, warn_locked, cancel_current_session, resolve_banner_photo

router = Router(name="start")

HOME_CAPTION = (
    f"Welcome to {config.community_handle} Support\n\n"
    "What do you need help with?"
)

OWNERS_CAPTION_EXTRA = "\n\n".join(
    [f"👑 <b>{o['display_name']}</b> — {o['contact']}" for o in config.owners]
)


async def _touch_user(tg_user) -> dict:
    return await db.get_or_create_user(tg_user.id, tg_user.username or "", tg_user.first_name or "")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await _touch_user(message.from_user)

    if await is_locked(state):
        await warn_locked(message)
        return

    await message.answer_photo(
        resolve_banner_photo(),
        caption=HOME_CAPTION,
        reply_markup=home_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    cancelled = await cancel_current_session(message.bot, state)
    if not cancelled:
        await message.answer("Nothing to cancel. Send /start to begin.")


@router.callback_query(NavCallback.filter(F.target == "home"))
async def nav_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_caption(caption=HOME_CAPTION, reply_markup=home_keyboard())
    await call.answer()


@router.callback_query(NavCallback.filter(F.target == "owners"))
async def nav_owners(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    caption = f"<b>👑 {config.community_name} Owners</b>\n\n{OWNERS_CAPTION_EXTRA}"
    await call.message.edit_caption(caption=caption, reply_markup=back_to_home_keyboard())
    await call.answer()
