# CareerIntelligenceAgent — Full Agent Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the existing `CareerIntelligenceAgent` skeleton to the full multi-agent contract — adding identity attributes, a deterministic routing decision layer (`next_recommended_agents`), and state-merge semantics so it is orchestratable.

**Architecture:** The agent already has correct computation logic (skill scoring, clustering, gap analysis). The upgrade touches only the class shell and the `run()` return block — zero changes to the computation functions. A new module-level function `_decide_next_agents()` maps intelligence signals to downstream agent names.

**Tech Stack:** Python 3.11+, stdlib only (`re`, `collections`, `copy`). No new dependencies.

---

## Context — What Already Exists

The file `apps/api/src/compass/intelligence/career_intelligence_agent.py` already contains:
- All computation helpers (`_canon`, `_extract_profile_skills`, `_match_score`, `_dominant_domain`, `_cluster_key`, etc.)
- 8-step pipeline in `run()` producing `career_intelligence_report`
- 36 passing tests in `apps/api/tests/test_career_intelligence_agent.py`

**What is missing vs the agent contract spec:**

| Gap | Current state | Required state |
|-----|--------------|----------------|
| `self.name` | absent (`pass`) | `"career_intelligence_agent"` |
| `self.version` | absent | `"v1"` |
| `next_recommended_agents` | not in output | list of downstream agent names |
| State merge | returns isolated `{"career_intelligence_report": ...}` | returns `{**input_state, "career_intelligence_report": ..., "next_recommended_agents": [...]}` |
| Parameter name | `payload` | `state` (cosmetic, but spec-canonical) |

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `apps/api/src/compass/intelligence/career_intelligence_agent.py` | Add identity, `_decide_next_agents`, state merge, rename param |
| Modify | `apps/api/tests/test_career_intelligence_agent.py` | Add `TestAgentContract` and `TestNextAgents` classes |

---

## Task 1: Agent Identity (name + version)

**Files:**
- Modify: `apps/api/src/compass/intelligence/career_intelligence_agent.py:169-171`
- Modify: `apps/api/tests/test_career_intelligence_agent.py` (append new class)

- [ ] **Step 1: Write the failing tests**

Append this class at the end of `apps/api/tests/test_career_intelligence_agent.py`:

```python
# ---------------------------------------------------------------------------
# 9. Agent contract — identity
# ---------------------------------------------------------------------------

class TestAgentContract:
    def test_agent_has_name_attribute(self) -> None:
        agent = CareerIntelligenceAgent()
        assert agent.name == "career_intelligence_agent"

    def test_agent_has_version_attribute(self) -> None:
        agent = CareerIntelligenceAgent()
        assert agent.version == "v1"

    def test_output_preserves_input_career_profile(self) -> None:
        """State merge: career_profile must be forwarded in output."""
        profile = _make_career_profile()
        state = {"career_profile": profile, "offers": ANALYTICS_OFFERS}
        result = CareerIntelligenceAgent().run(state)
        assert result["career_profile"] == profile

    def test_output_preserves_extra_state_keys(self) -> None:
        """State merge: unknown upstream keys must pass through unchanged."""
        state = {
            "career_profile": _make_career_profile(),
            "offers": ANALYTICS_OFFERS,
            "structuring_report": {"foo": "bar"},
            "enrichment_report": {"baz": 42},
        }
        result = CareerIntelligenceAgent().run(state)
        assert result["structuring_report"] == {"foo": "bar"}
        assert result["enrichment_report"] == {"baz": 42}
```

- [ ] **Step 2: Run to confirm RED**

```bash
cd apps/api && python3 -m pytest tests/test_career_intelligence_agent.py::TestAgentContract -v
```

Expected: 4 FAILED — `AttributeError: 'CareerIntelligenceAgent' object has no attribute 'name'` and `KeyError` for state keys not forwarded.

- [ ] **Step 3: Add identity attributes to `__init__`**

In `apps/api/src/compass/intelligence/career_intelligence_agent.py`, replace:

```python
class CareerIntelligenceAgent:
    def __init__(self) -> None:
        pass
```

with:

```python
class CareerIntelligenceAgent:
    def __init__(self) -> None:
        self.name = "career_intelligence_agent"
        self.version = "v1"
```

> Note: `test_output_preserves_*` tests will still fail here — they need the state merge in Task 3. We'll go GREEN on the 2 identity tests now.

- [ ] **Step 4: Run identity tests**

