# prep

A minimal LAN-ready sandbox for a 2D grid-based game. It focuses on the network
plumbing and timing model while leaving room to add gameplay later.

## Features
- Asyncio TCP server that accepts LAN clients and broadcasts JSON messages.
- 0.5s tick loop that maps 1s real time to 5 minutes in-game time.
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

The server broadcasts heartbeat ticks to all connected players, and clients can
be extended to send actions back. This provides the foundation for synchronizing
movement and interactions on the 2D map in later iterations.
