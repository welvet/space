from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from .api import Api
from .arduino import Arduino
from .lego_ble import LegoBle
from script import Script

CONFIG = Path(__file__).resolve().parents[1] / "backend.json"


async def run() -> None:
    config = json.loads(CONFIG.read_text())
    trains = config["trains"]
    lego = LegoBle({
        train: details["ble_address"]
        for train, details in trains.items()
    })
    arduino = Arduino(config["arduino"])
    api = Api(config["api"], lego, arduino)
    automation = Script(trains, lego, arduino)
    await lego.start()
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