```bash
cd apps/api && python3 -m pytest tests/test_career_intelligence_agent.py::TestAgentContract::test_agent_has_name_attribute tests/test_career_intelligence_agent.py::TestAgentContract::test_agent_has_version_attribute -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit identity**

```bash
git add apps/api/src/compass/intelligence/career_intelligence_agent.py apps/api/tests/test_career_intelligence_agent.py
git commit -m "feat(intelligence): agent identity — name + version attributes"
```

---

## Task 2: `_decide_next_agents` Decision Function

**Files:**
- Modify: `apps/api/src/compass/intelligence/career_intelligence_agent.py` (add function before class)
- Modify: `apps/api/tests/test_career_intelligence_agent.py` (append new class)

- [ ] **Step 1: Write the failing tests**

Append this class at the end of `apps/api/tests/test_career_intelligence_agent.py`:

```python
# ---------------------------------------------------------------------------
# 10. next_recommended_agents — routing decision layer
# ---------------------------------------------------------------------------

class TestNextAgents:
    def test_output_contains_next_recommended_agents_key(self) -> None:
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        )
        assert "next_recommended_agents" in result

    def test_next_agents_is_non_empty_list(self) -> None:
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        )
        agents = result["next_recommended_agents"]
        assert isinstance(agents, list)
        assert len(agents) >= 1

    def test_next_agents_values_are_strings(self) -> None:
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        )
        for item in result["next_recommended_agents"]:
            assert isinstance(item, str)

    def test_empty_offers_routes_to_application_strategy(self) -> None:
        """No signals → default to application_strategy_agent."""
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": []}
        )
        assert "application_strategy_agent" in result["next_recommended_agents"]

    def test_blocking_gaps_route_to_skill_gap_remediation(self) -> None:
        """Python missing from profile but required ≥3 times + high demand → blocking gap."""
        profile = _make_career_profile(skills=["SQL"])
        offers = [
            _make_offer("Data Analyst", f"Co {i}", "France", ["SQL", "Python"])
            for i in range(6)  # 6 offers → HIGH demand (≥5 threshold)
        ]
        result = CareerIntelligenceAgent().run({"career_profile": profile, "offers": offers})
        assert "skill_gap_remediation_agent" in result["next_recommended_agents"]

    def test_high_match_high_demand_routes_to_application_strategy(self) -> None:
        """Profile matches ≥60% and cluster is high demand → application_strategy_agent."""
        profile = _make_career_profile(skills=["SQL", "Python", "Power BI"])
        offers = [
            _make_offer("Data Analyst", f"Co {i}", "France", ["SQL", "Python", "Power BI"])
            for i in range(6)  # 6 offers → HIGH demand
        ]
        result = CareerIntelligenceAgent().run({"career_profile": profile, "offers": offers})
        assert "application_strategy_agent" in result["next_recommended_agents"]

    def test_many_target_companies_routes_to_opportunity_hunter(self) -> None:
        """≥3 qualifying target companies → opportunity_hunter_agent."""
        profile = _make_career_profile(skills=["SQL", "Python", "Power BI"])
        # 4 companies, each appearing twice, each matching well
        offers = []
        for company in ["Capgemini", "Sopra", "Thales", "Atos"]:
            for _ in range(2):
                offers.append(
                    _make_offer("Data Analyst", company, "France", ["SQL", "Python", "Power BI"])
                )
        result = CareerIntelligenceAgent().run({"career_profile": profile, "offers": offers})
        assert "opportunity_hunter_agent" in result["next_recommended_agents"]

    def test_routing_is_deterministic(self) -> None:
        payload = {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        r1 = CareerIntelligenceAgent().run(deepcopy(payload))
        r2 = CareerIntelligenceAgent().run(deepcopy(payload))
        assert r1["next_recommended_agents"] == r2["next_recommended_agents"]
```

- [ ] **Step 2: Run to confirm RED**

```bash
cd apps/api && python3 -m pytest tests/test_career_intelligence_agent.py::TestNextAgents -v
```

Expected: 8 FAILED — `KeyError: 'next_recommended_agents'` on all tests.

- [ ] **Step 3: Implement `_decide_next_agents` function**

In `apps/api/src/compass/intelligence/career_intelligence_agent.py`, add this function **immediately before** `class CareerIntelligenceAgent:` (after the `_cluster_key` function block):

```python
def _decide_next_agents(
    opportunity_clusters: list[dict[str, Any]],
    blocking_gaps: list[str],
    target_companies: list[dict[str, Any]],
) -> list[str]:
    """
    Route to downstream agents based on career intelligence signals.

    Rules (in priority order):
    1. Blocking gaps present → skill remediation needed before applying
    2. Strong cluster match + high demand → ready to apply
    3. Many qualifying companies → opportunity hunting is worth it
    4. Fallback → always route somewhere
    """
    agents: list[str] = []

    # Blocking skill gaps must be addressed before mass applications
    if blocking_gaps:
        agents.append("skill_gap_remediation_agent")

    # Strong match in a high-demand cluster → go apply
    has_strong_cluster = any(
        c["match_score_avg"] >= HIGH_MATCH_THRESHOLD and c["demand_level"] == "high"
        for c in opportunity_clusters
    )
    if has_strong_cluster:
        agents.append("application_strategy_agent")

    # Many companies hiring for this profile → targeted hunting
    if len(target_companies) >= 3:
        agents.append("opportunity_hunter_agent")

    # Always route forward — minimum: application strategy
    if not agents:
        agents.append("application_strategy_agent")

    return agents
```

> Note: `next_recommended_agents` is not yet in `run()`'s output — these tests will still FAIL. We wire it in Task 3.

- [ ] **Step 4: Confirm `_decide_next_agents` is importable**

```bash
cd apps/api && python3 -c "from src.compass.intelligence.career_intelligence_agent import _decide_next_agents; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit function**

```bash
git add apps/api/src/compass/intelligence/career_intelligence_agent.py apps/api/tests/test_career_intelligence_agent.py
git commit -m "feat(intelligence): _decide_next_agents routing function + TestNextAgents skeleton"
```

---

## Task 3: State Merge + Wire `next_recommended_agents` into `run()`

**Files:**
- Modify: `apps/api/src/compass/intelligence/career_intelligence_agent.py:173-407`

- [ ] **Step 1: Rename `payload` → `state` and update the return block**

In `apps/api/src/compass/intelligence/career_intelligence_agent.py`, replace the entire `run()` signature and its first four lines:

```python
    def run(self, payload: dict) -> dict:
        """
        Input:
        {
            "career_profile": {...},
            "structuring_report": {...},
            "enrichment_report": {...},
            "offers": [...],
        }

        Output:
        {
            "career_intelligence_report": {...}
        }
        """
        career_profile = deepcopy(payload.get("career_profile") or {})
        structuring_report = payload.get("structuring_report") or {}
        enrichment_report = payload.get("enrichment_report") or {}
        offers = list(payload.get("offers") or [])
```

with:

```python
    def run(self, state: dict) -> dict:
        """
        Input state:
        {
            "career_profile": {...},
            "structuring_report": {...},
            "enrichment_report": {...},
            "offers": [...],
        }

        Output state (merged — all input keys preserved):
        {
            **input_state,
            "career_intelligence_report": {...},
            "next_recommended_agents": [...],
        }
        """
        career_profile = deepcopy(state.get("career_profile") or {})
        structuring_report = state.get("structuring_report") or {}
        enrichment_report = state.get("enrichment_report") or {}
        offers = list(state.get("offers") or [])
```

- [ ] **Step 2: Replace the return block**

Find and replace the final `report` assembly and `return report` at the bottom of `run()` (currently lines 377–407):

```python
        # ── 8. Assemble report ──────────────────────────────────────
        report: dict[str, Any] = {
            "career_intelligence_report": {
                "profile_summary": {
                    "dominant_domain": dominant_domain,
                    "core_strengths": core_strengths,
                    "secondary_strengths": secondary_strengths,
                },
                "market_fit": {
                    "top_countries": top_countries,
                    "top_roles": top_roles,
                    "top_sectors": top_sectors,
                },
                "opportunity_clusters": opportunity_clusters,
                "gap_analysis": {
                    "critical_missing_skills": critical_missing[:10],
                    "nice_to_have_skills": nice_to_have[:10],
                    "blocking_gaps": blocking_gaps[:5],
                },
                "recommended_actions": recommended_actions,
                "target_companies": target_companies,
                "stats": {
                    "offers_analyzed": len(offers),
                    "scored_offers": len(scored_offers),
                    "matching_clusters": len(opportunity_clusters),
                    "profile_skills_count": len(profile_skill_keys),
                    "critical_gaps_count": len(critical_missing),
                },
            }
        }

        return report
```

with:

```python
        # ── 8. Decision layer — next agents ────────────────────────
        next_agents = _decide_next_agents(
            opportunity_clusters=opportunity_clusters,
            blocking_gaps=blocking_gaps[:5],
            target_companies=target_companies,
        )

        # ── 9. Assemble output state (merge, not replace) ───────────
        output_state = dict(state)
        output_state["career_intelligence_report"] = {
            "profile_summary": {
                "dominant_domain": dominant_domain,
                "core_strengths": core_strengths,
                "secondary_strengths": secondary_strengths,
            },
            "market_fit": {
                "top_countries": top_countries,
                "top_roles": top_roles,
                "top_sectors": top_sectors,
            },
            "opportunity_clusters": opportunity_clusters,
            "gap_analysis": {
                "critical_missing_skills": critical_missing[:10],
                "nice_to_have_skills": nice_to_have[:10],
                "blocking_gaps": blocking_gaps[:5],
            },
            "recommended_actions": recommended_actions,
            "target_companies": target_companies,
            "stats": {
                "offers_analyzed": len(offers),
                "scored_offers": len(scored_offers),
                "matching_clusters": len(opportunity_clusters),
                "profile_skills_count": len(profile_skill_keys),
                "critical_gaps_count": len(critical_missing),
            },
        }
        output_state["next_recommended_agents"] = next_agents
        return output_state
```

- [ ] **Step 3: Run the new contract tests**

```bash
cd apps/api && python3 -m pytest tests/test_career_intelligence_agent.py::TestAgentContract tests/test_career_intelligence_agent.py::TestNextAgents -v
```

Expected: 12 PASSED (4 contract + 8 routing).

- [ ] **Step 4: Run the full agent test suite — zero regressions**

```bash
cd apps/api && python3 -m pytest tests/test_career_intelligence_agent.py -v
```

Expected: all tests PASSED (previously 36, now 36 + 4 + 8 = 48).

> If any of the original 36 tests fail, check `TestNoMutation.test_payload_dict_is_not_mutated` — it checks that the original dict is not mutated. `dict(state)` creates a new dict so the original `payload` object is untouched. This test must still pass.

- [ ] **Step 5: Commit contract upgrade**

```bash
git add apps/api/src/compass/intelligence/career_intelligence_agent.py apps/api/tests/test_career_intelligence_agent.py
git commit -m "feat(intelligence): full agent contract — state merge + next_recommended_agents routing"
```

---

## Task 4: Regression Check

**Files:** none — verification only.

- [ ] **Step 1: Run the full API test suite**

```bash
cd apps/api && python3 -m pytest tests/ -v --tb=short -q 2>&1 | tail -20
```

Expected: same pass/fail ratio as before this plan (previously: ~1184 passed, 24 pre-existing failures, 0 regressions from this work).

- [ ] **Step 2: Verify agent is importable and callable from root**

```bash
cd apps/api && python3 -c "
from src.compass.intelligence import CareerIntelligenceAgent
agent = CareerIntelligenceAgent()
print('name:', agent.name)
print('version:', agent.version)
result = agent.run({'career_profile': {'base_title': 'Data Analyst'}, 'offers': []})
print('next_recommended_agents:', result['next_recommended_agents'])
print('career_intelligence_report keys:', list(result['career_intelligence_report'].keys()))
"
```

Expected output:
```
name: career_intelligence_agent
version: v1
next_recommended_agents: ['application_strategy_agent']
career_intelligence_report keys: ['profile_summary', 'market_fit', 'opportunity_clusters', 'gap_analysis', 'recommended_actions', 'target_companies', 'stats']
```

- [ ] **Step 3: Final commit if any fixes were needed**

Only if Step 1 revealed new failures:
```bash
git add -p
git commit -m "fix(intelligence): regression fixes from full suite run"
```

---

## Self-Review Against Spec

| Spec requirement | Covered by |
|-----------------|------------|
| `self.name = "career_intelligence_agent"` | Task 1, Step 3 |
| `self.version = "v1"` | Task 1, Step 3 |
| `run(self, state: dict) -> dict` signature | Task 3, Step 1 |
| Output merged, not replaced | Task 3, Step 2 (`dict(state)`) |
| `next_recommended_agents` in output | Task 3, Step 2 |
| MUST NOT modify `career_profile` | Pre-existing `deepcopy` — verified by existing `TestNoMutation` |
| MUST NOT call LLM | Pre-existing — no LLM calls anywhere |
| Deterministic | Pre-existing `TestDeterminism` + new `test_routing_is_deterministic` |
| Idempotent (same input → same output) | Pre-existing + routing determinism test |
| `career_intelligence_report` sections | Pre-existing computation |
| Decision layer (routing) | Task 2, `_decide_next_agents` |
| Tests: deterministic, no mutation, clustering, gap detection | Pre-existing 36 tests |
| Tests: `next_recommended_agents`, state merge | Task 1 + Task 2 new tests |
