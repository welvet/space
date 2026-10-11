from __future__ import annotations

import asyncio
import logging
import struct
from contextlib import suppress
from typing import Mapping

from bleak import BleakClient
from bleak.exc import BleakDeviceNotFoundError

HUB_CHARACTERISTIC_UUID = "00001624-1212-efde-1623-785feabcd123"
VOLTAGE_PORT = 0x3C
RECONNECT_SECONDS = 5

BATTERY_REQUEST = bytes([0x05, 0x00, 0x01, 0x06, 0x05])
BATTERY_ENABLE_UPDATES = bytes([0x05, 0x00, 0x01, 0x06, 0x02])
VOLTAGE_MAX_RAW = 3893.0
VOLTAGE_MAX_V = 9.6


class LegoTrain:
    def __init__(self, trains: Mapping[str, str]) -> None:
        self._trains = dict(trains)
        self._clients: dict[str, BleakClient] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._battery: dict[str, int] = {}
        self._voltage: dict[str, float] = {}
        self._speed = {train: 0 for train in self._trains}
        self._log = logging.getLogger("backend.lego_train")

    async def start(self) -> None:
        if self._tasks:
            raise RuntimeError("LegoTrain is already started")
        for train, address in self._trains.items():
            self._tasks[train] = asyncio.create_task(
                self._watch(train, address),
                name=f"lego-train:{train}",
            )

    async def setSpeed(self, train: str, speed: int) -> None:
        command = bytes([0x06, 0x00, 0x81, 0x01, 0x11, 0x51, 0x00])
        command += struct.pack("b", speed)
        await self._clients[train].write_gatt_char(HUB_CHARACTERISTIC_UUID, command)
        self._speed[train] = speed

    def getSpeed(self, train: str) -> int:
        return self._speed[train]

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
            train: {
                "address": address,
                "connected": (
                    (client := self._clients.get(train)) is not None
                    and client.is_connected
                ),
                "speed": self._speed[train],
                "battery_percent": self._battery.get(train),
                "voltage": self._voltage.get(train),
            }
            for train, address in self._trains.items()
        }

    async def _watch(self, train: str, address: str) -> None:
        while True:
            client = BleakClient(address)
            try:
                await client.connect()
                await self._setup(train, client)
                self._clients[train] = client
                self._log.info("Connected to %s", train)
                while client.is_connected:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except BleakDeviceNotFoundError:
                pass
            except Exception as error:
                self._log.warning("%s: %s", train, error)
            finally:
                self._clients.pop(train, None)
                self._battery.pop(train, None)
                self._voltage.pop(train, None)
                if client.is_connected:
                    with suppress(Exception):
                        await client.disconnect()

            await asyncio.sleep(RECONNECT_SECONDS)

    async def _setup(self, train: str, client: BleakClient) -> None:
        def notification(_: object, data: bytearray) -> None:
            if len(data) < 3:
                return
            message_type = data[2]
            if message_type == 0x01 and len(data) >= 6 and data[3] == 0x06:
                self._battery[train] = data[5]
            elif message_type == 0x45 and len(data) >= 6 and data[3] == VOLTAGE_PORT:
                raw = int.from_bytes(data[4:6], "little")
                self._voltage[train] = round(
                    raw * VOLTAGE_MAX_V / VOLTAGE_MAX_RAW,
                    2,
                )

        await client.start_notify(HUB_CHARACTERISTIC_UUID, notification)
        await client.write_gatt_char(
            HUB_CHARACTERISTIC_UUID,
            bytes([
                0x0A,
                0x00,
                0x41,
                VOLTAGE_PORT,
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
