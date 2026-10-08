from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .api import Api
from .devices import Devices
from .lego_remote import LegoRemote
from .lego_train import LegoTrain
from script import Script

CONFIG = Path(__file__).resolve().parents[1] / "backend.json"
REMOTE_CONFIG = Path(__file__).resolve().parents[1] / "remote.json"


async def run() -> None:
    config = json.loads(CONFIG.read_text())
    trains = config["trains"]
    lego_train = LegoTrain({
        train: details["ble_address"]
        for train, details in trains.items()
    })
    remote = LegoRemote(json.loads(REMOTE_CONFIG.read_text()))
    devices = Devices(config["devices"])
    automation = Script(trains, lego_train, devices, remote)
    api = Api(config["api"], lego_train, remote, devices, automation)
    try:
        await devices.start()
        await lego_train.start()
        await remote.start()
        await api.start()
        await automation.start()
        await asyncio.Event().wait()
    finally:
        await devices.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
