"""Entry points for running the LAN server and client demos."""
from __future__ import annotations

import argparse
import asyncio
import socket
from contextlib import suppress

import pygame

from lan_game.client_app import run_lobby
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
    raw_args = list(argv) if argv is not None else []

    if raw_args:
        parser = build_parser()
        args = parser.parse_args(raw_args)
        if args.command:
            try:
                asyncio.run(args.func(args))
            except KeyboardInterrupt:
                print("Shutting down")
            return

    # No (or unrecognized) args: launch the Pygame-driven menu
    asyncio.run(run_launcher())


if __name__ == "__main__":
    main()


# --- Pygame launcher (replaces terminal prompts) ---


class InputBox:
    def __init__(self, x: int, y: int, w: int, h: int, text: str = "", placeholder: str = ""):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = (80, 80, 80)
        self.color_active = (120, 180, 255)
        self.color = self.color_inactive
        self.text = text
        self.placeholder = placeholder
        self.active = False
        self.font = pygame.font.SysFont("malgungothic", 18)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            self.color = self.color_active if self.active else self.color_inactive
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
                self.color = self.color_inactive
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode

    def draw(self, screen):
        txt = self.text if self.text else self.placeholder
        txt_surface = self.font.render(txt, True, (230, 230, 230))
        screen.blit(txt_surface, (self.rect.x + 5, self.rect.y + 5))
        pygame.draw.rect(screen, self.color, self.rect, 2)

    def value_or(self, default: str) -> str:
        return self.text.strip() or default


async def run_launcher():
    """Full-screen Pygame menu for host/join/settings/exit."""

    pygame.init()
    screen = pygame.display.set_mode((760, 520))
    pygame.display.set_caption("LAN Game Launcher")
    font = pygame.font.SysFont("malgungothic", 20)
    clock = pygame.time.Clock()

    mode = "menu"
    message = ""

    # Forms
    host_name_box = InputBox(320, 200, 200, 32, text="Host", placeholder="닉네임")
    host_port_box = InputBox(320, 250, 200, 32, text="9000", placeholder="포트")

    join_name_box = InputBox(320, 200, 200, 32, text="Player", placeholder="닉네임")
    join_host_box = InputBox(320, 250, 200, 32, text="127.0.0.1", placeholder="호스트 주소")
    join_port_box = InputBox(320, 300, 200, 32, text="9000", placeholder="포트")

    BUTTONS = {
        "host": pygame.Rect(40, 120, 200, 50),
        "join": pygame.Rect(40, 190, 200, 50),
        "settings": pygame.Rect(40, 260, 200, 50),
        "exit": pygame.Rect(40, 330, 200, 50),
        "back": pygame.Rect(40, 440, 120, 40),
        "go": pygame.Rect(560, 440, 120, 40),
    }

    def draw_button(rect, label, active=True):
        color = (70, 120, 220) if active else (60, 60, 60)
        pygame.draw.rect(screen, color, rect, border_radius=6)
        txt = font.render(label, True, (255, 255, 255))
        screen.blit(txt, (rect.x + 12, rect.y + 12))

    async def do_host():
        nonlocal message
        try:
            port = int(host_port_box.value_or("9000"))
        except ValueError:
            message = "포트는 숫자여야 합니다."
            return
        name = host_name_box.value_or("Host")
        server = LanServer(host="0.0.0.0", port=port)
        server_task = asyncio.create_task(server.start())
        try:
            await asyncio.sleep(0.1)
            await run_lobby(name=name, host="127.0.0.1", port=port, is_host=True)
        except Exception as exc:  # noqa: BLE001
            message = f"호스트 오류: {exc}"
        finally:
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task

    async def do_join():
        nonlocal message
        try:
            port = int(join_port_box.value_or("9000"))
        except ValueError:
            message = "포트는 숫자여야 합니다."
            return
        host = join_host_box.value_or("127.0.0.1")
        name = join_name_box.value_or("Player")
        try:
            await run_lobby(name=name, host=host, port=port, is_host=False)
        except Exception as exc:  # noqa: BLE001
            message = f"접속 오류: {exc}"

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            if mode == "menu":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if BUTTONS["host"].collidepoint(event.pos):
                        mode = "host"
                        message = ""
                    elif BUTTONS["join"].collidepoint(event.pos):
                        mode = "join"
                        message = ""
                    elif BUTTONS["settings"].collidepoint(event.pos):
                        mode = "settings"
                        message = "환경 설정은 아직 준비 중입니다."
                    elif BUTTONS["exit"].collidepoint(event.pos):
                        pygame.quit()
                        return
            else:
                host_name_box.handle_event(event)
                host_port_box.handle_event(event)
                join_name_box.handle_event(event)
                join_host_box.handle_event(event)
                join_port_box.handle_event(event)

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if BUTTONS["back"].collidepoint(event.pos):
                        mode = "menu"
                        message = ""
                    elif BUTTONS["go"].collidepoint(event.pos):
                        if mode == "host":
                            await do_host()
                        elif mode == "join":
                            await do_join()

        screen.fill((15, 15, 25))

        title = font.render("LAN Game Launcher", True, (255, 255, 255))
        screen.blit(title, (40, 40))

        if mode == "menu":
            draw_button(BUTTONS["host"], "게임 시작 - 호스트")
            draw_button(BUTTONS["join"], "게임 시작 - 참여")
            draw_button(BUTTONS["settings"], "환경 설정")
            draw_button(BUTTONS["exit"], "종료")
        elif mode == "host":
            draw_button(BUTTONS["back"], "뒤로")
            draw_button(BUTTONS["go"], "호스트 열기")
            font2 = pygame.font.SysFont("malgungothic", 18)
            screen.blit(font2.render("닉네임", True, (230, 230, 230)), (240, 205))
            screen.blit(font2.render("포트", True, (230, 230, 230)), (240, 255))
            host_name_box.draw(screen)
            host_port_box.draw(screen)
        elif mode == "join":
            draw_button(BUTTONS["back"], "뒤로")
            draw_button(BUTTONS["go"], "접속")
            font2 = pygame.font.SysFont("malgungothic", 18)
            screen.blit(font2.render("닉네임", True, (230, 230, 230)), (240, 205))
            screen.blit(font2.render("호스트 주소", True, (230, 230, 230)), (240, 255))
            screen.blit(font2.render("포트", True, (230, 230, 230)), (240, 305))
            join_name_box.draw(screen)
            join_host_box.draw(screen)
            join_port_box.draw(screen)
        elif mode == "settings":
            draw_button(BUTTONS["back"], "뒤로")
            screen.blit(font.render("환경 설정은 추후 제공됩니다.", True, (230, 230, 230)), (40, 120))

        if message:
            warn = font.render(message, True, (255, 180, 80))
            screen.blit(warn, (40, 480 - 40))

        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)
