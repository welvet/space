from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from aiohttp import web
from aiohttp.web_log import AccessLogger

from .devices import Devices
from .automation import Automation
from .lego_remote import LegoRemote
from .lego_train import LegoTrain

INDEX = Path(__file__).resolve().parents[1] / "index.html"


class ApiAccessLogger(AccessLogger):
    def log(self, request, response, time):
        if request.method != "GET":
            super().log(request, response, time)


class Api:
    def __init__(
        self,
        config: dict[str, object],
        train: LegoTrain,
        remote: LegoRemote,
        devices: Devices,
        automation: Automation,
    ) -> None:
        self._host = config["host"]
        self._port = config["port"]
        self._train = train
        self._remote = remote
        self._devices = devices
        self._events: set[asyncio.Queue[dict[str, str]]] = set()
        self._runner: web.AppRunner | None = None
        devices.on_detection(self._detection)
        automation.on_event(self._script_event)

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/info", self._info)
        app.router.add_get("/events", self._event_stream)
        app.router.add_post("/restart", self._restart)
        app.router.add_post("/train/{train}/speed/{speed}", self._set_speed)
        app.router.add_post(
            "/device/{device}/switch/{position}",
            self._set_switch,
        )
        self._runner = web.AppRunner(app, access_log_class=ApiAccessLogger)
        await self._runner.setup()
        await web.TCPSite(self._runner, self._host, self._port).start()

    async def _index(self, _: web.Request) -> web.FileResponse:
        return web.FileResponse(INDEX)

    async def _info(self, _: web.Request) -> web.Response:
        return web.json_response({
            "trains": self._train.info(),
            "remotes": self._remote.info(),
            "devices": self._devices.info(),
        })

    async def _set_speed(self, request: web.Request) -> web.Response:
        await self._train.setSpeed(
            request.match_info["train"],
            int(request.match_info["speed"]),
        )
        return web.Response(status=204)

    async def _set_switch(self, request: web.Request) -> web.Response:
        await self._devices.setSwitch(
            request.match_info["device"],
            request.match_info["position"],
        )
        return web.Response(status=204)

    async def _restart(self, _: web.Request) -> web.Response:
        asyncio.get_running_loop().call_later(
            0.2,
            os.execv,
            sys.executable,
            [sys.executable, "-m", "backend"],
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
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._events.add(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), 15)
                    data = json.dumps(event, separators=(",", ":"))
                    await response.write(f"data: {data}\n\n".encode())
                except TimeoutError:
                    await response.write(b": ping\n\n")
        except (ConnectionError, RuntimeError):
            pass
        finally:
            self._events.discard(queue)
        return response

    def _detection(
        self,
        device: str,
        tag: str,
        detected: bool,
    ) -> None:
        self._publish(
            "nfc",
            f"{device} "
            f"{'detected' if detected else 'removed'} {tag}",
        )

    def _script_event(self, message: str) -> None:
        self._publish("script", message)

    def _publish(self, event_type: str, message: str) -> None:
        event = {
            "date": datetime.now(UTC).isoformat(),
            "type": event_type,
            "message": message,
        }
        for queue in self._events:
            queue.put_nowait(event)
