from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aiohttp import web

from .arduino import Arduino
from .automation import Automation
from .lego_remote import LegoRemote
from .lego_train import LegoTrain

INDEX = Path(__file__).resolve().parents[1] / "index.html"


class Api:
    def __init__(
        self,
        config: dict[str, object],
        train: LegoTrain,
        remote: LegoRemote,
        arduino: Arduino,
        automation: Automation,
    ) -> None:
        self._host = config["host"]
        self._port = config["port"]
        self._train = train
        self._remote = remote
        self._arduino = arduino
        self._events: set[
            asyncio.Queue[tuple[str, dict[str, object]]]
        ] = set()
        self._runner: web.AppRunner | None = None
        arduino.on_detection(self._detection)
        automation.on_event(self._script_event)

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/info", self._info)
        app.router.add_get("/events", self._event_stream)
        app.router.add_post("/train/{train}/speed/{speed}", self._set_speed)
        app.router.add_post(
            "/arduino/{arduino}/switch/{switch}/{position}",
            self._set_switch,
        )
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, self._host, self._port).start()

    async def _index(self, _: web.Request) -> web.FileResponse:
        return web.FileResponse(INDEX)

    async def _info(self, _: web.Request) -> web.Response:
        return web.json_response({
            "trains": self._train.info(),
            "remotes": self._remote.info(),
            "arduinos": self._arduino.info(),
        })

    async def _set_speed(self, request: web.Request) -> web.Response:
        await self._train.setSpeed(
            request.match_info["train"],
            int(request.match_info["speed"]),
        )
        return web.Response(status=204)

    async def _set_switch(self, request: web.Request) -> web.Response:
        await self._arduino.setSwitch(
            request.match_info["arduino"],
            request.match_info["switch"],
            request.match_info["position"],
        )
        return web.Response(status=204)

    async def _event_stream(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        })
        await response.prepare(request)
        queue: asyncio.Queue[tuple[str, dict[str, object]]] = asyncio.Queue()
        self._events.add(queue)
        try:
            while True:
                try:
                    name, event = await asyncio.wait_for(queue.get(), 15)
                    data = json.dumps(event, separators=(",", ":"))
                    await response.write(f"event: {name}\ndata: {data}\n\n".encode())
                except TimeoutError:
                    await response.write(b": ping\n\n")
        except (ConnectionError, RuntimeError):
            pass
        finally:
            self._events.discard(queue)
        return response

    def _detection(
        self,
        arduino: str,
        detector: str,
        tag: str,
        detected: bool,
    ) -> None:
        event = {
            "arduino": arduino,
            "detector": detector,
            "tag": tag,
            "detected": detected,
        }
        self._publish("detector", event)

    def _script_event(self, message: str) -> None:
        self._publish("script", {"message": message})

    def _publish(self, name: str, event: dict[str, object]) -> None:
        for queue in self._events:
            queue.put_nowait((name, event))
