"""
Core mechanic shared by every multi-step form:

1. THE "SAME MESSAGE" UI — each form sends ONE photo (the banner) and then
   only ever edits that message's caption/keyboard as the user answers
   questions. `start_banner()` sends it; `update_banner()` edits it.

2. ONE-ACTIVE-REQUEST-AT-A-TIME — while a user has an FSM state set, no other
   form/button may start. `is_locked()` / `warn_locked()` implement the
   "You're already in the middle of a support request..." behaviour.

3. /cancel — appends "❌ Cancelled. Send /start to begin again." to whatever
   the banner caption currently says, strips the keyboard, and clears state.
   This lives in handlers/start.py but relies on the state data this module
   writes (`banner_chat_id`, `banner_message_id`, `banner_caption`).
"""
from aiogram import Bot
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from config import config

LOCKED_MESSAGE = (
    "You're already in the middle of a support request. "
    "Send /cancel to discard it and start over."
)


def resolve_banner_photo():
    """
    BANNER_IMAGE_PATH can be either a direct image URL (https://...) or a
    local file path. Telegram's Bot API accepts both — a URL is passed as a
    plain string, a local file must be wrapped in FSInputFile.
    """
    path = config.banner_image_path
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return FSInputFile(path)


async def is_locked(state: FSMContext) -> bool:
    return (await state.get_state()) is not None


async def warn_locked(message: Message) -> None:
    await message.answer(LOCKED_MESSAGE)


async def start_banner(
    message: Message,
    state: FSMContext,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Sends the banner photo with an initial caption and remembers its id."""
    sent = await message.answer_photo(
        resolve_banner_photo(),
        caption=caption,
        reply_markup=reply_markup,
    )
    await state.update_data(
        banner_chat_id=sent.chat.id,
        banner_message_id=sent.message_id,
        banner_caption=caption,
    )


async def update_banner(
    bot: Bot,
    state: FSMContext,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edits the previously-sent banner message in place."""
    data = await state.get_data()
    chat_id = data.get("banner_chat_id")
    message_id = data.get("banner_message_id")
    if chat_id is None or message_id is None:
        return
    await bot.edit_message_caption(
        chat_id=chat_id,
        message_id=message_id,
        caption=caption,
        reply_markup=reply_markup,
    )
    await state.update_data(banner_caption=caption)


async def update_banner_from_callback(
    call,
    state: FSMContext,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Same as update_banner but used when we already have the callback's message object."""
    await call.message.edit_caption(caption=caption, reply_markup=reply_markup)
    await state.update_data(
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )


async def cancel_current_session(bot: Bot, state: FSMContext) -> bool:
    """
    Called by /cancel. Appends the cancellation notice to the existing banner
    caption and strips buttons. Returns True if a banner message was found
    and edited, False if there was nothing to cancel.
    """
    data = await state.get_data()
    chat_id = data.get("banner_chat_id")
    message_id = data.get("banner_message_id")
    caption = data.get("banner_caption", "")

    await state.clear()

    if chat_id is None or message_id is None:
        return False

    new_caption = f"{caption}\n\n❌ Cancelled. Send /start to begin again."
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=new_caption,
            reply_markup=None,
        )
    except Exception:
        pass
    return True
