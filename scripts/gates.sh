#!/bin/bash
# gates.sh - Run validation gates as defined in docs/ai/GATES.md
# Sprint 21 - Agentic Workflow
#
# Usage:
#   ./scripts/gates.sh gate-1    # Pre-commit checks
#   ./scripts/gates.sh gate-2    # PR review checks
#   ./scripts/gates.sh gate-3    # Pre-merge checks
#   ./scripts/gates.sh all       # Run all gates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Gate 1: Pre-Commit (Local)
gate_1() {
    echo -e "${GREEN}=== Gate 1: Pre-Commit ===${NC}"
    local status=0

    # Check 1: Linting (ruff if available, else basic syntax check)
    echo -n "Checking lint... "
    if command -v ruff &> /dev/null; then
        if ruff check "$API_DIR/src/" "$API_DIR/scripts/" 2>/dev/null; then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${YELLOW}WARN (ruff issues)${NC}"
        fi
    else
        # Fallback: Python syntax check
        if find "$API_DIR/src" "$API_DIR/scripts" -name "*.py" -exec python3 -m py_compile {} \; 2>/dev/null; then
            echo -e "${GREEN}OK (syntax)${NC}"
        else
            echo -e "${RED}FAIL${NC}"
            status=1
        fi
    fi

    # Check 2: Fast tests (if pytest available)
    echo -n "Running fast tests... "
    if command -v pytest &> /dev/null; then
        cd "$API_DIR"
        if timeout 60 pytest tests/ -x -q --tb=no 2>/dev/null; then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${YELLOW}WARN (tests skipped or failed)${NC}"
        fi
        cd "$REPO_ROOT"
    else
        echo -e "${YELLOW}SKIP (pytest not installed)${NC}"
    fi

    # Check 3: No secrets in staged diff
    echo -n "Checking for secrets... "
    if git diff --cached 2>/dev/null | grep -qEi "(password|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}['\"]"; then
        echo -e "${RED}FAIL (possible secret detected)${NC}"
        status=1
    else
        echo -e "${GREEN}OK${NC}"
    fi

    if [ $status -eq 0 ]; then
        echo -e "\n${GREEN}Gate 1: PASS${NC}"
    else
        echo -e "\n${RED}Gate 1: FAIL${NC}"
    fi
    return $status
}

# Gate 2: PR Review (CI)
gate_2() {
    echo -e "${GREEN}=== Gate 2: PR Review ===${NC}"
    local status=0

    # Check 1: Run agents review
    echo "Running agents review..."
    if "$SCRIPT_DIR/agents_review.sh"; then
        echo -e "${GREEN}Agents: OK${NC}"
    else
        echo -e "${RED}Agents: FAIL${NC}"
        status=1
    fi

    # Check 2: Full test suite
    echo -n "Running full tests... "
    if command -v pytest &> /dev/null; then
        cd "$API_DIR"
        if pytest tests/ -v --tb=short 2>/dev/null; then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${RED}FAIL${NC}"
            status=1
        fi
        cd "$REPO_ROOT"
    else
        echo -e "${YELLOW}SKIP (pytest not installed)${NC}"
    fi

    if [ $status -eq 0 ]; then
        echo -e "\n${GREEN}Gate 2: PASS${NC}"
    else
        echo -e "\n${RED}Gate 2: FAIL${NC}"
    fi
    return $status
}

# Gate 3: Pre-Merge (Final)
gate_3() {
    echo -e "${GREEN}=== Gate 3: Pre-Merge ===${NC}"
    local status=0

    # Check 1: Branch up to date with main
    echo -n "Checking branch is up to date... "
    git fetch origin main 2>/dev/null || true
    if git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${YELLOW}WARN (branch may need rebase)${NC}"
    fi

    # Check 2: No merge conflicts
    echo -n "Checking for conflicts... "
    if git diff --check HEAD 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL (conflicts detected)${NC}"
        status=1
    fi

    # Check 3: All files committed
    echo -n "Checking working directory clean... "
    if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${YELLOW}WARN (uncommitted changes)${NC}"
    fi

    if [ $status -eq 0 ]; then
        echo -e "\n${GREEN}Gate 3: PASS${NC}"
    else
        echo -e "\n${RED}Gate 3: FAIL${NC}"
    fi
    return $status
}

# Run all gates
run_all() {
    local final_status=0

    gate_1 || final_status=1
    echo ""
    gate_2 || final_status=1
    echo ""
    gate_3 || final_status=1

    echo ""
    echo "========================"
    if [ $final_status -eq 0 ]; then
        echo -e "${GREEN}ALL GATES: PASS${NC}"
    else
        echo -e "${RED}GATES: FAIL${NC}"
    fi
    return $final_status
}

# Main
case "${1:-}" in
    gate-1|1)
        gate_1
        ;;
    gate-2|2)
        gate_2
        ;;
    gate-3|3)
        gate_3
        ;;
    all|"")
        run_all
        ;;
    *)
        echo "Usage: $0 {gate-1|gate-2|gate-3|all}"
        exit 1
        ;;
esac
