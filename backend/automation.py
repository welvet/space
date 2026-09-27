from __future__ import annotations

import asyncio

from .arduino import Arduino
from .lego_ble import LegoBle


class Automation:
    def __init__(
        self,
        trains: dict[str, dict[str, object]],
        lego: LegoBle,
        arduino: Arduino,
    ) -> None:
        self._lego = lego
        self._arduino = arduino
        self._trains_by_tag = {
            self._normalize(tag): train
            for train, config in trains.items()
            for tag in config["nfc_tags"]
        }
        self._last_seen: dict[str, float] = {}

    async def start(self) -> None:
        pass

    async def on_train(self, train: str) -> None:
        pass

    def on_detector(
        self,
        arduino: str,
        detector: str,
        cooldown: float = 2,
    ) -> None:
        self._arduino.on_detector(
            arduino,
            detector,
            lambda tag: asyncio.create_task(self._detected(tag, cooldown)),
        )

    async def setSpeed(self, train: str, speed: int) -> None:
        await self._lego.setSpeed(train, speed)

    async def setSwitch(
        self,
        arduino: str,
        switch: str,
        position: str,
    ) -> None:
        await self._arduino.setSwitch(arduino, switch, position)

    async def _detected(self, tag: str, cooldown: float) -> None:
        train = self._trains_by_tag.get(self._normalize(tag))
        if train is None:
            return

        now = asyncio.get_running_loop().time()
        last_seen = self._last_seen.get(train)
        if last_seen is not None and now - last_seen < cooldown:
            return
        self._last_seen[train] = now
        await self.on_train(train)

    @staticmethod
    def _normalize(tag: str) -> str:
        return tag.replace(":", "").replace("-", "").upper()
