"""
Central configuration for the bot. Loads from environment variables (.env)
so nothing sensitive is hardcoded in source.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _parse_ids(raw: str) -> list[int]:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]


@dataclass
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list[int] = field(default_factory=lambda: _parse_ids(os.getenv("ADMIN_IDS", "")))
    db_path: str = os.getenv("DB_PATH", "./bot.db")

    # The Telegram group this bot serves. Message/rank/rep tracking is scoped
    # to this chat only (set after adding the bot to your group — see README).
    main_chat_id: int = int(os.getenv("MAIN_CHAT_ID", "0") or "0")

    community_name: str = "Texting"
    community_handle: str = "@Texting"

    # Banner shown above every screen (photo + caption gets edited in place).
    # Can be EITHER:
    #   - a direct image URL (e.g. https://i.ibb.co/xxxx/banner.jpg)  <- easiest
    #   - a local file path (e.g. ./assets/banner.jpg)
    banner_image_path: str = os.getenv("BANNER_IMAGE_PATH", "./assets/banner.jpg")

    owners: tuple = (
        {"username": "Simp", "display_name": "Simp", "role": "Owner", "contact": "@Simp"},
    )

    # Shown when the "Rules" button is tapped. Edit freely — one bullet per line.
    rules_text: str = (
        "💎 @Texting Rules\n\n"
        "• Do not advertise or promote anything.\n"
        "• Do not share NSFW content.\n"
        "• Do not post personal or sensitive information.\n"
        "• Do not spam messages or reactions.\n"
        "• Do not promote other groups or channels.\n"
        "• Do not beg for money.\n"
        "• Treat every member and moderator with respect.\n"
        "• Listen to staff — repeated rule-breaking leads to a ban.\n"
    )

    giveaway_host_contact: str = os.getenv("GIVEAWAY_HOST_CONTACT", "hoepium")

    # Footer stamped on every generated rank/streak/leaderboard image.
    powered_by: str = "Powered By @SEASON"

    # XP / leveling tuning
    xp_per_message_min: int = 15
    xp_per_message_max: int = 25
    xp_cooldown_seconds: int = 60
    # level = floor(sqrt(xp / xp_curve_divisor))
    xp_curve_divisor: int = 50

    # Reputation
    rep_cooldown_hours: int = 24


config = Config()

if not config.bot_token:
    raise RuntimeError(
        "BOT_TOKEN is not set. Copy .env.example to .env and fill in your bot token."
    )
