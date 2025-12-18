"""Client helper for connecting to the LAN server."""
from __future__ import annotations

import asyncio
import json
from typing import Callable, Coroutine, Optional


class LanClient:
    """Connects to the LAN server and handles JSON messages."""

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 9000):
        self.name = name
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        await self._send({"name": self.name})

    async def listen(self, on_message: Callable[[dict], Coroutine[None, None, None]]):
        if not self.reader:
            raise RuntimeError("connect before calling listen")

        while not self.reader.at_eof():
            line = await self.reader.readline()
            if not line:
                break
            try:
                payload = json.loads(line.decode())
            except json.JSONDecodeError:
                continue
            await on_message(payload)

    async def send_action(self, payload: dict):
        payload.setdefault("type", "action")
        await self._send(payload)

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def _send(self, payload: dict):
        if not self.writer:
            raise RuntimeError("not connected")
        message = json.dumps(payload) + "\n"
        self.writer.write(message.encode())
        await self.writer.drain()


def main():
    import argparse

    async def printer(message: dict):
        print(f"[server] {message}")

    parser = argparse.ArgumentParser(description="Connect to the LAN game server")
    parser.add_argument("name", help="Player name to present to the server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=9000, help="Server port")
    args = parser.parse_args()

    client = LanClient(name=args.name, host=args.host, port=args.port)

    async def run_client():
        await client.connect()
        print(f"Connected to {args.host}:{args.port} as {args.name}")
        await client.listen(printer)

    try:
        asyncio.run(run_client())
    except KeyboardInterrupt:
        print("Disconnected")


if __name__ == "__main__":
    main()
