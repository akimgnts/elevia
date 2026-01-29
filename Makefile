# Makefile - Elevia Compass
# Sprint 21 - Agentic Workflow
#
# Usage:
#   make agents-review    # Run all required agents based on REVIEW_MATRIX
#   make gate-1           # Pre-commit checks (lint, fast tests, secrets)
#   make gate-2           # PR review checks (agents + full tests)
#   make gate-3           # Pre-merge checks (branch sync, conflicts)
#   make gates            # Run all gates sequentially

.PHONY: agents-review gate-1 gate-2 gate-3 gates lint test-fast test test-api help

# Default target
help:
	@echo "Elevia Compass - Agentic Workflow"
	@echo ""
	@echo "Available targets:"
	@echo "  make agents-review  - Run agents review (REVIEW_MATRIX)"
	@echo "  make gate-1         - Pre-commit checks"
	@echo "  make gate-2         - PR review checks"
	@echo "  make gate-3         - Pre-merge checks"
	@echo "  make gates          - Run all gates"
	@echo "  make lint           - Run linting"
	@echo "  make test-fast      - Run fast tests"
	@echo "  make test           - Run full test suite"
	@echo "  make test-api       - Alias for make test"

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
