from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Mapping

from bleak import BleakClient
from bleak.exc import BleakDeviceNotFoundError

HUB_CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"
RECONNECT_SECONDS = 5
BUTTON_PORTS = {0: "left", 1: "right"}
BUTTON_VALUES = {0x01: "plus", 0x7F: "stop", 0xFF: "minus"}
BATTERY_REQUEST = bytes([0x05, 0x00, 0x01, 0x06, 0x05])
BATTERY_ENABLE_UPDATES = bytes([0x05, 0x00, 0x01, 0x06, 0x02])


class LegoRemote:
    def __init__(self, remotes: Mapping[str, str]) -> None:
        self._remotes = dict(remotes)
        self._clients: dict[str, BleakClient] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._callbacks: list[Callable[[str, str], None]] = []
        self._battery: dict[str, int] = {}
        self._log = logging.getLogger("backend.lego_remote")

    async def start(self) -> None:
        if self._tasks:
            raise RuntimeError("LegoRemote is already started")
        for remote, address in self._remotes.items():
            self._tasks[remote] = asyncio.create_task(
                self._watch(remote, address),
                name=f"lego-remote:{remote}",
            )

    def on_button(self, callback: Callable[[str, str], None]) -> None:
        self._callbacks.append(callback)

    async def shutdown(self) -> None:
        results = await asyncio.gather(*(
            client.write_gatt_char(
                HUB_CHARACTERISTIC_UUID,
                bytes([0x04, 0x00, 0x02, 0x01]),
            )
            for client in list(self._clients.values())
            if client.is_connected
        ), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result

    def info(self) -> dict[str, dict[str, object]]:
        return {
            remote: {
                "address": address,
                "connected": (
                    (client := self._clients.get(remote)) is not None
                    and client.is_connected
                ),
                "battery_percent": self._battery.get(remote),
            }
            for remote, address in self._remotes.items()
        }

    async def _watch(self, remote: str, address: str) -> None:
        while True:
            client = BleakClient(address)
            try:
                await client.connect()
                await self._setup(remote, client)
                self._clients[remote] = client
                self._log.info("Connected to %s", remote)
                while client.is_connected:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except BleakDeviceNotFoundError:
                pass
            except Exception as error:
                self._log.warning("%s: %s", remote, error)
            finally:
                self._clients.pop(remote, None)
                self._battery.pop(remote, None)
                if client.is_connected:
                    with suppress(Exception):
                        await client.disconnect()

            await asyncio.sleep(RECONNECT_SECONDS)

    async def _setup(self, remote: str, client: BleakClient) -> None:
        def notification(_: object, data: bytearray) -> None:
            if len(data) >= 6 and data[2] == 0x01 and data[3] == 0x06:
                self._battery[remote] = data[5]
                return
            if len(data) < 5 or data[2] != 0x45:
                return
            side = BUTTON_PORTS.get(data[3])
            button = BUTTON_VALUES.get(data[4])
            if side is None or button is None:
                return
            for callback in self._callbacks:
                callback(remote, f"{side}_{button}")

        await client.start_notify(HUB_CHARACTERISTIC_UUID, notification)
        for port in BUTTON_PORTS:
            await client.write_gatt_char(
                HUB_CHARACTERISTIC_UUID,
                bytes([
                    0x0A,
                    0x00,
                    0x41,
                    port,
                    0x00,
                    0x01,
                    0x00,
                    0x00,
                    0x00,
                    0x01,
                ]),
            )
        await client.write_gatt_char(HUB_CHARACTERISTIC_UUID, BATTERY_REQUEST)
        await client.write_gatt_char(
            HUB_CHARACTERISTIC_UUID,
            BATTERY_ENABLE_UPDATES,
        )
