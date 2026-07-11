"""
Host a Giveaway — in the reference bot this button opens no form at all,
just a static message pointing the user to DM the giveaway host. Kept
byte-for-byte matching (only the contact username is configurable).
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config
from callbacks.factories import NavCallback
from utils.session import is_locked

router = Router(name="giveaway")


@router.callback_query(NavCallback.filter(F.target == "giveaway"))
async def show_giveaway_contact(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    caption = f"Want to host a giveaway? Please private message @{config.giveaway_host_contact} to set it up."
    await call.message.edit_caption(caption=caption, reply_markup=None)
    await call.answer()
