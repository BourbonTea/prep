# prep

A minimal LAN-ready sandbox for a 2D grid-based tag maze game. It focuses on
the network plumbing and simple simulation primitives so the hide-and-seek
rules are easy to extend.

## Features
- Asyncio TCP server that accepts LAN clients and broadcasts JSON messages.
- Maze generation up to 100x100 cells with random spawns and one tagger.
- Real-time 0.5s ticks that drive per-player snapshots with vision and warnings.
- Pygame renderer stub that draws a grid and placeholder objects.

## Getting started
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python main.py server --host 0.0.0.0 --port 9000
   ```

3. Connect a client from another terminal or machine on the LAN:
   ```bash
   python main.py client player-one --host <server_ip> --port 9000
   ```

4. Preview the renderer locally:
   ```bash
   python -m lan_game.renderer.pygame_renderer
   ```

5. Launch the interactive lobby (no arguments opens the menu):
   ```bash
   python main.py
   ```
   - Choose **게임 시작 - 호스트** to start hosting; your address is shown and a Pygame lobby opens.
   - Choose **게임 시작 - 참여** to join an existing host by entering its address.
   - The first client in the lobby sees a **Start** button to begin the round. All clients can chat, see who’s present (up to 4), and exit from the lobby window.

### Gameplay rules
- One player becomes the tagger; everyone else is a runner. Tagger speed is 1.5x; runners move at 1x (1 tile per 0.5s at 1x).
- Tagger vision: 180° in the facing direction, up to 5 tiles away, walls block visibility.
- Runner vision: full circle up to 3 tiles; a warning triggers if a tagger is within 5 tiles (Manhattan distance).
- Collision resolution is tile-based. A runner on the same tile as a tagger is out.
- A five-minute timer ends the round; if any runner survives, runners win, otherwise the tagger wins sooner by tagging everyone.
