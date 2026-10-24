import asyncio
import logging

from app.config import get_settings
from app.db import SessionLocal
from app.services.recertification import run_recertification_cycle

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _recert_loop() -> None:
    settings = get_settings()
    while True:
        try:
            async with SessionLocal() as db:
                summary = await run_recertification_cycle(db)
                if summary["demoted"] or summary["recertified"]:
                    logger.info("recert_cycle_complete", extra={"extra_fields": summary})
        except Exception:
            logger.exception("recert_cycle_failed")
        await asyncio.sleep(settings.recert_check_interval_seconds)


def start_recertification_scheduler() -> None:
    global _task
    settings = get_settings()
    if not settings.recert_scheduler_enabled:
        return
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_recert_loop())


def stop_recertification_scheduler() -> None:
    global _task
    if _task:
        _task.cancel()
        _task = None
