from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.factories import GiveawayEntryCallback, GiveawayCheckCallback


def participate_keyboard(giveaway_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🎉 Participate!", callback_data=GiveawayEntryCallback(giveaway_id=giveaway_id))
    return b.as_markup()


def requirements_keyboard(giveaway_id: int, channels: list[str]) -> InlineKeyboardMarkup:
    """Join @channel buttons (open the channel) plus a Done button to recheck membership."""
    b = InlineKeyboardBuilder()
    for ch in channels:
        b.button(text=f"Join @{ch}", url=f"https://t.me/{ch}")
    b.adjust(1)
    b.button(text="✅ Done", callback_data=GiveawayCheckCallback(giveaway_id=giveaway_id))
    b.adjust(*([1] * len(channels)), 1)
    return b.as_markup()
