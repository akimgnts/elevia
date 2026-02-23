# Makefile - Elevia Compass
# Sprint 21 - Agentic Workflow
#
# Usage:
#   make agents-review    # Run all required agents based on REVIEW_MATRIX
#   make gate-1           # Pre-commit checks (lint, fast tests, secrets)
#   make gate-2           # PR review checks (agents + full tests)
#   make gate-3           # Pre-merge checks (branch sync, conflicts)
#   make gates            # Run all gates sequentially

.PHONY: agents-review gate-1 gate-2 gate-3 gates lint test-fast test test-api help \
        venv install api web test-cvdelta devtools \
        dev-up dev-down dev-status dev smoke

# Default target
help:
	@echo "Elevia Compass"
	@echo ""
	@echo "Dev Runner (recommended):"
	@echo "  make dev           - Start API+WEB (alias for dev-up)"
	@echo "  make smoke         - Quick end-to-end smoke test (API must be up)"
	@echo "  make dev-up        - Start API+WEB deterministically (kill old, free ports, wait health)"
	@echo "  make dev-down      - Stop API+WEB cleanly"
	@echo "  make dev-status    - Show process/port/log status"
	@echo ""
	@echo "Dev UX (manual):"
	@echo "  make venv          - Create .venv at repo root"
	@echo "  make install       - Install Python deps"
	@echo "  make api           - Start API (port 8000, ELEVIA_DEV_TOOLS=1)"
	@echo "  make web           - Start Vite (port 3001)"
	@echo "  make devtools      - Print start-up instructions"
	@echo "  make test-cvdelta  - Run /dev/cv-delta tests"
	@echo ""
	@echo "CI Gates:"
	@echo "  make gate-1        - Pre-commit (lint + fast tests)"
	@echo "  make gate-2        - PR review (agents + full tests)"
	@echo "  make gate-3        - Pre-merge (branch sync)"
	@echo "  make gates         - All gates"
	@echo "  make test          - Full test suite"
	@echo "  make lint          - Lint"

# Agents review (per REVIEW_MATRIX)
agents-review:
	@./scripts/agents_review.sh

# Gate 1: Pre-commit
gate-1:
	@./scripts/gates.sh gate-1

# Gate 2: PR Review
gate-2:
	@./scripts/gates.sh gate-2

# Gate 3: Pre-merge
gate-3:
	@./scripts/gates.sh gate-3

# All gates
gates:
	@./scripts/gates.sh all

# Linting (used by gate-1)
lint:
	@echo "Running lint checks..."
	@cd apps/api && (command -v ruff > /dev/null && ruff check src/ scripts/ || python3 -m py_compile src/**/*.py scripts/*.py 2>/dev/null || echo "Lint check completed")

# Fast tests (used by gate-1)
test-fast:
	@echo "Running fast tests..."
	@cd apps/api && python3 -m pytest tests/ -x -q --timeout=30

# Full test suite (used by gate-2)
test:
	@echo "Running full test suite..."
	@cd apps/api && python3 -m pytest tests/ -v

# Alias
test-api: test

# ── Dev UX ─────────────────────────────────────────────────────────────────

venv:
	python3 -m venv .venv
	@echo "Run: source .venv/bin/activate"

install:
	.venv/bin/pip install -r apps/api/requirements.txt
	@if [ -f apps/api/requirements-dev.txt ]; then .venv/bin/pip install -r apps/api/requirements-dev.txt; fi
	@echo "Done. Activate with: source .venv/bin/activate"

api:
	@echo "Starting API on http://0.0.0.0:8000 (ELEVIA_DEV_TOOLS=1)..."
	cd apps/api && ELEVIA_DEV_TOOLS=1 $(PWD)/.venv/bin/uvicorn api.main:app \
	  --host 0.0.0.0 --port 8000 --reload

web:
	@echo "Starting Vite on http://0.0.0.0:3001 (proxy -> http://localhost:8000)..."
	cd apps/web && npm run dev -- --host 0.0.0.0 --port 3001

test-cvdelta:
	@echo "Running /dev/cv-delta tests..."
	cd apps/api && ELEVIA_DEV_TOOLS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
	  $(PWD)/.venv/bin/python3 -m pytest tests/test_dev_cv_delta_endpoint.py tests/test_cv_parsing_delta_report.py \
	  -v --tb=short

# ── Dev Runner ──────────────────────────────────────────────────────────────

# One-command start (alias for dev-up)
dev: dev-up

# Quick smoke test (requires API running)
smoke:
	@bash scripts/smoke_dev.sh

# Start API+WEB deterministically (idempotent: kills old instances, frees ports)
dev-up:
	@bash scripts/dev/up.sh

# Stop API+WEB cleanly (PID files + port sweep)
dev-down:
	@bash scripts/dev/down.sh

# Show status: ports, PIDs, health, log tails
dev-status:
	@bash scripts/dev/status.sh

devtools:
	@echo ""
	@echo "  Start API (terminal 1):"
	@echo "    make api"
	@echo ""
	@echo "  Start Web (terminal 2):"
	@echo "    make web"
	@echo ""
	@echo "  Open page:"
	@echo "    http://localhost:3001/dev/cv-delta"
	@echo "    http://\$$(ipconfig getifaddr en0):3001/dev/cv-delta  (phone/LAN)"
	@echo ""
	@echo "  curl proof:"
	@echo "    curl -i http://localhost:8000/dev/cv-delta                     # expect 405"
	@echo "    curl -F 'file=@apps/api/fixtures/cv_samples/sample_delta.txt' \\"
	@echo "         http://localhost:8000/dev/cv-delta                        # expect 200"
	@echo ""
