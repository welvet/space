import asyncio

from backend import Automation

WAIT_TIME = 2.5
TRAIN_SPEED = 60


class Script(Automation):
    async def start(self) -> None:
        self.on_detector("A_HUB_1", "D1")
        self.on_detector("A_HUB_1", "D2")

    async def on_train(self, train: str, detector: str) -> None:
        self.event(f"{train} detected at {detector}")
        if detector == "D1":
            await asyncio.sleep(WAIT_TIME)
            await self.setSpeed(train, 0)
            other_train = "arctic_express" if train == "steam_train" else "steam_train"
            await self.setSpeed(other_train, TRAIN_SPEED)
        elif detector == "D2" and train == "steam_train":
            await self.setSwitch("A_HUB_1", "S1", "side")
        elif detector == "D2" and train == "arctic_express":
            await self.setSwitch("A_HUB_1", "S1", "straight")

    async def on_button(self, remote: str, button: str) -> None:
        pass
