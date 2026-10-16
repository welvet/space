import asyncio

from backend import Automation


class Script(Automation):
    async def start(self):
        self._count = 0
        self._switch_lock = asyncio.Lock()
        self._switch = "SWITCH_8C94DF7E5524"
        self._angle = self._devices.info().get(self._switch, {}).get("angle", 0)
        self.on_detector("NFC_READER_582ABDD8ED94", cooldown=0)

    async def on_train(self, train, detector):
        if train == "arctic_express":
            self._count += 1
            self.event(f"Arctic Express detected at {detector}: count {self._count}")

    async def on_button(self, remote, button):
        if remote != "Handset":
            return
        if button not in ("left_plus", "left_minus", "right_plus", "right_minus", "right_stop"):
            return
        async with self._switch_lock:
            if self._switch not in self._devices.info():
                self.event(f"{self._switch} is disconnected")
                return
            if button.startswith("left_"):
                power = int(button == "left_plus")
                await self.runSwitch(self._switch, [{"cmd": "power", "value": power}])
                self.event(f"{self._switch} power {'on' if power else 'off'}")
                return
            delta = 10 if button == "right_plus" else -10
            angle = 0 if button == "right_stop" else max(-90, min(90, self._angle + delta))
            await self.runSwitch(self._switch, [{"cmd": "rotate", "value": angle}])
            self._angle = angle
            self.event(f"{self._switch} angle {angle}°")
