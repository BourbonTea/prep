"""Pygame-driven lobby UI for hosting or joining the LAN game."""
from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

import pygame

from lan_game.network.client import LanClient

WIDTH, HEIGHT = 720, 480
BG = (20, 20, 20)
PANEL = (35, 35, 35)
TEXT = (230, 230, 230)
ACCENT = (80, 200, 255)
BUTTON = (60, 60, 60)
BUTTON_ACTIVE = (70, 120, 220)
WARNING = (200, 80, 80)


@dataclass
class LobbyState:
    name: str
    is_host: bool
    players: List[str] = field(default_factory=list)
    chat: Deque[str] = field(default_factory=lambda: deque(maxlen=50))
    warning: bool = False
    started: bool = False
    host: Optional[str] = None
    countdown: float = 5 * 60


async def run_lobby(name: str, host: str, port: int, is_host: bool):
    client = LanClient(name=name, host=host, port=port)
    lobby = LobbyState(name=name, is_host=is_host)
    chat_input = ""

    await client.connect()
    lobby.chat.append("서버에 연결되었습니다.")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Lobby")
    font = pygame.font.SysFont("malgungothic", 18)

    async def listen():
        async def handle(message: dict):
            msg_type = message.get("type")
            if msg_type == "join":
                lobby.chat.append(f"{message.get('name')} 님이 입장했습니다.")
            elif msg_type == "leave":
                lobby.chat.append(f"{message.get('name')} 님이 퇴장했습니다.")
            elif msg_type == "chat":
                lobby.chat.append(f"{message.get('sender')}: {message.get('text')}")
            elif msg_type == "state":
                lobby.players = message.get("players_present", lobby.players)
                lobby.warning = bool(message.get("warning"))
                lobby.started = bool(message.get("started"))
                lobby.countdown = float(message.get("time_remaining", lobby.countdown))
                lobby.host = message.get("host", lobby.host)
            elif msg_type == "game_start":
                lobby.started = True
                lobby.chat.append("게임이 시작되었습니다!")
            elif msg_type == "welcome":
                lobby.chat.append(message.get("message", "환영합니다."))
            elif msg_type == "spawn":
                role = message.get("role", "runner")
                lobby.chat.append(f"당신의 역할은 {role} 입니다.")
        await client.listen(handle)

    listener = asyncio.create_task(listen())

    async def send_chat(text: str):
        await client.send_action({"type": "chat", "text": text})

    async def send_start():
        await client.send_action({"type": "start"})

    running = True
    clock = pygame.time.Clock()

    def draw_text(surface, text, x, y, color=TEXT):
        img = font.render(text, True, color)
        surface.blit(img, (x, y))

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN:
                    if chat_input.strip():
                        await send_chat(chat_input.strip())
                        lobby.chat.append(f"{name}: {chat_input.strip()}")
                        chat_input = ""
                elif event.key == pygame.K_BACKSPACE:
                    chat_input = chat_input[:-1]
                else:
                    chat_input += event.unicode
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if is_host and not lobby.started and 20 <= mx <= 140 and HEIGHT - 50 <= my <= HEIGHT - 20:
                    await send_start()
                if 160 <= mx <= 260 and HEIGHT - 50 <= my <= HEIGHT - 20:
                    running = False

        screen.fill(BG)

        # Players panel
        pygame.draw.rect(screen, PANEL, (20, 20, 200, HEIGHT - 90))
        draw_text(screen, "플레이어 (최대 4)", 30, 30, ACCENT)
        for idx, player in enumerate(lobby.players):
            label = f"{player}" + (" (호스트)" if player == lobby.host else "")
            draw_text(screen, label, 30, 60 + idx * 22)

        # Chat panel
        pygame.draw.rect(screen, PANEL, (230, 20, WIDTH - 250, HEIGHT - 130))
        draw_text(screen, "채팅", 240, 30, ACCENT)
        for idx, line in enumerate(list(lobby.chat)[-15:]):
            draw_text(screen, line, 240, 60 + idx * 20)

        # Input box
        pygame.draw.rect(screen, BUTTON, (230, HEIGHT - 100, WIDTH - 250, 30))
        draw_text(screen, chat_input + ("|" if pygame.time.get_ticks() % 1000 < 500 else ""), 240, HEIGHT - 95)

        # Buttons
        start_color = BUTTON_ACTIVE if is_host and not lobby.started else BUTTON
        pygame.draw.rect(screen, start_color, (20, HEIGHT - 50, 120, 30))
        draw_text(screen, "Start (Host)", 30, HEIGHT - 45)

        pygame.draw.rect(screen, BUTTON, (160, HEIGHT - 50, 100, 30))
        draw_text(screen, "나가기", 170, HEIGHT - 45)

        # Status
        status_y = HEIGHT - 80
        if lobby.warning:
            draw_text(screen, "경고: 술래가 근처에 있습니다!", 240, status_y, WARNING)
        draw_text(screen, f"타이머: {int(lobby.countdown)}s", WIDTH - 200, status_y)
        draw_text(screen, f"역할: {'호스트' if is_host else '참여자'}", WIDTH - 200, status_y + 25)

        pygame.display.flip()
        clock.tick(30)
        await asyncio.sleep(0)

    listener.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await listener
    await client.close()
    pygame.quit()
