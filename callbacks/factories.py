from aiogram.filters.callback_data import CallbackData


class NavCallback(CallbackData, prefix="nav"):
    """Static navigation between home-screen entry points."""
    target: str  # "home" | "report" | "appeal" | "suggest" | "feedback" | "apply_mod" | "giveaway" | "moderators" | "owners"


class FormActionCallback(CallbackData, prefix="frm"):
    """Confirm / Cancel / Submit-anonymously on any form's review step."""
    form: str    # "report" | "appeal" | "suggest" | "feedback"
    action: str  # "confirm" | "cancel" | "anonymous"


class AppealTypeCallback(CallbackData, prefix="apt"):
    kind: str  # "Mute" | "Warning" | "Ban"


class ModeratorCallback(CallbackData, prefix="mod"):
    action: str  # "profile" | "services" | "reviews"
    mod_id: int


class ReviewCallback(CallbackData, prefix="rev"):
    action: str  # "start" | "rate"
    mod_id: int
    rating: int = 0


class ReviewCategoryCallback(CallbackData, prefix="rvc"):
    category_index: int


class GiveawayEntryCallback(CallbackData, prefix="gwe"):
    giveaway_id: int


class GiveawayCheckCallback(CallbackData, prefix="gwc"):
    """'Done' button — re-checks channel membership after the user joins."""
    giveaway_id: int


# ---------------- Admin callbacks ----------------

class AdminFormCallback(CallbackData, prefix="adf"):
    table: str    # "reports" | "appeals" | "suggestions" | "feedback" | "applications"
    action: str   # "approve" | "reject"
    item_id: int


class AdminReviewCallback(CallbackData, prefix="arv"):
    action: str  # "approve" | "reject"
    review_id: int


class AdminModCallback(CallbackData, prefix="amd"):
    action: str  # "verify" | "unverify" | "activate" | "deactivate"
    mod_id: int


class AdminApplyToggleCallback(CallbackData, prefix="atg"):
    open_: int  # 1 to open, 0 to close
