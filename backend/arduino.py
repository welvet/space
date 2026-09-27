from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable


class Arduino:
    def __init__(self, config: dict[str, object]) -> None:
        self._host = config["host"]
        self._port = config["port"]
        self._connections: dict[str, dict[str, object]] = {}
        self._callbacks: dict[tuple[str, str], Callable[[str], None]] = {}
        self._detection_callbacks: list[
            Callable[[str, str, str, bool], None]
        ] = []
        self._server: asyncio.Server | None = None
        self._log = logging.getLogger("backend.arduino")

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._connect,
            self._host,
            self._port,
        )
        self._log.info("Listening for Arduino connections on %s:%s", self._host, self._port)

    def info(self) -> dict[str, dict[str, object]]:
        return {
            name: {
                "switches": connection["switches"],
                "detectors": connection["detectors"],
                "detected": dict(connection["detected"]),
            }
            for name, connection in self._connections.items()
        }

    async def setSwitch(
        self,
        arduino: str,
        switch: str,
        position: str,
    ) -> None:
        if position == "side":
            position = "diverge"
        writer = self._connections[arduino]["writer"]
        writer.write((json.dumps({
            "cmd": "move",
            "switch": switch,
            "position": position,
        }) + "\n").encode())
        await writer.drain()

    def on_detector(
        self,
        arduino: str,
        detector: str,
        callback: Callable[[str], None],
    ) -> None:
        self._callbacks[(arduino, detector)] = callback
        connection = self._connections.get(arduino)
        if connection is not None:
            tag = connection["detected"].get(detector)
            if tag is not None:
                callback(tag)

    def on_detection(
        self,
        callback: Callable[[str, str, str, bool], None],
    ) -> None:
        self._detection_callbacks.append(callback)

    async def _connect(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        arduino = None
        try:
            while line := await reader.readline():
                message = json.loads(line)
                event = message.get("event")

                if event == "hello":
                    arduino = message["hub"]
                    detected = {
                        tag["detector"]: tag["tag_id"]
                        for tag in message.get("detected_tags", [])
                    }
                    self._connections[arduino] = {
                        "writer": writer,
                        "switches": message.get("switches", []),
                        "detectors": message.get("detectors", []),
                        "detected": detected,
                    }
                    self._log.info("Arduino %s connected", arduino)
                    for detector, tag in detected.items():
                        self._notify_detection(arduino, detector, tag, True)
                        callback = self._callbacks.get((arduino, detector))
                        if callback is not None:
                            callback(tag)

                elif event == "tag_detected":
                    arduino = message["hub"]
                    detector = message["detector"]
                    tag = message["tag_id"]
                    self._connections[arduino]["detected"][detector] = tag
                    self._notify_detection(arduino, detector, tag, True)
                    callback = self._callbacks.get((arduino, detector))
                    if callback is not None:
                        callback(tag)

                elif event == "tag_removed":
                    arduino = message["hub"]
                    detector = message["detector"]
                    tag = message["tag_id"]
                    self._connections[arduino]["detected"].pop(
                        detector,
                        None,
                    )
                    self._notify_detection(arduino, detector, tag, False)
        except (ConnectionError, json.JSONDecodeError):
            pass
        finally:
            if (
                arduino is not None
                and self._connections.get(arduino, {}).get("writer") is writer
            ):
                self._connections.pop(arduino)
                self._log.info("Arduino %s disconnected", arduino)
            writer.close()
            await writer.wait_closed()

    def _notify_detection(
        self,
        arduino: str,
        detector: str,
        tag: str,
        detected: bool,
    ) -> None:
        for callback in self._detection_callbacks:
            callback(arduino, detector, tag, detected)
