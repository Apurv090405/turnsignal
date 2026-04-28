from __future__ import annotations

import asyncio
import logging
import os

from websockets.asyncio.server import serve

from turnsignal import load_config
from turnsignal.core.call import Call
from turnsignal.core.frame import AudioFrame
from turnsignal.core.pipeline import Stage, StageContext
from turnsignal.core.types import AudioDirection
from turnsignal.telco.twilio import TwilioStage


class EchoStage(Stage):
    name = "echo"

    async def run(self, ctx: StageContext) -> None:
        async for frame in ctx.subscribe(AudioFrame):
            assert isinstance(frame, AudioFrame)
            if frame.direction != AudioDirection.INBOUND:
                continue
            ctx.publish(
                AudioFrame(
                    data=frame.data,
                    sample_rate=frame.sample_rate,
                    encoding=frame.encoding,
                    direction=AudioDirection.OUTBOUND,
                )
            )
    #----------#
#----------#


async def handle(websocket) -> None:
    call = Call()
    call.add_stage(TwilioStage(websocket))
    call.add_stage(EchoStage())
    logging.info("call %s started", call.id)
    await call.start()
    await call.wait()
    logging.info("call %s ended", call.id)
#----------#


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(os.getenv("TS_CONFIG"))
    async with serve(handle, config.telco.bind_host, config.telco.bind_port):
        logging.info("listening on ws://%s:%s", config.telco.bind_host, config.telco.bind_port)
        await asyncio.Future()
#----------#


if __name__ == "__main__":
    asyncio.run(main())
