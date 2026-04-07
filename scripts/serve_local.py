#!/usr/bin/env python3
"""
HTTP server for MapLibre PoC assets.

Serves style JSON and individual vector tiles read directly from a PMTiles archive.
Vector tiles are exposed as standard {z}/{x}/{y} HTTP endpoints — the same pattern
that worked for raster PNG tiles, so no special protocol support needed in MapLibre.

Usage:
    python3 scripts/serve_local.py            # serves tiles/ on port 8080
    python3 scripts/serve_local.py tiles/ 8080

Endpoints:
    GET /vector-style.json              — MapLibre style
    GET /<archive>/<z>/<x>/<y>          — vector tile (PBF) from <archive>.pmtiles
    GET /offline-style.json             — raster style (legacy)

Requires:
    pip install pmtiles
"""

import gzip
import http.server
import importlib
import importlib.util
import os
import re
import socketserver
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = SCRIPT_DIR.parent / "tiles"
DEFAULT_PORT = 8080

# Tile URL pattern: /<archive>/<z>/<x>/<y>
_TILE_RE = re.compile(r"^/([^/]+)/(\d+)/(\d+)/(\d+)$")

# PMTiles tile_compression values
_COMPRESSION = {1: None, 2: "gzip", 3: "br", 4: "zstd"}


def _require_pmtiles() -> bool:
    """Ensure pmtiles package is available, auto-installing if needed."""
    if importlib.util.find_spec("pmtiles") is None:
        print("  'pmtiles' package not found — installing...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pmtiles", "--quiet"],
            check=False,
        )
        if result.returncode != 0:
            print("  ERROR: pip install pmtiles failed.")
            print("  Try manually:  pip install pmtiles")
            return False
        # Invalidate importlib cache so the newly installed package is found
        importlib.invalidate_caches()
        print("  Installed pmtiles.")
    return True


class ArchiveReader:
    """Thread-safe wrapper around a single open PMTiles file."""

    def __init__(self, path: Path) -> None:
        from pmtiles.reader import Reader, MmapSource  # type: ignore[import]
        self._lock   = threading.Lock()
        self._file   = open(path, "rb")
        self._reader = Reader(MmapSource(self._file))
        self._header = self._reader.header()
        self.tile_compression: Optional[str] = _COMPRESSION.get(
            self._header.get("tile_compression", 1)
        )

    def get(self, z: int, x: int, y: int) -> Optional[bytes]:
        with self._lock:
            return self._reader.get(z, x, y)

    def close(self) -> None:
        self._file.close()


class TileHandler(http.server.SimpleHTTPRequestHandler):

    # Populated at server startup: {"poland": ArchiveReader, ...}
    archives: dict[str, ArchiveReader] = {}

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        m = _TILE_RE.match(self.path)
        if m:
            self._serve_tile(m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        else:
            super().do_GET()

    # ── Tile handler ─────────────────────────────────────────────────────────

    def _serve_tile(self, archive: str, z: int, x: int, y: int) -> None:
        reader = self.archives.get(archive)
        if reader is None:
            self.send_error(404, f"Archive '{archive}.pmtiles' not loaded")
            return

        tile_data = reader.get(z, x, y)

        if not tile_data:
            # Tile does not exist in the archive (e.g. ocean/empty area)
            self.send_response(204)
            self._cors()
            self.end_headers()
            return

        # Decompress gzip by magic bytes (0x1f 0x8b) — reliable regardless of header flags.
        # MapLibre Native Qt needs raw PBF; it does not reliably handle Content-Encoding: gzip
        # for tile responses via the Qt Location plugin.
        if len(tile_data) >= 2 and tile_data[0] == 0x1f and tile_data[1] == 0x8b:
            tile_data = gzip.decompress(tile_data)
        encoding = None  # always serve raw PBF

        self.send_response(200)
        self.send_header("Content-Type",   "application/x-protobuf")
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Content-Length", str(len(tile_data)))
        self._cors()
        self.end_headers()
        self.wfile.write(tile_data)

    # ── CORS ──────────────────────────────────────────────────────────────────

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def end_headers(self) -> None:
        if not _TILE_RE.match(self.path):
            self._cors()
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        code = args[1] if len(args) > 1 else "?"
        print(f"  {code}  {self.path[:80]}", flush=True)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Handle each tile request in its own thread (MapLibre fetches tiles in parallel)."""
    allow_reuse_address = True
    daemon_threads      = True


def main() -> None:
    args = sys.argv[1:]

    serve_dir = Path(args[0]) if args else DEFAULT_DIR
    port      = int(args[1]) if len(args) > 1 else DEFAULT_PORT

    if not serve_dir.is_dir():
        print(f"Error: directory not found: {serve_dir}")
        sys.exit(1)

    if not _require_pmtiles():
        sys.exit(1)

    os.chdir(serve_dir)

    # Open all .pmtiles archives in the directory
    for pmtiles_file in sorted(serve_dir.glob("*.pmtiles")):
        name = pmtiles_file.stem
        try:
            TileHandler.archives[name] = ArchiveReader(pmtiles_file)
            size_mb = pmtiles_file.stat().st_size / 1024 / 1024
            print(f"  Loaded  : {pmtiles_file.name} ({size_mb:.0f} MB)")
        except Exception as exc:
            print(f"  WARNING : failed to open {pmtiles_file.name}: {exc}")

    print()
    print(f"Serving '{serve_dir}' on http://localhost:{port}/")
    for name in TileHandler.archives:
        print(f"  Tiles  : http://localhost:{port}/{name}/{{z}}/{{x}}/{{y}}")
    if (serve_dir / "vector-style.json").exists():
        print(f"  Style  : http://localhost:{port}/vector-style.json")
    if (serve_dir / "offline-style.json").exists():
        print(f"  Style  : http://localhost:{port}/offline-style.json  (raster, legacy)")
    print(f"  Ctrl+C to stop.")
    print()

    with ThreadedTCPServer(("", port), TileHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping...")
            for reader in TileHandler.archives.values():
                reader.close()


if __name__ == "__main__":
    main()
