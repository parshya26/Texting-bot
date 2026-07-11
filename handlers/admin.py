"""
Admin panel. Every handler checks db.is_admin() first.

Approve: marks the item approved and (best-effort) DMs the submitter a short
confirmation. Skipped entirely for anonymous submissions since we don't want
to reveal to anyone (including via a stray DM) who submitted what — but note
the bot still knows the internal user_id for record-keeping; only the
admin-facing message hides the username.

Reject: asks the admin to type a reason first, THEN applies it and DMs the
submitter: "Your request has been reviewed and was not approved. <reason>"
(exact wording confirmed against the reference bot for reports).

Commands:
  /admin                    - menu
  /pending_reports /pending_appeals /pending_suggestions
  /pending_feedback /pending_applications /pending_reviews
  /mods                     - manage moderator verification/active status
  /applications             - view/toggle whether Apply-for-Mod is open
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from callbacks.factories import AdminFormCallback, AdminReviewCallback, AdminModCallback, AdminApplyToggleCallback
from keyboards.admin import admin_form_keyboard, admin_review_keyboard, admin_moderator_keyboard, admin_apply_toggle_keyboard
from states.forms import AdminRejectForm

router = Router(name="admin")

# table -> (getter, setter, display label, field->label map for the notification)
FORM_TABLES = {
    "reports": {
        "get": db.get_report, "set": db.set_report_status, "label": "Report",
        "fields": [("target_username", "Username"), ("reason", "Reason"), ("proof", "Proof")],
    },
    "appeals": {
        "get": db.get_appeal, "set": db.set_appeal_status, "label": "Appeal",
        "fields": [("appealing", "Appealing"), ("reason", "Reason"), ("anything_else", "Anything else")],
    },
    "suggestions": {
        "get": db.get_suggestion, "set": db.set_suggestion_status, "label": "Suggestion",
        "fields": [("idea", "Idea"), ("how_it_works", "How it works"), ("prizes", "Prizes"), ("why", "Why")],
    },
    "feedback": {
        "get": db.get_feedback, "set": db.set_feedback_status, "label": "Feedback",
        "fields": [("feedback_text", "Feedback")],
    },
    "applications": {
        "get": db.get_application, "set": db.set_application_status, "label": "Mod Application",
        "fields": [("experience", "Experience"), ("availability", "Availability"), ("why_you", "Why them")],
    },
}


async def _require_admin(message_or_call) -> bool:
    return await db.is_admin(message_or_call.from_user.id)


@router.message(Command("admin"))
async def admin_home(message: Message):
    if not await _require_admin(message):
        await message.answer("🚫 You're not authorized to use this command.")
        return
    await message.answer(
        "🛠️ <b>Admin Panel</b>\n\n"
        "/pending_reports — moderate pending reports\n"
        "/pending_appeals — moderate pending appeals\n"
        "/pending_suggestions — moderate pending suggestions\n"
        "/pending_feedback — moderate pending feedback\n"
        "/pending_applications — moderate pending mod applications\n"
        "/pending_reviews — moderate pending moderator reviews\n"
        "/mods — manage moderator verification/active status\n"
        "/applications — view/toggle whether Apply-for-Mod is open\n"
        "/creategiveaway — post a live giveaway to the group\n"
    )


def _register_pending_command(table: str) -> None:
    meta = FORM_TABLES[table]

    @router.message(Command(f"pending_{table}"))
    async def _handler(message: Message):
        if not await _require_admin(message):
            return
        list_fn = getattr(db, f"list_pending_{table}")
        items = await list_fn()
        if not items:
            await message.answer(f"No pending {meta['label'].lower()}s. ✅")
            return
        for item in items:
            submitter = "Submitted anonymously" if item.get("anonymous") else f"From: @{item.get('submitter_username') or 'unknown'}"
            body_lines = [f"<b>{meta['label']} #{item['id']}</b>", submitter, ""]
            for field, field_label in meta["fields"]:
                body_lines.append(f"<b>{field_label}:</b> {item[field]}")
            await message.answer("\n".join(body_lines), reply_markup=admin_form_keyboard(table, item["id"]))


for _table in FORM_TABLES:
    _register_pending_command(_table)


@router.callback_query(AdminFormCallback.filter(F.action == "approve"))
async def approve_form_item(call: CallbackQuery, callback_data: AdminFormCallback):
    if not await _require_admin(call):
        await call.answer("Not authorized.", show_alert=True)
        return
    meta = FORM_TABLES[callback_data.table]
    item = await meta["set"](callback_data.item_id, "approved")
    if not item:
        await call.answer("Item not found.", show_alert=True)
        return
    if not item.get("anonymous") and item.get("submitter_telegram_id"):
        try:
            await call.bot.send_message(
                item["submitter_telegram_id"],
                f"✅ Your {meta['label'].lower()} has been reviewed and approved. Thank you!",
            )
        except Exception:
            pass
    await call.message.edit_text(call.message.html_text + "\n\n<b>Status: APPROVED</b>")
    await call.answer("Approved.")


@router.callback_query(AdminFormCallback.filter(F.action == "reject"))
async def reject_form_item_start(call: CallbackQuery, callback_data: AdminFormCallback, state: FSMContext):
    if not await _require_admin(call):
        await call.answer("Not authorized.", show_alert=True)
        return
    await state.set_state(AdminRejectForm.waiting_for_reason)
    await state.update_data(reject_table=callback_data.table, reject_item_id=callback_data.item_id, reject_message_id=call.message.message_id)
    await call.message.answer("Please give a reason for rejecting this submission:")
    await call.answer()


@router.message(AdminRejectForm.waiting_for_reason)
async def reject_form_item_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    table, item_id = data["reject_table"], data["reject_item_id"]
    meta = FORM_TABLES[table]
    reason = message.text.strip()

    item = await meta["set"](item_id, "rejected", reason)
    await state.clear()
    if not item:
        await message.answer("That item no longer exists.")
        return

    if not item.get("anonymous") and item.get("submitter_telegram_id"):
        try:
            await message.bot.send_message(
                item["submitter_telegram_id"],
                f"❌ Your {meta['label'].lower()} has been reviewed and was not approved.\n\n{reason}",
            )
        except Exception:
            pass
    await message.answer(f"Rejected {meta['label']} #{item_id} with reason sent to the submitter.")


# ---------------- Reviews ----------------

@router.message(Command("pending_reviews"))
async def pending_reviews(message: Message):
    if not await _require_admin(message):
        return
    reviews = await db.list_pending_reviews()
    if not reviews:
        await message.answer("No pending reviews. ✅")
        return
    for r in reviews:
        text = (
            f"⭐ <b>Review #{r['id']}</b> for {r['mod_name']}\n"
            f"From: @{r['reviewer_username'] or 'unknown'}\n"
            f"Rating: {'⭐' * r['rating']}\n"
            f"Category: {r['service_category']}\n\n"
            f"{r['review_text']}"
        )
        await message.answer(text, reply_markup=admin_review_keyboard(r["id"]))


@router.callback_query(AdminReviewCallback.filter())
async def moderate_review(call: CallbackQuery, callback_data: AdminReviewCallback):
    if not await _require_admin(call):
        await call.answer("Not authorized.", show_alert=True)
        return
    status = "approved" if callback_data.action == "approve" else "rejected"
    review = await db.set_review_status(callback_data.review_id, status)
    if not review:
        await call.answer("Review not found.", show_alert=True)
        return
    await call.message.edit_text(call.message.html_text + f"\n\n<b>Status: {status.upper()}</b>")
    await call.answer(f"Review {status}.")


# ---------------- Moderator management ----------------

@router.message(Command("mods"))
async def list_mods_admin(message: Message):
    if not await _require_admin(message):
        return
    mods = await db.list_moderators(active_only=False)
    if not mods:
        await message.answer("No moderators in the database yet.")
        return
    for m in mods:
        text = (
            f"<b>{m['display_name']}</b> (@{m['username']})\n"
            f"Verification: {m['verification_status']} | "
            f"Active: {'yes' if m['active_status'] else 'no'} | "
            f"Rating: {m['reputation_score']:.1f}"
        )
        await message.answer(text, reply_markup=admin_moderator_keyboard(m))


@router.callback_query(AdminModCallback.filter())
async def moderate_mod(call: CallbackQuery, callback_data: AdminModCallback):
    if not await _require_admin(call):
        await call.answer("Not authorized.", show_alert=True)
        return
    action = callback_data.action
    if action == "verify":
        await db.set_moderator_verification(callback_data.mod_id, "verified")
    elif action == "unverify":
        await db.set_moderator_verification(callback_data.mod_id, "unverified")
    elif action == "deactivate":
        await db.set_moderator_active(callback_data.mod_id, False)
    elif action == "activate":
        await db.set_moderator_active(callback_data.mod_id, True)

    mod = await db.get_moderator(callback_data.mod_id)
    await call.message.edit_text(
        f"<b>{mod['display_name']}</b> (@{mod['username']})\n"
        f"Verification: {mod['verification_status']} | "
        f"Active: {'yes' if mod['active_status'] else 'no'} | "
        f"Rating: {mod['reputation_score']:.1f}",
        reply_markup=admin_moderator_keyboard(mod),
    )
    await call.answer("Updated.")


# ---------------- Apply-for-Mod toggle ----------------

@router.message(Command("applications"))
async def applications_status(message: Message):
    if not await _require_admin(message):
        return
    is_open = await db.is_mod_applications_open()
    status = "OPEN 🟢" if is_open else "CLOSED 🔴"
    await message.answer(f"Mod applications are currently: <b>{status}</b>", reply_markup=admin_apply_toggle_keyboard(is_open))


@router.callback_query(AdminApplyToggleCallback.filter())
async def toggle_applications(call: CallbackQuery, callback_data: AdminApplyToggleCallback):
    if not await _require_admin(call):
        await call.answer("Not authorized.", show_alert=True)
        return
    await db.set_mod_applications_open(bool(callback_data.open_))
    is_open = await db.is_mod_applications_open()
    status = "OPEN 🟢" if is_open else "CLOSED 🔴"
    await call.message.edit_text(
        f"Mod applications are currently: <b>{status}</b>", reply_markup=admin_apply_toggle_keyboard(is_open)
    )
    await call.answer("Updated.")
