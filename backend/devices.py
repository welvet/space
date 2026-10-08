from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
from collections.abc import Callable

import ifaddr
from zeroconf import IPVersion, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf


class Devices:
    def __init__(self, config: dict[str, object]) -> None:
        self._host = config["host"]
        self._port = config["port"]
        self._interface = config.get("interface")
        self._connections: dict[str, dict[str, object]] = {}
        self._callbacks: dict[str, Callable[[str], None]] = {}
        self._detection_callbacks: list[Callable[[str, str, bool], None]] = []
        self._server: asyncio.Server | None = None
        self._discovery: AsyncZeroconf | None = None
        self._log = logging.getLogger("backend.devices")

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._connect, self._host, self._port)
        addresses = [
            ip.ip
            for adapter in ifaddr.get_adapters()
            if self._interface is None or adapter.name == self._interface
            for ip in adapter.ips
            if ip.is_IPv4 and not ipaddress.ip_address(ip.ip).is_loopback
            and (self._host == "0.0.0.0" or self._host == ip.ip)
        ]
        if not addresses:
            raise RuntimeError("Device listener needs a LAN IPv4 address")
        self._discovery = AsyncZeroconf(interfaces=addresses, ip_version=IPVersion.V4Only)
        service = ServiceInfo(
            "_space._tcp.local.",
            "Space._space._tcp.local.",
            parsed_addresses=addresses,
            port=self._server.sockets[0].getsockname()[1],
            server="space-backend.local.",
        )
        await self._discovery.async_register_service(service)
        self._log.info("Listening for devices on %s:%s", self._host, service.port)

    async def stop(self) -> None:
        if self._discovery is not None:
            await self._discovery.async_close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        for connection in list(self._connections.values()):
            connection["writer"].close()

    def info(self) -> dict[str, dict[str, object]]:
        return {
            name: {"type": connection["type"], **connection["state"]}
            for name, connection in self._connections.items()
        }

    async def setSwitch(self, device: str, position: str) -> None:
        writer = self._connections[device]["writer"]
        writer.write((json.dumps({"cmd": "move", "position": position}) + "\n").encode())
        await writer.drain()

    def on_detector(self, device: str, callback: Callable[[str], None]) -> None:
        self._callbacks[device] = callback
        connection = self._connections.get(device)
        if connection is not None and connection["state"].get("tag_id") is not None:
            callback(connection["state"]["tag_id"])

    def on_detection(self, callback: Callable[[str, str, bool], None]) -> None:
        self._detection_callbacks.append(callback)

    async def _connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        device = None
        try:
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=15)
                if not line:
                    break
                message = json.loads(line)
                if not isinstance(message, dict):
                    break
                event = message.get("event")
                if event in ("hello", "state"):
                    if not isinstance(message.get("ready"), bool):
                        break
                    if message.get("tag_id") is not None and not isinstance(message["tag_id"], str):
                        break
                if event == "hello":
                    if device is not None:
                        break
                    name = message["device"]
                    if not isinstance(name, str) or not name:
                        break
                    if message["type"] not in ("NFC_READER", "MOTOR", "SWITCH"):
                        break
                    device = name
                    previous = self._connections.get(device)
                    if previous is not None:
                        previous["writer"].close()
                    self._connections[device] = {
                        "writer": writer,
                        "type": message["type"],
                        "state": {},
                    }
                    self._log.info("Device %s connected", device)
                    self._state(device, message)
                elif event == "state" and device is not None:
                    if self._connections.get(device, {}).get("writer") is not writer:
                        break
                    self._state(device, message)
                elif event == "ping" and device is not None:
                    if self._connections.get(device, {}).get("writer") is not writer:
                        break
                    writer.write(b'{"event":"pong"}\n')
                    await asyncio.wait_for(writer.drain(), timeout=15)
        except (ConnectionError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
        finally:
            if device is not None and self._connections.get(device, {}).get("writer") is writer:
                self._connections.pop(device)
                self._log.info("Device %s disconnected", device)
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    def _state(self, device: str, message: dict[str, object]) -> None:
        connection = self._connections[device]
        previous = connection["state"].get("tag_id")
        tag = message.get("tag_id")
        connection["state"] = {
            key: value for key, value in message.items()
            if key not in ("event", "device", "type")
        }
        if connection["type"] != "NFC_READER":
            return
        if previous == tag:
            return
        if previous is not None:
            self._notify_detection(device, previous, False)
        if tag is not None:
            self._notify_detection(device, tag, True)
            callback = self._callbacks.get(device)
            if callback is not None:
                callback(tag)

    def _notify_detection(self, device: str, tag: str, detected: bool) -> None:
        for callback in self._detection_callbacks:
            callback(device, tag, detected)
