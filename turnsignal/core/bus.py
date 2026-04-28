from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import AsyncIterator

from turnsignal.core.frame import Frame

log = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 1024


class EventBus:
    """In-process pub/sub for frames, scoped to a single Call."""

    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE):
        self._queue_size = queue_size
        self._subscribers: dict[type, list[asyncio.Queue]] = defaultdict(list)
        self._closed = False
    #----------#

    def subscribe(self, frame_type: type[Frame]) -> AsyncIterator[Frame]:
        if self._closed:
            raise RuntimeError("bus is closed")
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers[frame_type].append(q)
        return self._drain(q)
    #----------#

    async def _drain(self, q: asyncio.Queue) -> AsyncIterator[Frame]:
        while True:
            frame = await q.get()
            if frame is None:
                return
            yield frame
    #----------#

    def publish(self, frame: Frame) -> None:
        if self._closed:
            return
        for ftype, queues in self._subscribers.items():
            if not isinstance(frame, ftype):
                continue
            for q in queues:
                try:
                    q.put_nowait(frame)
                except asyncio.QueueFull:
                    log.warning("bus queue full for %s; dropping frame", ftype.__name__)
    #----------#

    async def close(self) -> None:
        self._closed = True
        for queues in self._subscribers.values():
            for q in queues:
                await q.put(None)
    #----------#
#----------#
