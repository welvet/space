from backend import Automation


class Script(Automation):
    async def start(self) -> None:
        pass

    async def on_train(self, train: str) -> None:
        pass

    async def on_button(self, remote: str, button: str) -> None:
        pass
