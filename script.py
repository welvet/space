import asyncio

from backend import Automation


class Script(Automation):
    async def start(self):
        self._count = 0
        self._speed_lock = asyncio.Lock()
        self.on_detector("NFC_READER_582ABDD8ED94", cooldown=0)

    async def on_train(self, train, detector):
        if train == "arctic_express":
            self._count += 1
            self.event(f"Arctic Express detected at {detector}: count {self._count}")

    async def on_button(self, remote, button):
        if remote != "Handset":
            return
        controls = {
            "left_plus": ("arctic_express", 20),
            "left_minus": ("arctic_express", -20),
            "left_stop": ("arctic_express", 0),
            "right_plus": ("steam_train", 20),
            "right_minus": ("steam_train", -20),
            "right_stop": ("steam_train", 0),
        }
        if button not in controls:
            return
        train, delta = controls[button]
        async with self._speed_lock:
            speed = max(-100, min(100, self.getSpeed(train) + delta)) if delta else 0
            await self.setSpeed(train, speed)
            self.event(f"{train} speed changed to {speed}")
