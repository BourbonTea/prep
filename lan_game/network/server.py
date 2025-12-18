"""Asyncio-powered LAN game server.

The server accepts TCP connections, manages a player lobby, and runs a simple
broadcast loop that keeps every client updated with the simulation ticks. The
network payload is a newline-delimited JSON message that includes a ``type``
field so it can be extended later.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, Optional

from lan_game.game_loop import GameLoop


@dataclass
class PlayerSession:
    """Represents a connected player."""

    name: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    address: str = field(default="unknown")

    async def send(self, payload: dict) -> None:
        message = json.dumps(payload) + "\n"
        self.writer.write(message.encode())
        await self.writer.drain()


class LanServer:
    """Minimal LAN server for the game sandbox."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9000):
        self.host = host
        self.port = port
        self.loop = GameLoop()
        self._server: Optional[asyncio.AbstractServer] = None
        self._players: Dict[str, PlayerSession] = {}

    async def start(self):
        """Start accepting connections and ticking the world."""

        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        addr = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        print(f"Server listening on {addr}")
        asyncio.create_task(self.loop.run(self._tick_world))

        async with self._server:
            await self._server.serve_forever()

    async def _tick_world(self, elapsed_game_minutes: float):
        """Broadcast a heartbeat containing the elapsed time."""

        if not self._players:
            return

        payload = {"type": "tick", "elapsed_minutes": elapsed_game_minutes}
        await asyncio.gather(*(player.send(payload) for player in self._players.values()))

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        address = writer.get_extra_info("peername")
        peer_display = f"{address[0]}:{address[1]}" if address else "unknown"
        print(f"Connection from {peer_display}")
        player_name: Optional[str] = None

        try:
            join_line = await reader.readline()
            join_data = json.loads(join_line.decode())
            name = join_data.get("name")
            if not name:
                raise ValueError("missing player name")

            if name in self._players:
                raise ValueError("name already taken")

            session = PlayerSession(name=name, reader=reader, writer=writer, address=peer_display)
            self._players[name] = session
            player_name = name
            await session.send({"type": "welcome", "message": f"joined as {name}"})
            await self._broadcast({"type": "join", "name": name}, exclude=name)

            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                await self._route_message(name, line)
        except Exception as exc:  # noqa: BLE001 broad ok for network boundary
            print(f"Error handling {peer_display}: {exc}")
        finally:
            if player_name:
                self._disconnect(player_name)

    async def _route_message(self, sender: str, raw: bytes):
        try:
            payload = json.loads(raw.decode())
        except json.JSONDecodeError:
            print(f"Ignoring invalid payload from {sender}")
            return

        payload["sender"] = sender
        await self._broadcast(payload, exclude=None)

    async def _broadcast(self, payload: dict, exclude: Optional[str]):
        tasks = []
        for name, session in list(self._players.items()):
            if name == exclude:
                continue
            tasks.append(session.send(payload))

        if tasks:
            await asyncio.gather(*tasks)

    def _disconnect(self, name: str):
        session = self._players.pop(name, None)
        if not session:
            return
        try:
            session.writer.close()
        finally:
            asyncio.create_task(self._broadcast({"type": "leave", "name": name}, exclude=name))
            print(f"Player {name} disconnected")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run the LAN game server")
    parser.add_argument("--host", default="0.0.0.0", help="Interface to bind to")
    parser.add_argument("--port", type=int, default=9000, help="Port to listen on")
    args = parser.parse_args()

    server = LanServer(host=args.host, port=args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("Server shutting down")


if __name__ == "__main__":
    main()
