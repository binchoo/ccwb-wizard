"""Backend settings — host, port range, profile directory."""

from __future__ import annotations

from pathlib import Path

HOST = "127.0.0.1"
PORT_RANGE_START = 8450
PORT_RANGE_END = 8499

PROFILES_DIR = Path.home() / ".ccwb" / "profiles"
