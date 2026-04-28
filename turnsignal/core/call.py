from __future__ import annotations

import asyncio
import logging
import uuid
from enum import Enum

from turnsignal.core.bus import EventBus
from turnsignal.core.frame import EventFrame
from turnsignal.core.pipeline import Stage, StageContext
from turnsignal.core.types import EventType

log = logging.getLogger(__name__)


class CallState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
#----------#


class Call:
    """One voice call. Owns the bus and supervises stages."""

    def __init__(self, *, call_id: str | None = None):
        self.id = call_id or str(uuid.uuid4())
        self.bus = EventBus()
        self.state = CallState.PENDING
        self._stages: list[Stage] = []
        self._tasks: list[asyncio.Task] = []
        self._stopped = asyncio.Event()
    #----------#

    def add_stage(self, stage: Stage) -> None:
        if self.state != CallState.PENDING:
            raise RuntimeError(f"cannot add stage to call in state {self.state}")
        self._stages.append(stage)
    #----------#

    async def start(self) -> None:
        if self.state != CallState.PENDING:
            raise RuntimeError(f"cannot start call in state {self.state}")
        self.state = CallState.RUNNING
        ctx = StageContext(self, self.bus)
        self._tasks.append(
            asyncio.create_task(
                self._watch_hangup(),
                name=f"call-{self.id}-hangup-watcher",
            )
        )
        for stage in self._stages:
            self._tasks.append(
                asyncio.create_task(
                    self._supervise(stage, ctx),
                    name=f"call-{self.id}-{stage.name}",
                )
            )
        for _ in range(5):
            await asyncio.sleep(0)
    #----------#

    async def _supervise(self, stage: Stage, ctx: StageContext) -> None:
        try:
            await stage.run(ctx)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("stage %s failed in call %s", stage.name, self.id)
            self.state = CallState.FAILED
            asyncio.create_task(self.stop())
    #----------#

    async def _watch_hangup(self) -> None:
        async for frame in self.bus.subscribe(EventFrame):
            if isinstance(frame, EventFrame) and frame.event_type == EventType.HANGUP:
                asyncio.create_task(self.stop())
                return
    #----------#

    async def wait(self) -> None:
        await self._stopped.wait()
    #----------#

    async def stop(self) -> None:
        if self.state == CallState.STOPPED:
            return
        if self.state != CallState.FAILED:
            self.state = CallState.STOPPED
        self.bus.publish(EventFrame(event_type=EventType.HANGUP))
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.bus.close()
        self._stopped.set()
    #----------#
#----------#
