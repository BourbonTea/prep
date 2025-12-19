"""Entry points for running the LAN server and client demos."""
from __future__ import annotations

import argparse
import asyncio
import socket
from contextlib import suppress

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
    subparsers = parser.add_subparsers(dest="command")

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
    raw_args = list(argv) if argv is not None else None
    if raw_args is None:
        raw_args = []

    if raw_args:
        parser = build_parser()
        try:
            args = parser.parse_args(raw_args)
        except SystemExit:
            # Fallback to the interactive menu if parsing fails or subcommand missing.
            asyncio.run(interactive_menu())
            return

        if args.command:
            try:
                asyncio.run(args.func(args))
            except KeyboardInterrupt:
                print("Shutting down")
            return

    # No arguments (or parse failed) — show interactive menu.
    asyncio.run(interactive_menu())


if __name__ == "__main__":
    main()


# --- Interactive menu helpers ---


async def interactive_menu():
    """Present the interactive lobby-driven flow requested in the spec."""

    while True:
        print("\n==== LAN Game ====")
        print("1) 게임 시작 - 호스트")
        print("2) 게임 시작 - 참여")
        print("3) 환경 설정")
        print("4) 종료")
        choice = input("메뉴 번호를 선택하세요: ").strip()

        if choice == "1":
            await host_flow()
        elif choice == "2":
            await join_flow()
        elif choice == "3":
            show_settings()
        elif choice == "4":
            print("종료합니다.")
            return
        else:
            print("잘못된 선택입니다. 다시 선택해주세요.")


def pick_nickname(default: str = "Player") -> str:
    while True:
        name = input(f"닉네임을 입력하세요 ({default}): ").strip() or default
        if name:
            return name
        print("닉네임은 비워둘 수 없습니다.")


async def host_flow():
    port = prompt_int("호스트 포트 (기본 9000): ", default=9000)
    nickname = pick_nickname("Host")
    listen_host = "0.0.0.0"

    server = LanServer(host=listen_host, port=port)
    server_task = asyncio.create_task(server.start())

    try:
        display_addresses(port)
        await asyncio.sleep(0.1)  # let server start
        await lobby_chat(nickname, host="127.0.0.1", port=port)
    finally:
        server_task.cancel()
        with suppress(asyncio.CancelledError):
            await server_task


async def join_flow():
    host = input("접속할 호스트 주소를 입력하세요 (예: 192.168.0.10): ").strip() or "127.0.0.1"
    port = prompt_int("호스트 포트 (기본 9000): ", default=9000)
    nickname = pick_nickname()
    await lobby_chat(nickname, host=host, port=port)


def display_addresses(port: int):
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except OSError:
        local_ip = "127.0.0.1"

    print("\n서버가 시작되었습니다. 친구에게 아래 주소를 알려주세요:")
    print(f"- 로컬 주소: {local_ip}:{port}")
    print(f"- 루프백 주소: 127.0.0.1:{port}")
    print("로비에서 채팅을 시작하세요. '/quit'으로 종료합니다.")


def show_settings():
    print("\n환경 설정 (데모용):")
    print("- 별도의 설정 옵션이 없습니다. 기본값으로 실행됩니다.")


def prompt_int(prompt: str, default: int) -> int:
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("잘못된 숫자입니다. 기본값을 사용합니다.")
        return default


async def lobby_chat(nickname: str, host: str, port: int):
    client = LanClient(name=nickname, host=host, port=port)

    async def listener():
        async def printer(message: dict):
            msg_type = message.get("type")
            sender = message.get("name") or message.get("sender") or "server"
            content = message.get("message") or message.get("text") or ""

            if msg_type == "welcome":
                print(f"[알림] {content}")
            elif msg_type == "join":
                print(f"[알림] {message.get('name')} 님이 입장했습니다.")
            elif msg_type == "leave":
                print(f"[알림] {message.get('name')} 님이 퇴장했습니다.")
            elif msg_type == "tick":
                return
            else:
                print(f"[{sender}] {content}")

        await client.listen(printer)

    try:
        await client.connect()
        print(f"\n{host}:{port} 로 연결되었습니다. '/quit'으로 로비를 나갑니다.")
        listener_task = asyncio.create_task(listener())

        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, input, "")
            if line.strip() == "/quit":
                break
            if line.strip():
                await client.send_action({"type": "chat", "text": line.strip()})

    except Exception as exc:  # noqa: BLE001 user-facing feedback
        print(f"연결 중 오류가 발생했습니다: {exc}")
    finally:
        await client.close()
        with suppress(asyncio.CancelledError):
            if "listener_task" in locals():
                listener_task.cancel()
                await listener_task
        print("로비에서 나왔습니다.")
