"""Maze-based tag game rules and state tracking."""
from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set, Tuple

GridPos = Tuple[int, int]


class Role(str, Enum):
    TAGGER = "tagger"
    RUNNER = "runner"


BASE_MOVE_SECONDS = 0.5  # one tile at speed 1.0
TAGGER_SPEED = 1.5
RUNNER_SPEED = 1.0
TAGGER_VIEW_RADIUS = 5
RUNNER_VIEW_RADIUS = 3
ALERT_RANGE = 5
TIME_LIMIT_SECONDS = 5 * 60
MAX_SIZE = 100


class Maze:
    """Generates and stores a simple perfect maze."""

    def __init__(self, width: int = 30, height: int = 30):
        if width <= 0 or height <= 0 or width > MAX_SIZE or height > MAX_SIZE:
            raise ValueError("maze dimensions must be between 1 and 100")
        self.width = width
        self.height = height
        # 1 = wall, 0 = floor
        self.grid: List[List[int]] = [[1 for _ in range(width)] for _ in range(height)]
        self._generate()

    def _generate(self):
        """Recursive backtracker over a grid of cells spaced by 2."""

        def carve(x: int, y: int):
            self.grid[y][x] = 0
            dirs = [(2, 0), (-2, 0), (0, 2), (0, -2)]
            random.shuffle(dirs)
            for dx, dy in dirs:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < self.width and 0 <= ny < self.height):
                    continue
                if self.grid[ny][nx] == 0:
                    continue
                mx, my = x + dx // 2, y + dy // 2
                self.grid[my][mx] = 0
                carve(nx, ny)

        start_x = random.randrange(0, self.width, 2)
        start_y = random.randrange(0, self.height, 2)
        carve(start_x, start_y)

    def is_wall(self, pos: GridPos) -> bool:
        x, y = pos
        if not (0 <= x < self.width and 0 <= y < self.height):
            return True
        return self.grid[y][x] == 1

    def random_open_cell(self, occupied: Set[GridPos]) -> GridPos:
        attempts = 0
        while attempts < 5000:
            x = random.randrange(self.width)
            y = random.randrange(self.height)
            cell = (x, y)
            if not self.is_wall(cell) and cell not in occupied:
                return cell
            attempts += 1
        raise RuntimeError("failed to find empty cell for spawn")


@dataclass
class PlayerState:
    name: str
    role: Role
    position: GridPos
    heading: GridPos = (1, 0)
    eliminated: bool = False
    move_buffer: float = 0.0
    pending_direction: Optional[str] = None

    @property
    def speed(self) -> float:
        return TAGGER_SPEED if self.role == Role.TAGGER else RUNNER_SPEED

    def queue_direction(self, direction: Optional[str]):
        if direction:
            self.pending_direction = direction


