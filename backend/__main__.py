from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .api import Api
from .arduino import Arduino
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
    arduino = Arduino(config["arduino"])
    api = Api(config["api"], lego_train, remote, arduino)
    automation = Script(trains, lego_train, arduino, remote)
    await lego_train.start()
    await remote.start()
    await arduino.start()
    await api.start()
    await automation.start()
    await asyncio.Event().wait()


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
