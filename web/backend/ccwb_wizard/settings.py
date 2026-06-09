"""Backend settings — host, port range, profile directory."""

from __future__ import annotations

from pathlib import Path

HOST = "127.0.0.1"
# Wizard app port range. MUST NOT overlap with credential-process OIDC callback
# port (8400, registered as IdP callback URL) — otherwise running the wizard
# blocks local credential-process testing on the same machine.
PORT_RANGE_START = 8500
PORT_RANGE_END = 8599

PROFILES_DIR = Path.home() / ".ccwb" / "profiles"
