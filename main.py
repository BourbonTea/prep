"""Entry points for running the LAN server and client demos."""
from __future__ import annotations

import argparse
import asyncio

from lan_game.network.client import LanClient
from lan_game.network.server import LanServer


async def run_server(args):
    server = LanServer(host=args.host, port=args.port)
    await server.start()


async def run_client(args):
    async def printer(message: dict):
        print(message)

    client = LanClient(name=args.name, host=args.host, port=args.port)
    await client.connect()
    await client.listen(printer)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LAN game sandbox runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server_parser = subparsers.add_parser("server", help="Run the LAN server")
    server_parser.add_argument("--host", default="0.0.0.0")
    server_parser.add_argument("--port", type=int, default=9000)
    server_parser.set_defaults(func=run_server)

    client_parser = subparsers.add_parser("client", help="Connect to a server")
    client_parser.add_argument("name", help="Player name")
    client_parser.add_argument("--host", default="127.0.0.1")
    client_parser.add_argument("--port", type=int, default=9000)
    client_parser.set_defaults(func=run_client)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        asyncio.run(args.func(args))
    except KeyboardInterrupt:
        print("Shutting down")


if __name__ == "__main__":
    main()
