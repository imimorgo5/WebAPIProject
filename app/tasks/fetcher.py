import asyncio
from typing import Optional

from app.db.base import async_session
from app.services.parser import run_perfumes_generator_once
from app.config import BACKGROUND_INTERVAL_SECONDS


_shutdown_event: asyncio.Event = asyncio.Event()
_background_task_handle: Optional[asyncio.Task] = None


async def background_loop(interval_seconds: int = BACKGROUND_INTERVAL_SECONDS):
    while not _shutdown_event.is_set():
        async with async_session() as session:
            try:
                await run_perfumes_generator_once(session)
            except Exception:
                pass
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def start_background():
    global _background_task_handle
    if _background_task_handle is None:
        _background_task_handle = asyncio.create_task(background_loop())


async def stop_background():
    _shutdown_event.set()
    global _background_task_handle
    if _background_task_handle is not None:
        try:
            await _background_task_handle
        except Exception:
            pass
