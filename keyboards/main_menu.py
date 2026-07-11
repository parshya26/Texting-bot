from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.factories import NavCallback, FormActionCallback


def home_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Report", callback_data=NavCallback(target="report"))
    b.button(text="Appeal", callback_data=NavCallback(target="appeal"))
    b.button(text="Suggest", callback_data=NavCallback(target="suggest"))
    b.button(text="Feedback", callback_data=NavCallback(target="feedback"))
    b.button(text="Apply for Mod", callback_data=NavCallback(target="apply_mod"))
    b.button(text="Host a Giveaway", callback_data=NavCallback(target="giveaway"))
    b.button(text="Moderators", callback_data=NavCallback(target="moderators"))
    b.button(text="Owners", callback_data=NavCallback(target="owners"))
    b.adjust(2, 2, 1, 1, 2)
    return b.as_markup()


def confirm_cancel_keyboard(form: str, allow_anonymous: bool) -> InlineKeyboardMarkup:
    """The review-step keyboard used by Report/Suggest/Feedback (with anonymous)
    and Appeal (without anonymous)."""
    b = InlineKeyboardBuilder()
    b.button(text="✅ Confirm", callback_data=FormActionCallback(form=form, action="confirm"))
    b.button(text="✕ Cancel", callback_data=FormActionCallback(form=form, action="cancel"))
    if allow_anonymous:
        b.button(text="Submit anonymously", callback_data=FormActionCallback(form=form, action="anonymous"))
        b.adjust(2, 1)
    else:
        b.adjust(2)
    return b.as_markup()


def back_to_home_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Back to Home", callback_data=NavCallback(target="home"))
    return b.as_markup()
