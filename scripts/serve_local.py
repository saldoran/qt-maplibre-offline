#!/usr/bin/env python3
"""
Minimal HTTP server with CORS headers for serving local tile files.

Run from the tiles/ directory (or pass the directory as an argument):
    cd tiles
    python3 ../scripts/serve_local.py

    # OR from anywhere:
    python3 scripts/serve_local.py tiles/ 8080

Served endpoints (when run from tiles/):
    http://localhost:8080/{z}/{x}/{y}.png   — raster tile images
    http://localhost:8080/offline-style.json — MapLibre style
    http://localhost:8080/                   — directory listing

Then run the app:
    ./build/poc_map --offline
"""

import http.server
import os
import sys
import socketserver
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = SCRIPT_DIR.parent / "tiles"
DEFAULT_PORT = 8080


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with CORS headers added."""

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Cache tiles for 1 hour on the client side
        if self.path.endswith(".png"):
            self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        code = args[1] if len(args) > 1 else "?"
        path = self.path[:80]
        print(f"  {code}  {path}", flush=True)


def main() -> None:
    args = sys.argv[1:]

    serve_dir = Path(args[0]) if args else DEFAULT_DIR
    port      = int(args[1]) if len(args) > 1 else DEFAULT_PORT

    if not serve_dir.is_dir():
        print(f"Error: directory not found: {serve_dir}")
        print(f"  Run scripts/download_tiles.py first to populate the tiles/ directory.")
        sys.exit(1)

    # Verify at least one tile or style file exists
    has_tiles = any(serve_dir.rglob("*.png")) or (serve_dir / "offline-style.json").exists()
    if not has_tiles:
        print(f"Warning: no tiles found in {serve_dir}")
        print(f"  Run scripts/download_tiles.py first.")

    os.chdir(serve_dir)

    print(f"Serving '{serve_dir}' at http://localhost:{port}/")
    print(f"  Tiles : http://localhost:{port}/{{z}}/{{x}}/{{y}}.png")
    print(f"  Style : http://localhost:{port}/offline-style.json")
    print(f"  Press Ctrl+C to stop.")
    print()

    with socketserver.TCPServer(("", port), CORSHandler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