class GameState:
    """Complete world state for the tag maze game."""

    def __init__(self, width: int = 30, height: int = 30, max_players: int = 4):
        self.maze = Maze(width, height)
        self.players: Dict[str, PlayerState] = {}
        self.max_players = max_players
        self.time_remaining = TIME_LIMIT_SECONDS
        self.loop_task: Optional[asyncio.Task] = None

    async def loop(self, tick):
        """Simple fixed-step loop using real seconds."""

        tick_interval = BASE_MOVE_SECONDS
        last = asyncio.get_running_loop().time()
        while True:
            now = asyncio.get_running_loop().time()
            elapsed = now - last
            if elapsed < tick_interval:
                await asyncio.sleep(tick_interval - elapsed)
                continue
            await tick(elapsed)
            last = now

    def add_player(self, name: str) -> dict:
        if len(self.players) >= self.max_players:
            raise ValueError("lobby full")

        occupied = {p.position for p in self.players.values() if not p.eliminated}
        spawn = self.maze.random_open_cell(occupied)

        role = Role.TAGGER if not any(p.role == Role.TAGGER for p in self.players.values()) else Role.RUNNER
        player = PlayerState(name=name, role=role, position=spawn)
        self.players[name] = player

        return {
            "role": role.value,
            "position": spawn,
            "maze_size": (self.maze.width, self.maze.height),
        }

    def remove_player(self, name: str):
        self.players.pop(name, None)

    def queue_move(self, name: str, direction: Optional[str]):
        player = self.players.get(name)
        if player and not player.eliminated:
            player.queue_direction(direction)

    def tick(self, elapsed_seconds: float) -> List[str]:
        """Advance movement, resolve captures, and countdown timer."""

        self.time_remaining = max(0.0, self.time_remaining - elapsed_seconds)
        eliminated_now: List[str] = []

        for player in self.players.values():
            if player.eliminated:
                continue
            step_budget = player.speed * (elapsed_seconds / BASE_MOVE_SECONDS) + player.move_buffer
            whole_steps = int(step_budget)
            player.move_buffer = step_budget - whole_steps

            move_vector = self._direction_to_vec(player.pending_direction)
            if move_vector != (0, 0):
                player.heading = move_vector

            for _ in range(whole_steps):
                if move_vector == (0, 0):
                    break
                next_pos = (player.position[0] + move_vector[0], player.position[1] + move_vector[1])
                if self.maze.is_wall(next_pos):
                    break
                player.position = next_pos

        tagger_positions = {p.position for p in self.players.values() if p.role == Role.TAGGER and not p.eliminated}
        for player in self.players.values():
            if player.role == Role.RUNNER and not player.eliminated and player.position in tagger_positions:
                player.eliminated = True
                eliminated_now.append(player.name)

        return eliminated_now

    def snapshot_for(self, name: str) -> Optional[dict]:
        viewer = self.players.get(name)
        if not viewer:
            return None

        visibility = self._visible_tiles(viewer)
        visible_players = []
        for player in self.players.values():
            if player.eliminated:
                continue
            if player.name == name or player.position in visibility["floor"]:
                visible_players.append(
                    {
                        "name": player.name,
                        "role": player.role.value,
                        "position": player.position,
                    }
                )

        return {
            "type": "state",
            "you": name,
            "role": viewer.role.value,
            "position": viewer.position,
            "maze_size": (self.maze.width, self.maze.height),
            "visible_floor": sorted(list(visibility["floor"])),
            "visible_walls": sorted(list(visibility["walls"])),
            "players": visible_players,
            "warning": self._should_warn(viewer),
            "time_remaining": self.time_remaining,
            "eliminated": viewer.eliminated,
            "winner": self._winner(),
        }

    def _winner(self) -> Optional[str]:
        active_runners = [p for p in self.players.values() if p.role == Role.RUNNER and not p.eliminated]
        active_taggers = [p for p in self.players.values() if p.role == Role.TAGGER and not p.eliminated]
        if not active_taggers:
            return None
        if not active_runners:
            return Role.TAGGER.value
        if self.time_remaining <= 0:
            return Role.RUNNER.value
        return None

    def _visible_tiles(self, viewer: PlayerState) -> dict:
        radius = TAGGER_VIEW_RADIUS if viewer.role == Role.TAGGER else RUNNER_VIEW_RADIUS
        floor: Set[GridPos] = set()
        walls: Set[GridPos] = set()

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                target = (viewer.position[0] + dx, viewer.position[1] + dy)
                if not self._within_range(viewer, target, radius):
                    continue
                if self._blocked(viewer.position, target):
                    continue
                if self.maze.is_wall(target):
                    walls.add(target)
                else:
                    floor.add(target)
        return {"floor": floor, "walls": walls}

    def _within_range(self, viewer: PlayerState, target: GridPos, radius: int) -> bool:
        dist = math.hypot(target[0] - viewer.position[0], target[1] - viewer.position[1])
        if dist > radius + 0.001:
            return False
        if viewer.role != Role.TAGGER:
            return True

        hx, hy = viewer.heading
        vx, vy = target[0] - viewer.position[0], target[1] - viewer.position[1]
        dot = hx * vx + hy * vy
        if dist == 0:
            return True
        cos_angle = dot / (dist * math.hypot(hx, hy) if math.hypot(hx, hy) else 1)
        return cos_angle >= 0  # front 180 degrees

    def _blocked(self, start: GridPos, end: GridPos) -> bool:
        """Simple Bresenham line of sight; ignore the starting tile."""

        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        x, y = x0, y0
        while (x, y) != (x1, y1):
            if (x, y) != start and self.maze.is_wall((x, y)):
                return True
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy
        return False

    def _should_warn(self, viewer: PlayerState) -> bool:
        if viewer.role != Role.RUNNER or viewer.eliminated:
            return False
        for player in self.players.values():
            if player.role != Role.TAGGER or player.eliminated:
                continue
            manhattan = abs(player.position[0] - viewer.position[0]) + abs(
                player.position[1] - viewer.position[1]
            )
            if manhattan <= ALERT_RANGE:
                return True
        return False

    def _direction_to_vec(self, direction: Optional[str]) -> GridPos:
        mapping = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            None: (0, 0),
        }
        return mapping.get(direction, (0, 0))
