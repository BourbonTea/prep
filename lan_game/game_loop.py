"""
Core game loop utilities.

This module implements a tick-based loop that advances game time faster than
real time. The intended mapping is 1 second of real time equals
5 minutes of in-game time with a full world tick every 0.5 seconds.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class GameClock:
    """Tracks the passage of in-game time.

    Attributes:
        minutes_per_real_second: How many in-game minutes elapse each real second.
    """

    minutes_per_real_second: float = 5.0

    def advance(self, real_seconds: float) -> float:
        """Convert real-time seconds into in-game minutes.

        Args:
            real_seconds: Seconds passed in real time.

        Returns:
            The equivalent in-game minutes.
        """

        return real_seconds * self.minutes_per_real_second


class GameLoop:
    """Runs a fixed-step update loop.

    The loop calls a provided coroutine every ``tick_interval`` seconds, and
    passes the elapsed in-game minutes since the previous tick. This keeps
    simulation logic decoupled from rendering or network transport.
    """

    def __init__(self, tick_interval: float = 0.5, clock: Optional[GameClock] = None):
        self.tick_interval = tick_interval
        self.clock = clock or GameClock()
        self._running = False

    async def run(self, tick: Callable[[float], Awaitable[None]]):
        """Run the loop until :meth:`stop` is invoked.

        Args:
            tick: Coroutine invoked every tick with the elapsed game minutes.
        """

        self._running = True
        last_tick = asyncio.get_running_loop().time()
        next_tick = last_tick

        while self._running:
            now = asyncio.get_running_loop().time()
            if now < next_tick:
                await asyncio.sleep(next_tick - now)
                continue

            elapsed_real = now - last_tick
            elapsed_game_minutes = self.clock.advance(elapsed_real)
            await tick(elapsed_game_minutes)

            last_tick = now
            next_tick += self.tick_interval

    def stop(self):
        """Request the loop to stop after the current tick."""

        self._running = False
