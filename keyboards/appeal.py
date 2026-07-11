from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.factories import AppealTypeCallback

APPEAL_TYPES = ["Mute", "Warning", "Ban"]


def appeal_type_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for kind in APPEAL_TYPES:
        b.button(text=kind, callback_data=AppealTypeCallback(kind=kind))
    b.adjust(1)
    return b.as_markup()
