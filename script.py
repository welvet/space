from backend import Automation


class Script(Automation):
    async def start(self):
        self._count = 0
        self.on_detector("NFC_READER_582ABDD8ED94", cooldown=0)

    async def on_train(self, train, detector):
        if train == "arctic_express":
            self._count += 1
            self.event(f"Arctic Express detected at {detector}: count {self._count}")
