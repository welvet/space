from __future__ import annotations

import asyncio
from collections.abc import Callable

from .arduino import Arduino
from .lego_remote import LegoRemote
from .lego_train import LegoTrain


class Automation:
    def __init__(
        self,
        trains: dict[str, dict[str, object]],
        train: LegoTrain,
        arduino: Arduino,
        remote: LegoRemote,
    ) -> None:
        self._train = train
        self._arduino = arduino
        self._trains_by_tag = {
            self._normalize(tag): train
            for train, config in trains.items()
            for tag in config["nfc_tags"]
        }
        self._last_seen: dict[str, float] = {}
        self._event_callbacks: list[Callable[[str], None]] = []
        remote.on_button(self._on_button)

    async def start(self) -> None:
        pass

    async def on_train(self, train: str) -> None:
        pass

    async def on_button(self, remote: str, button: str) -> None:
        pass

    def on_event(self, callback: Callable[[str], None]) -> None:
        self._event_callbacks.append(callback)

    def event(self, message: str) -> None:
        for callback in self._event_callbacks:
            callback(message)

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
        await self._train.setSpeed(train, speed)

    async def setSwitch(
        self,
        arduino: str,
        switch: str,
        position: str,
    ) -> None:
        await self._arduino.setSwitch(arduino, switch, position)

    def _on_button(self, remote: str, button: str) -> None:
        asyncio.create_task(self.on_button(remote, button))

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
