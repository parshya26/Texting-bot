"""
Sends a formatted notification to every configured admin whenever a new
report / appeal / suggestion / feedback / application / review comes in.
If a submission was made anonymously, the submitter's username is withheld
from the admin-facing message.
"""
from aiogram import Bot

from config import config
from keyboards.admin import admin_form_keyboard, admin_review_keyboard


async def _broadcast(bot: Bot, text: str, reply_markup=None) -> None:
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception:
            # Admin may have blocked the bot or never started it — skip silently.
            pass


def _submitter_line(row: dict) -> str:
    if row.get("anonymous"):
        return "Submitted anonymously"
    username = row.get("submitter_username")
    return f"From: @{username}" if username else "From: (no username)"


async def notify_admins_new_report(bot: Bot, report: dict) -> None:
    text = (
        f"🚨 <b>New Report #{report['id']}</b>\n"
        f"{_submitter_line(report)}\n\n"
        f"<b>Username:</b> {report['target_username']}\n"
        f"<b>Reason:</b> {report['reason']}\n"
        f"<b>Proof:</b> {report['proof']}"
    )
    await _broadcast(bot, text, admin_form_keyboard("reports", report["id"]))


async def notify_admins_new_appeal(bot: Bot, appeal: dict) -> None:
    text = (
        f"📮 <b>New Appeal #{appeal['id']}</b>\n"
        f"{_submitter_line(appeal)}\n\n"
        f"<b>Appealing:</b> {appeal['appealing']}\n"
        f"<b>Reason:</b> {appeal['reason']}\n"
        f"<b>Anything else:</b> {appeal['anything_else']}"
    )
    await _broadcast(bot, text, admin_form_keyboard("appeals", appeal["id"]))


async def notify_admins_new_suggestion(bot: Bot, suggestion: dict) -> None:
    text = (
        f"💡 <b>New Suggestion #{suggestion['id']}</b>\n"
        f"{_submitter_line(suggestion)}\n\n"
        f"<b>Idea:</b> {suggestion['idea']}\n"
        f"<b>How it works:</b> {suggestion['how_it_works']}\n"
        f"<b>Prizes:</b> {suggestion['prizes']}\n"
        f"<b>Why:</b> {suggestion['why']}"
    )
    await _broadcast(bot, text, admin_form_keyboard("suggestions", suggestion["id"]))


async def notify_admins_new_feedback(bot: Bot, feedback: dict) -> None:
    text = (
        f"📝 <b>New Feedback #{feedback['id']}</b>\n"
        f"{_submitter_line(feedback)}\n\n"
        f"{feedback['feedback_text']}"
    )
    await _broadcast(bot, text, admin_form_keyboard("feedback", feedback["id"]))


async def notify_admins_new_application(bot: Bot, application: dict) -> None:
    text = (
        f"🎓 <b>New Mod Application #{application['id']}</b>\n"
        f"{_submitter_line(application)}\n\n"
        f"<b>Experience:</b> {application['experience']}\n"
        f"<b>Availability:</b> {application['availability']}\n"
        f"<b>Why them:</b> {application['why_you']}"
    )
    await _broadcast(bot, text, admin_form_keyboard("applications", application["id"]))


async def notify_admins_new_review(bot: Bot, review: dict) -> None:
    text = (
        f"⭐ <b>New Review #{review['id']}</b> for {review.get('mod_name', 'a moderator')}\n"
        f"From: @{review.get('reviewer_username') or 'unknown'}\n"
        f"Rating: {'⭐' * review['rating']}\n"
        f"Category: {review.get('service_category', 'Other')}\n\n"
        f"{review['review_text']}"
    )
    await _broadcast(bot, text, admin_review_keyboard(review["id"]))
