from aiogram.fsm.state import State, StatesGroup


class ReportForm(StatesGroup):
    waiting_for_username = State()
    waiting_for_reason = State()
    waiting_for_proof = State()
    waiting_for_confirmation = State()


class AppealForm(StatesGroup):
    waiting_for_appealing = State()
    waiting_for_reason = State()
    waiting_for_anything_else = State()
    waiting_for_confirmation = State()


class SuggestForm(StatesGroup):
    waiting_for_idea = State()
    waiting_for_how_it_works = State()
    waiting_for_prizes = State()
    waiting_for_why = State()
    waiting_for_confirmation = State()


class FeedbackForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_confirmation = State()


class ApplyModForm(StatesGroup):
    waiting_for_experience = State()
    waiting_for_availability = State()
    waiting_for_why_you = State()
    waiting_for_confirmation = State()


class ReviewForm(StatesGroup):
    waiting_for_category = State()
    waiting_for_rating = State()
    waiting_for_text = State()


class AdminRejectForm(StatesGroup):
    """Generic state used whenever an admin needs to type a rejection reason."""
    waiting_for_reason = State()


class CreateGiveawayForm(StatesGroup):
    """Admin-only flow for posting a live giveaway into the group."""
    waiting_for_prize = State()
    waiting_for_conditions = State()
    waiting_for_required_channels = State()
    waiting_for_duration = State()
    waiting_for_confirmation = State()
