import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.db import init_db
from utils.giveaway_scheduler import giveaway_watcher

from handlers import (
    start,
    report,
    appeal,
    suggest,
    feedback,
    apply_mod,
    giveaway,
    giveaway_engine,
    moderators,
    rank,
    reputation,
    admin,
    message_tracker,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Order matters: command/callback-specific routers first, the passive
    # group message tracker last so it never intercepts anything meant for
    # an active FSM form.
    dp.include_router(start.router)
    dp.include_router(report.router)
    dp.include_router(appeal.router)
    dp.include_router(suggest.router)
    dp.include_router(feedback.router)
    dp.include_router(apply_mod.router)
    dp.include_router(giveaway.router)
    dp.include_router(giveaway_engine.router)
    dp.include_router(moderators.router)
    dp.include_router(rank.router)
    dp.include_router(reputation.router)
    dp.include_router(admin.router)
    dp.include_router(message_tracker.router)

    asyncio.create_task(giveaway_watcher(bot))

    logger.info("Starting bot polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
