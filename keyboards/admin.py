from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks.factories import AdminFormCallback, AdminReviewCallback, AdminModCallback, AdminApplyToggleCallback


def admin_form_keyboard(table: str, item_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Approve", callback_data=AdminFormCallback(table=table, action="approve", item_id=item_id))
    b.button(text="❌ Reject", callback_data=AdminFormCallback(table=table, action="reject", item_id=item_id))
    b.adjust(2)
    return b.as_markup()


def admin_review_keyboard(review_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Approve", callback_data=AdminReviewCallback(action="approve", review_id=review_id))
    b.button(text="❌ Reject", callback_data=AdminReviewCallback(action="reject", review_id=review_id))
    b.adjust(2)
    return b.as_markup()


def admin_moderator_keyboard(mod: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if mod["verification_status"] in ("verified", "trusted"):
        b.button(text="⚪ Unverify", callback_data=AdminModCallback(action="unverify", mod_id=mod["id"]))
    else:
        b.button(text="✅ Verify", callback_data=AdminModCallback(action="verify", mod_id=mod["id"]))
    if mod["active_status"]:
        b.button(text="🔴 Deactivate", callback_data=AdminModCallback(action="deactivate", mod_id=mod["id"]))
    else:
        b.button(text="🟢 Activate", callback_data=AdminModCallback(action="activate", mod_id=mod["id"]))
    b.adjust(2)
    return b.as_markup()


def admin_apply_toggle_keyboard(currently_open: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if currently_open:
        b.button(text="🔴 Close Applications", callback_data=AdminApplyToggleCallback(open_=0))
    else:
        b.button(text="🟢 Open Applications", callback_data=AdminApplyToggleCallback(open_=1))
    return b.as_markup()
