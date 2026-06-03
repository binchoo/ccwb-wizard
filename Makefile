# ccwb Build & Development Makefile

.PHONY: dev build install clean

# Development mode — backend reload + frontend hot reload
dev:
	@echo "Starting backend (uvicorn) + frontend (vite) in parallel..."
	@echo "Backend: http://127.0.0.1:8400"
	@echo "Frontend: http://localhost:5173 (proxied to backend)"
	@echo "Use Ctrl+C to stop both."
	cd web/frontend && yarn dev &
	uv run uvicorn ccwb_wizard.main:app --host 127.0.0.1 --port 8400 --reload

# Production build — frontend → static, then backend serves everything
build:
	cd web/frontend && yarn install && yarn build
	rm -rf web/backend/ccwb_wizard/static
	cp -r web/frontend/dist web/backend/ccwb_wizard/static
	@echo "Build complete. Run 'uv run ccwb' to start."

# Install all Python deps (workspace)
install:
	uv sync --all-packages

# Clean build artifacts
clean:
	rm -rf web/frontend/dist web/frontend/node_modules
	rm -rf web/backend/ccwb_wizard/static
	rm -rf .venv
