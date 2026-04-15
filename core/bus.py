"""
Internal pub/sub event bus. Components communicate through this,
never by calling each other directly. This is what lets AERIS
do multiple things simultaneously without coupling.
"""

import asyncio
from collections import defaultdict
from typing import Callable, Any

from loguru import logger


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue | None = None

    def initialize(self):
        self._queue = asyncio.Queue()

    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers[event_type].append(handler)
        logger.debug(f"Bus: {handler.__name__} subscribed to '{event_type}'")

    async def publish(self, event_type: str, data: Any = None):
        if self._queue is None:
            raise RuntimeError("Event bus not initialized")
        event = {"type": event_type, "data": data}
        await self._queue.put(event)

    async def run(self):
        """Dispatch loop — runs forever as a background task"""
        if self._queue is None:
            raise RuntimeError("Event bus not initialized")

        logger.info("Event bus running")
        while True:
            event = await self._queue.get()
            handlers = self._subscribers.get(event["type"], [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event["data"])
                    else:
                        handler(event["data"])
                except Exception as e:
                    logger.error(f"Bus handler error in {handler.__name__}: {e}")
            self._queue.task_done()


bus = EventBus()