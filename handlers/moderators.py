from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import db
from callbacks.factories import NavCallback, ModeratorCallback, ReviewCallback, ReviewCategoryCallback
from keyboards.moderators import (
    moderators_list_keyboard,
    moderator_profile_keyboard,
    back_to_moderator_keyboard,
    review_category_keyboard,
    rating_keyboard,
    SERVICE_CATEGORIES,
)
from utils.texts import moderators_list_text, moderator_profile_text, service_list_text, reviews_list_text
from utils.session import is_locked, update_banner, update_banner_from_callback
from utils.admin_notify import notify_admins_new_review
from states.forms import ReviewForm

router = Router(name="moderators")


@router.callback_query(NavCallback.filter(F.target == "moderators"))
async def show_moderators(call: CallbackQuery, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return
    mods = await db.list_moderators(active_only=True)
    await call.message.edit_caption(
        caption=moderators_list_text(len(mods)),
        reply_markup=moderators_list_keyboard(mods),
    )
    await call.answer()


@router.callback_query(ModeratorCallback.filter(F.action == "profile"))
async def show_profile(call: CallbackQuery, callback_data: ModeratorCallback, state: FSMContext):
    mod = await db.get_moderator(callback_data.mod_id)
    if not mod:
        await call.answer("This moderator no longer exists.", show_alert=True)
        return
    community = await db.get_community(mod["community_id"]) if mod["community_id"] else None
    services = await db.list_services(mod["id"])
    review_count = await db.count_reviews(mod["id"])
    await call.message.edit_caption(
        caption=moderator_profile_text(mod, community, services, review_count),
        reply_markup=moderator_profile_keyboard(mod),
    )
    await call.answer()


@router.callback_query(ModeratorCallback.filter(F.action == "services"))
async def show_services(call: CallbackQuery, callback_data: ModeratorCallback):
    mod = await db.get_moderator(callback_data.mod_id)
    services = await db.list_services(callback_data.mod_id)
    await call.message.edit_caption(
        caption=service_list_text(mod, services),
        reply_markup=back_to_moderator_keyboard(callback_data.mod_id),
    )
    await call.answer()


@router.callback_query(ModeratorCallback.filter(F.action == "reviews"))
async def show_reviews(call: CallbackQuery, callback_data: ModeratorCallback):
    mod = await db.get_moderator(callback_data.mod_id)
    reviews = await db.list_reviews(callback_data.mod_id, status="approved", limit=10)
    await call.message.edit_caption(
        caption=reviews_list_text(mod, reviews),
        reply_markup=back_to_moderator_keyboard(callback_data.mod_id),
    )
    await call.answer()


# ---------------- Leave a Review flow ----------------

@router.callback_query(ReviewCallback.filter(F.action == "start"))
async def start_review(call: CallbackQuery, callback_data: ReviewCallback, state: FSMContext):
    if await is_locked(state):
        await call.answer("You're already in the middle of a support request. Send /cancel first.", show_alert=True)
        return

    user = await db.get_or_create_user(call.from_user.id, call.from_user.username or "", call.from_user.first_name or "")
    if await db.has_reviewed(user["id"], callback_data.mod_id):
        await call.answer("You've already reviewed this moderator.", show_alert=True)
        return

    await state.set_state(ReviewForm.waiting_for_category)
    caption = "Leaving a review\n\nWhich service is this review about?"
    await call.message.edit_caption(caption=caption, reply_markup=review_category_keyboard())
    await state.update_data(
        mod_id=callback_data.mod_id,
        banner_chat_id=call.message.chat.id,
        banner_message_id=call.message.message_id,
        banner_caption=caption,
    )
    await call.answer()


@router.callback_query(ReviewForm.waiting_for_category, ReviewCategoryCallback.filter())
async def review_category_chosen(call: CallbackQuery, callback_data: ReviewCategoryCallback, state: FSMContext):
    category = SERVICE_CATEGORIES[callback_data.category_index]
    data = await state.get_data()
    await state.update_data(category=category)
    await state.set_state(ReviewForm.waiting_for_rating)
    caption = f"Leaving a review\nCategory: {category}\n\nRate the moderator from 1 to 5 stars:"
    await update_banner_from_callback(call, state, caption, rating_keyboard(data["mod_id"]))
    await call.answer()


@router.callback_query(ReviewForm.waiting_for_rating, ReviewCallback.filter(F.action == "rate"))
async def review_rating_chosen(call: CallbackQuery, callback_data: ReviewCallback, state: FSMContext):
    await state.update_data(rating=callback_data.rating)
    await state.set_state(ReviewForm.waiting_for_text)
    data = await state.get_data()
    caption = (
        f"Leaving a review\nCategory: {data['category']}\nRating: {'⭐' * callback_data.rating}\n\n"
        "Now send a short text describing your experience:"
    )
    await update_banner_from_callback(call, state, caption, reply_markup=None)
    await call.answer()


@router.message(ReviewForm.waiting_for_text)
async def review_text_received(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_or_create_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "")

    if await db.has_reviewed(user["id"], data["mod_id"]):
        await message.answer("You've already reviewed this moderator.")
        await state.clear()
        return

    review_id = await db.add_review(
        user_id=user["id"],
        moderator_id=data["mod_id"],
        rating=data["rating"],
        text=message.text.strip(),
        category=data.get("category", "Other"),
    )
    caption = (
        f"Leaving a review\nCategory: {data['category']}\nRating: {'⭐' * data['rating']}\n\n"
        "✅ Thanks! Your review has been submitted and is pending admin approval."
    )
    await update_banner(message.bot, state, caption, back_to_moderator_keyboard(data["mod_id"]))
    await state.clear()

    review = await db.get_review_with_details(review_id)
    if review:
        await notify_admins_new_review(message.bot, review)
