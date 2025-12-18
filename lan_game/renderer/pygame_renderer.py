"""Minimal Pygame renderer stub for the 2D grid."""
from __future__ import annotations

import pygame
from typing import Iterable, Tuple

CELL_SIZE = 32
GRID_COLOR = (40, 40, 40)
BG_COLOR = (12, 12, 12)
OBJECT_COLOR = (200, 200, 120)
PLAYER_COLOR = (80, 200, 255)


def draw_grid(screen: pygame.Surface, width: int, height: int):
    screen.fill(BG_COLOR)
    for x in range(0, width, CELL_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (x, 0), (x, height))
    for y in range(0, height, CELL_SIZE):
        pygame.draw.line(screen, GRID_COLOR, (0, y), (width, y))


def draw_objects(screen: pygame.Surface, positions: Iterable[Tuple[int, int]], color=OBJECT_COLOR):
    for grid_x, grid_y in positions:
        rect = pygame.Rect(grid_x * CELL_SIZE, grid_y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(screen, color, rect)


def draw_players(screen: pygame.Surface, positions: Iterable[Tuple[int, int]]):
    draw_objects(screen, positions, color=PLAYER_COLOR)


def preview():
    """Render a static preview of the grid and some placeholders."""

    pygame.init()
    width, height = 640, 480
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("LAN Game Renderer Preview")

    clock = pygame.time.Clock()
    running = True
    objects = [(3, 3), (7, 5), (10, 2)]
    players = [(5, 6)]

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        draw_grid(screen, width, height)
        draw_objects(screen, objects)
        draw_players(screen, players)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    preview()
