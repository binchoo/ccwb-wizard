"""FastAPI app + uvicorn entry point for the ccwb web wizard.

Usage:
  uv run ccwb          # (after Frontend+Wiring unit registers the script)
  uv run python -m ccwb_wizard.main   # direct invocation for dev
"""

from __future__ import annotations

import socket
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import wizard, scenarios, aws_lookup, secret, auth_test, deploy, package
from .settings import HOST, PORT_RANGE_START, PORT_RANGE_END

app = FastAPI(title="ccwb wizard", version="0.1.0")

# Mount API routers
app.include_router(wizard.router, prefix="/api")
app.include_router(scenarios.router, prefix="/api")
app.include_router(aws_lookup.router, prefix="/api")
app.include_router(secret.router, prefix="/api")
app.include_router(auth_test.router, prefix="/api")
app.include_router(deploy.router, prefix="/api")
app.include_router(package.router, prefix="/api")


# Health check
@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Static files (frontend dist — populated by Frontend+Wiring unit)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def find_free_port(start: int = PORT_RANGE_START, end: int = PORT_RANGE_END) -> int:
    """Find a free port in range [start, end]. Raises RuntimeError if none."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in {start}–{end}. Close other ccwb instances or free a port.")


def main() -> None:
    """Entry point: start uvicorn + open browser."""
    import uvicorn

    port = find_free_port()
    url = f"http://{HOST}:{port}"

    # Start uvicorn in a daemon thread so Ctrl+C exits cleanly
    server_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": "ccwb_wizard.main:app", "host": HOST, "port": port, "log_level": "warning"},
        daemon=True,
    )
    server_thread.start()

    print(f"ccwb wizard running at {url}")
    webbrowser.open(url)

    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down ccwb wizard.")


if __name__ == "__main__":
    main()
