#!/bin/bash
# agents_review.sh - Orchestrate agent reviews based on REVIEW_MATRIX
# Sprint 21 - Agentic Workflow
#
# Usage:
#   ./scripts/agents_review.sh [--dry-run]
#
# Output:
#   docs/ai/reports/agents-review-<gitsha>.md

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORTS_DIR="$REPO_ROOT/docs/ai/reports"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get git info
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Report file
REPORT_FILE="$REPORTS_DIR/agents-review-${GIT_SHA}.md"

# Ensure reports directory exists
mkdir -p "$REPORTS_DIR"

# Get changed files
CHANGED_FILES=$(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
    echo -e "${YELLOW}No changed files detected. Using staged files...${NC}"
    CHANGED_FILES=$(git diff --name-only --cached 2>/dev/null || echo "")
fi

if [ -z "$CHANGED_FILES" ]; then
    echo -e "${GREEN}No files to review. Exiting.${NC}"
    exit 0
fi

# Determine required agents based on REVIEW_MATRIX
determine_agents() {
    local agents=""

    # API routes → FEAT, QA, RELIABILITY, SEC, OBS
    if echo "$CHANGED_FILES" | grep -q "src/api/routes/"; then
        agents="$agents FEAT QA RELIABILITY SEC OBS"
    fi

    # Schemas → FEAT, QA
    if echo "$CHANGED_FILES" | grep -q "src/api/schemas/"; then
        agents="$agents FEAT QA"
    fi

    # Matching engine → FEAT, QA, RELIABILITY
    if echo "$CHANGED_FILES" | grep -q "src/matching/"; then
        agents="$agents FEAT QA RELIABILITY"
    fi

    # Scripts → QA, RELIABILITY, SEC, OBS
    if echo "$CHANGED_FILES" | grep -q "scripts/"; then
        agents="$agents QA RELIABILITY SEC OBS"
    fi

    # Database → FEAT, QA, RELIABILITY, SEC
    if echo "$CHANGED_FILES" | grep -q "src/db/"; then
        agents="$agents FEAT QA RELIABILITY SEC"
    fi

    # Auth/Secrets → SEC
    if echo "$CHANGED_FILES" | grep -qE "\.env|secret|token|credential"; then
        agents="$agents SEC"
    fi

    # Config → RELIABILITY, SEC
    if echo "$CHANGED_FILES" | grep -qE "\.(toml|json)$"; then
        agents="$agents RELIABILITY SEC"
    fi

    # Tests → QA
    if echo "$CHANGED_FILES" | grep -q "tests/"; then
        agents="$agents QA"
    fi

    # Docs → FEAT
    if echo "$CHANGED_FILES" | grep -q "docs/"; then
        agents="$agents FEAT"
    fi

    # CI/CD → RELIABILITY, SEC
    if echo "$CHANGED_FILES" | grep -q "\.github/"; then
        agents="$agents RELIABILITY SEC"
    fi

    # Deduplicate and sort
    echo "$agents" | tr ' ' '\n' | sort -u | tr '\n' ' '
}

# Initialize report
init_report() {
    cat > "$REPORT_FILE" << EOF
# Agents Review Report

**Git SHA:** \`$GIT_SHA\`
**Branch:** \`$GIT_BRANCH\`
**Timestamp:** $TIMESTAMP

## Changed Files

\`\`\`
$CHANGED_FILES
\`\`\`

## Agent Results

EOF
}

# Simulate agent review (static analysis)
run_agent() {
    local agent=$1
    local status="ok"
    local scope=""
    local plan="none"
    local risks="none"

    case $agent in
        FEAT)
            scope="Feature & Contract"
            # Check for breaking changes (removed fields, changed types)
            if echo "$CHANGED_FILES" | grep -q "schemas/"; then
                if git diff HEAD~1 -- "*.py" 2>/dev/null | grep -qE "^-\s+\w+:.*Field"; then
                    status="warn"
                    plan="- Vérifier si champ supprimé est breaking change"
                    risks="- [medium] Possible breaking change détecté"
                fi
            fi
            ;;
        QA)
            scope="Quality Assurance"
            # Check if new code has tests
            local src_changes=$(echo "$CHANGED_FILES" | grep -c "src/" || true)
            local test_changes=$(echo "$CHANGED_FILES" | grep -c "tests/" || true)
            if [ "$src_changes" -gt 0 ] && [ "$test_changes" -eq 0 ]; then
                status="warn"
                plan="- Ajouter tests pour le nouveau code"
                risks="- [medium] Code modifié sans tests correspondants"
            fi
            ;;
        RELIABILITY)
            scope="Reliability"
            # Check for requests without timeout
            if echo "$CHANGED_FILES" | xargs grep -l "requests\." 2>/dev/null | head -1 | xargs grep -L "timeout=" 2>/dev/null; then
                status="warn"
                plan="- Ajouter timeout aux appels requests"
                risks="- [high] Appels HTTP sans timeout"
            fi
            ;;
        SEC)
            scope="Security"
            # Check for SQL injection patterns
            if git diff HEAD~1 -- "*.py" 2>/dev/null | grep -qE 'execute\(f"|execute\(.*%s'; then
                status="blocked"
                plan="- Corriger injection SQL potentielle"
                risks="- [critical] Pattern SQL injection détecté"
            fi
            # Check for hardcoded secrets
            if git diff HEAD~1 -- "*.py" 2>/dev/null | grep -qEi "(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]"; then
                status="blocked"
                plan="- Déplacer secrets vers variables d'environnement"
                risks="- [critical] Secret hardcodé détecté"
            fi
            ;;
        OBS)
            scope="Observability"
            # Check for print statements instead of logging
            if git diff HEAD~1 -- "*.py" 2>/dev/null | grep -q "^\+.*print("; then
                status="warn"
                plan="- Remplacer print() par logger structuré"
                risks="- [low] Utilisation de print() au lieu de logger"
            fi
            ;;
    esac

    # Write agent result to report
    cat >> "$REPORT_FILE" << EOF
### $agent

\`\`\`
STATUS: $status
SCOPE: $scope - $(echo "$CHANGED_FILES" | head -3 | tr '\n' ', ')
PLAN: $plan
PATCH: none
TESTS: none
RISKS: $risks
\`\`\`

EOF

    echo "$status"
}

# Main execution
main() {
    echo -e "${GREEN}=== Agents Review ===${NC}"
    echo "Git SHA: $GIT_SHA"
    echo "Branch: $GIT_BRANCH"
    echo ""

    # Determine required agents
    REQUIRED_AGENTS=$(determine_agents)

    if [ -z "$REQUIRED_AGENTS" ]; then
        echo -e "${YELLOW}No agents required for changed files.${NC}"
        exit 0
    fi

    echo "Changed files:"
    echo "$CHANGED_FILES" | head -10
    echo ""
    echo "Required agents: $REQUIRED_AGENTS"
    echo ""

    # Initialize report
    init_report

    # Run each agent
    FINAL_STATUS="PASS"
    HAS_BLOCKED=false
    HAS_WARN=false

    for agent in $REQUIRED_AGENTS; do
        echo -n "Running $agent... "
        result=$(run_agent "$agent")

        case $result in
            ok)
                echo -e "${GREEN}OK${NC}"
                ;;
            warn)
                echo -e "${YELLOW}WARN${NC}"
                HAS_WARN=true
                ;;
            blocked)
                echo -e "${RED}BLOCKED${NC}"
                HAS_BLOCKED=true
                ;;
        esac
    done

    # Determine final status
    if $HAS_BLOCKED; then
        FINAL_STATUS="FAIL"
    elif $HAS_WARN; then
        FINAL_STATUS="WARN"
    fi

    # Add summary to report
    cat >> "$REPORT_FILE" << EOF
## Summary

**Final Status:** \`$FINAL_STATUS\`

| Agent | Status |
|-------|--------|
EOF

    for agent in $REQUIRED_AGENTS; do
        echo "| $agent | $(grep -A1 "### $agent" "$REPORT_FILE" | grep "STATUS:" | cut -d: -f2 | tr -d ' ') |" >> "$REPORT_FILE"
    done

    echo ""
    echo "---"
    echo ""
    echo -e "Final Status: ${FINAL_STATUS}"
    echo "Report: $REPORT_FILE"

    if [ "$FINAL_STATUS" = "FAIL" ]; then
        echo -e "${RED}FAIL - Blocked issues must be resolved${NC}"
        exit 1
    elif [ "$FINAL_STATUS" = "WARN" ]; then
        echo -e "${YELLOW}WARN - Review warnings before merge${NC}"
        exit 0
    else
        echo -e "${GREEN}PASS - All agents OK${NC}"
        exit 0
    fi
}

main "$@"
