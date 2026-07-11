"""Fetches a user's current Telegram avatar as raw bytes (or None if they have none)."""
from aiogram import Bot


async def fetch_avatar_bytes(bot: Bot, telegram_id: int) -> bytes | None:
    try:
        photos = await bot.get_user_profile_photos(telegram_id, limit=1)
        if photos.total_count == 0:
            return None
        file_id = photos.photos[0][-1].file_id
        file = await bot.get_file(file_id)
        buf = await bot.download_file(file.file_path)
        return buf.read()
    except Exception:
        return None
