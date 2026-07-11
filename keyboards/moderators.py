from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.factories import NavCallback, ModeratorCallback, ReviewCallback, ReviewCategoryCallback

SERVICE_CATEGORIES = ["Instagram unban", "Middleman", "Account recovery", "Dispute help", "Other"]


def moderators_list_keyboard(moderators: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in moderators:
        badge = "✅ " if m["verification_status"] in ("verified", "trusted") else ""
        b.button(
            text=f"{badge}{m['display_name']}",
            callback_data=ModeratorCallback(action="profile", mod_id=m["id"]),
        )
    b.adjust(1)
    b.button(text="🏠 Back to Home", callback_data=NavCallback(target="home"))
    b.adjust(1)
    return b.as_markup()


def moderator_profile_keyboard(mod: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛠️ Services", callback_data=ModeratorCallback(action="services", mod_id=mod["id"]))
    b.button(text="💬 Reviews", callback_data=ModeratorCallback(action="reviews", mod_id=mod["id"]))
    b.button(text="✍️ Leave a Review", callback_data=ReviewCallback(action="start", mod_id=mod["id"]))
    if mod.get("contact_username"):
        b.button(text=f"✉️ Contact @{mod['contact_username']}", url=f"https://t.me/{mod['contact_username']}")
    b.button(text="⬅️ Back to Moderators", callback_data=NavCallback(target="moderators"))
    b.adjust(2, 1, 1, 1)
    return b.as_markup()


def back_to_moderator_keyboard(mod_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Back to Profile", callback_data=ModeratorCallback(action="profile", mod_id=mod_id))
    b.button(text="🏠 Home", callback_data=NavCallback(target="home"))
    b.adjust(1)
    return b.as_markup()


def review_category_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for idx, cat in enumerate(SERVICE_CATEGORIES):
        b.button(text=cat, callback_data=ReviewCategoryCallback(category_index=idx))
    b.adjust(1)
    return b.as_markup()


def rating_keyboard(mod_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i in range(1, 6):
        b.button(text="⭐" * i, callback_data=ReviewCallback(action="rate", mod_id=mod_id, rating=i))
    b.adjust(1)
    return b.as_markup()
