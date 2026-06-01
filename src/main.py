from __future__ import annotations

import asyncio
import logging
import signal

import database as db
from bot import build_app
from worker import polling_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    await db.get_pool()
    logger.info("Database connected.")

    app = build_app()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started.")

        worker_task = asyncio.create_task(polling_loop(app.bot))

        await stop_event.wait()
        logger.info("Shutting down…")

        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        await app.updater.stop()
        await app.stop()

    await db.close_pool()
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
