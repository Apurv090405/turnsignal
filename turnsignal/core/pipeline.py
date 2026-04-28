from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, AsyncIterator

from turnsignal.core.frame import Frame

if TYPE_CHECKING:
    from turnsignal.core.bus import EventBus
    from turnsignal.core.call import Call


class StageContext:
    """Handle given to a Stage at run-time. Provides bus + call access."""

    def __init__(self, call: "Call", bus: "EventBus"):
        self.call = call
        self.bus = bus
    #----------#

    def subscribe(self, frame_type: type[Frame]) -> AsyncIterator[Frame]:
        return self.bus.subscribe(frame_type)
    #----------#

    def publish(self, frame: Frame) -> None:
        self.bus.publish(frame)
    #----------#
#----------#


class Stage(ABC):
    """A pipeline stage. Implement `run(ctx)` as a long-running coroutine."""

    name: str = "stage"

    @abstractmethod
    async def run(self, ctx: StageContext) -> None: ...
    #----------#
#----------#
