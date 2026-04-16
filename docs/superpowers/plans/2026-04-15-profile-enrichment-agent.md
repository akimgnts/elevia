# Profile Enrichment Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic backend `ProfileEnrichmentAgent` that runs after `ProfileStructuringAgent`, enriches the existing `career_profile` additively, persists `enrichment_report`, and preserves downstream compatibility.

**Architecture:** Extend the current parse pipeline in `cache_hooks.py` with a second additive agent pass. The new agent operates on the persisted `career_profile` produced by `ProfileStructuringAgent`, never rewrites existing `skill_links`, and records all enrichment decisions in `enrichment_report` plus traceable `enrichment_meta` stored in the profile payload.

**Tech Stack:** Python 3, Pydantic models in `documents/career_profile.py`, existing backend pipeline hooks in `apps/api/src/compass/pipeline`, pytest, graphify.

---

## File Map

- Create: `apps/api/src/compass/structuring/profile_enrichment_agent.py`
  - Deterministic enrichment orchestrator and private helper functions.
- Modify: `apps/api/src/compass/structuring/__init__.py`
  - Export `ProfileEnrichmentAgent` lazily alongside existing structuring exports.
- Modify: `apps/api/src/documents/career_profile.py`
  - Add additive metadata fields needed to persist enrichment provenance without breaking current readers.
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
  - Run `ProfileEnrichmentAgent` after `ProfileStructuringAgent`, persist `enrichment_report`, log `ENRICHMENT_STATS`, rebuild `profile["experiences"]` from final `career_profile`.
- Create: `apps/api/tests/test_profile_enrichment_agent.py`
  - Focused unit tests for thresholds, determinism, protected `skill_links`, traceability, and report shape.
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`
  - Assert pipeline persistence of `enrichment_report` and `enrichment_meta`.
- Verify only: `apps/api/tests/test_profile_structuring_agent.py`
  - Regression guard for structuring behavior after pipeline extension.
- Verify only: `apps/api/tests/test_apply_pack_cv_engine.py`
  - Ensure downstream CV generation still reads `skill_links` unchanged.
- Verify only: `apps/api/tests/test_html_renderer.py`
  - Ensure HTML rendering still works with additive metadata present.

### Task 1: Add enrichment metadata to the persisted career profile

**Files:**
- Modify: `apps/api/src/documents/career_profile.py`
- Test: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Write the failing integration test for additive enrichment metadata round-trip**

```python
def test_load_career_profile_round_trips_enrichment_meta():
    payload = {
        "schema_version": "v2",
        "experiences": [
            {
                "title": "Data Analyst",
                "company": "ACME",
                "skill_links": [
                    {
                        "skill": {"label": "Analyse de donnees", "uri": "skill:data_analysis"},
                        "tools": [{"label": "Python"}],
                        "context": None,
                        "autonomy_level": None,
                    }
                ],
            }
        ],
        "enrichment_meta": {
            "experiences": [
                {
                    "skill_links": [
                        {
                            "tools": [
                                {"label": "Power BI", "source": "enrichment", "confidence": 0.8}
                            ],
                            "context": {"source": "enrichment", "confidence": 0.76},
                        }
                    ]
                }
            ]
        },
    }

    cp = load_career_profile(payload)

    assert cp.enrichment_meta is not None
    assert cp.enrichment_meta["experiences"][0]["skill_links"][0]["tools"][0]["label"] == "Power BI"
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_load_career_profile_round_trips_enrichment_meta -q`
Expected: FAIL because `CareerProfile` does not yet persist or expose `enrichment_meta`.

- [ ] **Step 3: Add minimal additive metadata support to `CareerProfile`**

```python
class CareerProfile(BaseModel):
    schema_version: Literal["v2"] = "v2"
    base_title: Optional[str] = None
    summary_master: Optional[str] = None
    target_title: Optional[str] = None
    summary: Optional[str] = None
    identity: Optional[CareerIdentity] = None
    experiences: List[CareerExperience] = Field(default_factory=list)
    projects: List[CareerProject] = Field(default_factory=list)
    education: List[CareerEducation] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[CareerLanguage] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    selected_skills: List[CareerSkillSelection] = Field(default_factory=list)
    pending_skill_candidates: List[str] = Field(default_factory=list)
    enrichment_meta: Dict[str, Any] = Field(default_factory=dict)
    completeness: float = 0.0
    source_version: str = "profile_structured_v1"
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_load_career_profile_round_trips_enrichment_meta -q`
Expected: PASS

### Task 2: Add failing tests for deterministic enrichment behavior

**Files:**
- Create: `apps/api/tests/test_profile_enrichment_agent.py`
- Test: `apps/api/tests/test_profile_enrichment_agent.py`

- [ ] **Step 1: Write the failing unit tests covering thresholds, protection, and determinism**

```python
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.structuring.profile_enrichment_agent import ProfileEnrichmentAgent


def _payload() -> dict:
    return {
        "career_profile": {
            "schema_version": "v2",
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "responsibilities": [
                        "Analyse de performance avec Python, SQL et Power BI pour le reporting mensuel",
                        "Creation de tableaux de bord de performance",
                    ],
                    "tools": ["Python", "SQL", "Power BI"],
                    "autonomy_level": "autonomous",
                    "canonical_skills_used": [
                        {"label": "Analyse de donnees", "uri": "skill:data_analysis"}
                    ],
                    "skill_links": [
                        {
                            "skill": {"label": "Analyse de donnees", "uri": "skill:data_analysis"},
                            "tools": [{"label": "Python"}],
                            "context": None,
                            "autonomy_level": None,
                        }
                    ],
                }
            ],
        },
        "structuring_report": {
            "used_signals": [
                {"experience_index": 0, "skill": "Analyse de donnees", "tools": ["Python"], "context": None}
            ],
            "uncertain_links": [],
            "questions_for_user": [],
            "canonical_candidates": [],
            "rejected_noise": [{"value": "communication", "reason": "generic_without_context"}],
            "unresolved_candidates": [{"raw_value": "powerbi dashboards"}],
        },
        "canonical_skills": [
            {"label": "Analyse de donnees", "uri": "skill:data_analysis", "raw": "analyse"},
            {"label": "Reporting", "uri": "skill:reporting", "raw": "reporting"},
        ],
        "unresolved": [{"raw": "powerbi dashboards"}],
        "rejected_noise": [{"value": "communication", "reason": "generic_without_context"}],
    }


def test_enrichment_agent_is_deterministic():
    payload = _payload()
    first = ProfileEnrichmentAgent().run(copy.deepcopy(payload))
    second = ProfileEnrichmentAgent().run(copy.deepcopy(payload))
    assert first == second


def test_enrichment_agent_does_not_overwrite_existing_skill_link_fields():
    result = ProfileEnrichmentAgent().run(_payload())
    link = result["career_profile_enriched"]["experiences"][0]["skill_links"][0]

    assert link["skill"]["label"] == "Analyse de donnees"
    assert any(tool["label"] == "Python" for tool in link["tools"])
    assert link["context"] is not None
    assert link["autonomy_level"] == "autonomous"


def test_enrichment_agent_auto_fills_only_above_threshold_and_tracks_source():
    result = ProfileEnrichmentAgent().run(_payload())
    report = result["enrichment_report"]
    profile = result["career_profile_enriched"]

    assert report["auto_filled"]
    assert any(item["target_field"] == "context" for item in report["auto_filled"])
    assert profile["enrichment_meta"]["experiences"][0]["skill_links"][0]["context"]["source"] == "enrichment"


def test_enrichment_agent_uses_uncertain_signals_for_suggestions_not_hallucinations():
    payload = _payload()
    payload["career_profile"]["experiences"][0]["skill_links"] = []
    payload["career_profile"]["experiences"][0]["canonical_skills_used"] = []

    result = ProfileEnrichmentAgent().run(payload)
    report = result["enrichment_report"]

    assert report["suggestions"] or report["questions"]
    labels = {
        entry.get("skill")
        for entry in report["suggestions"]
        if isinstance(entry, dict)
    }
    assert labels <= {"Analyse de donnees", "Reporting", None}


def test_enrichment_agent_emits_learning_and_priority_signals():
    result = ProfileEnrichmentAgent().run(_payload())
    report = result["enrichment_report"]

    assert report["priority_signals"]
    assert report["learning_candidates"]
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `./.venv/bin/pytest apps/api/tests/test_profile_enrichment_agent.py -q`
Expected: FAIL because `ProfileEnrichmentAgent` does not exist yet.

### Task 3: Implement the enrichment agent core

**Files:**
- Create: `apps/api/src/compass/structuring/profile_enrichment_agent.py`
- Modify: `apps/api/src/compass/structuring/__init__.py`
- Test: `apps/api/tests/test_profile_enrichment_agent.py`

- [ ] **Step 1: Add the new enrichment agent module with deterministic helpers**

```python
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from documents.career_profile import CareerProfile, CareerSkillSelection, SkillLink, ToolRef


KNOWN_TOOL_TOKENS = {
    "python": "Python",
    "sql": "SQL",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "excel": "Excel",
    "sap": "SAP",
}


def _canon(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _sentence_split(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        out.extend(part.strip() for part in re.split(r"[.;\n]+", str(value or "")) if part.strip())
    return out


def compute_confidence(evidence_count: int, explicit_tool: bool, keyword_strength: float, context_coherence: float) -> float:
    score = 0.0
    if explicit_tool:
        score += 0.4
    score += min(evidence_count * 0.2, 0.4)
    score += keyword_strength
    score += context_coherence
    return round(min(score, 1.0), 2)


class ProfileEnrichmentAgent:
    def __init__(self):
        pass

    def run(self, profile_input: dict) -> dict:
        payload = deepcopy(profile_input or {})
        career_profile = CareerProfile.model_validate(payload.get("career_profile") or {})
        structuring_report = payload.get("structuring_report") or {}
        canonical_skills = [item for item in payload.get("canonical_skills") or [] if isinstance(item, dict)]
        unresolved = list(payload.get("unresolved") or [])
        rejected_noise = list(payload.get("rejected_noise") or [])

        auto_filled: list[dict[str, Any]] = []
        suggestions: list[dict[str, Any]] = []
        questions: list[dict[str, Any]] = []
        reused_rejected: list[dict[str, Any]] = []
        confidence_scores: list[dict[str, Any]] = []
        priority_signals: list[dict[str, Any]] = []
        canonical_candidates: list[dict[str, Any]] = []
        learning_candidates: list[dict[str, Any]] = []
        enrichment_meta = deepcopy(career_profile.enrichment_meta or {})
        enrichment_meta.setdefault("experiences", [])

        for experience_index, exp in enumerate(career_profile.experiences):
            while len(enrichment_meta["experiences"]) <= experience_index:
                enrichment_meta["experiences"].append({"skill_links": []})
            exp_meta = enrichment_meta["experiences"][experience_index]
            exp_meta.setdefault("skill_links", [])

            sentences = _sentence_split(exp.responsibilities)
            exp_tools = {_canon(tool): tool for tool in exp.tools}

            for skill_link_index, link in enumerate(exp.skill_links):
                while len(exp_meta["skill_links"]) <= skill_link_index:
                    exp_meta["skill_links"].append({})
                link_meta = exp_meta["skill_links"][skill_link_index]
                skill_norm = _canon(link.skill.label)

                tool_candidates = []
                for token, label in KNOWN_TOOL_TOKENS.items():
                    explicit_tool = token in exp_tools or any(token in _canon(sentence) for sentence in sentences)
                    if not explicit_tool or any(_canon(tool.label) == _canon(label) for tool in link.tools):
                        continue
                    evidence_count = sum(1 for sentence in sentences if token in _canon(sentence) or skill_norm in _canon(sentence))
                    keyword_strength = 0.2 if skill_norm and any(skill_norm in _canon(sentence) for sentence in sentences) else 0.0
                    context_coherence = 0.2 if any(token in _canon(sentence) and skill_norm in _canon(sentence) for sentence in sentences) else 0.0
                    confidence = compute_confidence(evidence_count, explicit_tool, keyword_strength, context_coherence)
                    tool_candidates.append((confidence, label, explicit_tool, evidence_count, context_coherence))

                tool_candidates.sort(reverse=True)
                if len(tool_candidates) == 1 and tool_candidates[0][0] >= 0.75:
                    _, label, _, _, _ = tool_candidates[0]
                    link.tools.append(ToolRef(label=label))
                    link_meta.setdefault("tools", []).append({"label": label, "source": "enrichment", "confidence": tool_candidates[0][0]})
                    auto_filled.append({
                        "experience_index": experience_index,
                        "skill_link_index": skill_link_index,
                        "target_field": "tools",
                        "value": label,
                        "confidence": tool_candidates[0][0],
                        "reason": "single explicit tool candidate",
                    })

                for confidence, label, explicit_tool, evidence_count, context_coherence in tool_candidates:
                    confidence_scores.append({
                        "experience_index": experience_index,
                        "skill_link_index": skill_link_index,
                        "target_field": "tools",
                        "candidate": label,
                        "confidence": confidence,
                        "explicit_tool": explicit_tool,
                        "evidence_count": evidence_count,
                        "context_coherence": context_coherence,
                    })

                if not link.context and sentences:
                    best_sentence = next((sentence for sentence in sentences if skill_norm in _canon(sentence)), sentences[0])
                    confidence = compute_confidence(
                        2 if best_sentence else 1,
                        bool(link.tools),
                        0.2 if skill_norm in _canon(best_sentence) else 0.0,
                        0.2 if skill_norm in _canon(best_sentence) else 0.0,
                    )
                    if confidence >= 0.75:
                        link.context = best_sentence
                        link_meta["context"] = {"source": "enrichment", "confidence": confidence}
                        auto_filled.append({
                            "experience_index": experience_index,
                            "skill_link_index": skill_link_index,
                            "target_field": "context",
                            "value": best_sentence,
                            "confidence": confidence,
                            "reason": "best supporting sentence fragment",
                        })
                    elif confidence >= 0.5:
                        suggestions.append({
                            "experience_index": experience_index,
                            "skill_link_index": skill_link_index,
                            "target_field": "context",
                            "value": best_sentence,
                            "confidence": confidence,
                        })
                    else:
                        questions.append({
                            "type": "context",
                            "experience_index": experience_index,
                            "skill_link_index": skill_link_index,
                            "target_field": "context",
                            "question": "Quel etait le contexte principal de cette experience ?",
                            "confidence": confidence,
                        })

                if not link.autonomy_level and exp.autonomy_level:
                    link.autonomy_level = exp.autonomy_level
                    link_meta["autonomy_level"] = {"source": "enrichment", "confidence": 0.8}
                    auto_filled.append({
                        "experience_index": experience_index,
                        "skill_link_index": skill_link_index,
                        "target_field": "autonomy_level",
                        "value": exp.autonomy_level,
                        "confidence": 0.8,
                        "reason": "copied from deterministic experience autonomy",
                    })

                if link.skill.label:
                    priority_signals.append({
                        "experience_index": experience_index,
                        "skill": link.skill.label,
                        "reason": "strong structured signal with explicit tools and context",
                        "confidence": 0.84 if link.context or link.tools else 0.64,
                    })

            if not exp.skill_links:
                for item in canonical_skills:
                    label = str(item.get("label") or "").strip()
                    if not label:
                        continue
                    label_norm = _canon(label)
                    evidence_count = sum(1 for sentence in sentences if label_norm in _canon(sentence))
                    keyword_strength = 0.2 if evidence_count else 0.0
                    context_coherence = 0.2 if any(any(token in _canon(sentence) for token in KNOWN_TOOL_TOKENS) for sentence in sentences) else 0.0
                    confidence = compute_confidence(evidence_count, False, keyword_strength, context_coherence)
                    confidence_scores.append({
                        "experience_index": experience_index,
                        "target_field": "skill",
                        "candidate": label,
                        "confidence": confidence,
                    })
                    if confidence >= 0.5:
                        suggestions.append({
                            "experience_index": experience_index,
                            "target_field": "skill",
                            "skill": label,
                            "confidence": confidence,
                        })
                    else:
                        questions.append({
                            "type": "skill",
                            "experience_index": experience_index,
                            "target_field": "skill",
                            "question": "Quelle competence principale correspond a cette experience ?",
                            "confidence": confidence,
                        })

            for item in unresolved:
                raw_value = str(item.get("raw") or item.get("value") or "").strip() if isinstance(item, dict) else str(item or "").strip()
                if not raw_value:
                    continue
                learning_candidates.append({
                    "raw": raw_value,
                    "suggested_canonical": "Reporting" if "dashboard" in _canon(raw_value) else None,
                    "frequency": 1,
                    "reason": "unresolved token reused during enrichment diagnostics",
                })
                canonical_candidates.append({
                    "raw_value": raw_value,
                    "normalized_value": _canon(raw_value),
                    "type": "alias",
                    "confidence": 0.55,
                    "reason": "unresolved signal kept for canonical review",
                })

            reused_rejected.extend(item for item in rejected_noise if isinstance(item, dict))

        career_profile.enrichment_meta = enrichment_meta
        enrichment_report = {
            "auto_filled": auto_filled,
            "suggestions": suggestions,
            "questions": questions,
            "reused_rejected": reused_rejected,
            "confidence_scores": confidence_scores,
            "priority_signals": priority_signals[:10],
            "canonical_candidates": canonical_candidates,
            "learning_candidates": learning_candidates,
            "stats": {
                "suggestions_count": len(suggestions),
                "auto_filled_count": len(auto_filled),
                "questions_count": len(questions),
            },
        }
        return {
            "career_profile_enriched": career_profile.model_dump(),
            "enrichment_report": enrichment_report,
        }
```

- [ ] **Step 2: Export the new agent from the structuring package**

```python
from __future__ import annotations

from .skill_link_builder import build_skill_links_for_experience

__all__ = ["ProfileStructuringAgent", "ProfileEnrichmentAgent", "build_skill_links_for_experience"]


def __getattr__(name: str):
    if name == "ProfileStructuringAgent":
        from .profile_structuring_agent import ProfileStructuringAgent

        return ProfileStructuringAgent
    if name == "ProfileEnrichmentAgent":
        from .profile_enrichment_agent import ProfileEnrichmentAgent

        return ProfileEnrichmentAgent
    raise AttributeError(name)
```

- [ ] **Step 3: Run the new unit tests and iterate until they pass**

Run: `./.venv/bin/pytest apps/api/tests/test_profile_enrichment_agent.py -q`
Expected: PASS

### Task 4: Integrate the enrichment agent into the backend cache hooks

**Files:**
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Test: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Write the failing pipeline integration test**

```python
def test_run_profile_cache_hooks_persists_enrichment_report():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Francais", "Anglais"],
    }

    run_profile_cache_hooks(
        cv_text="Analyse de performance avec Python SQL et Power BI pour le reporting.",
        profile=profile,
        canonical_skills=[{"label": "Analyse de donnees", "uri": "skill:data_analysis", "raw": "analyse"}],
        unresolved=[{"raw": "powerbi dashboards"}],
        removed=[{"value": "communication", "reason": "generic_without_context"}],
    )

    assert "enrichment_report" in profile
    assert "stats" in profile["enrichment_report"]
    assert "enrichment_meta" in profile["career_profile"]
```

- [ ] **Step 2: Run the targeted integration test to verify it fails**

Run: `./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_persists_enrichment_report -q`
Expected: FAIL because cache hooks do not yet run `ProfileEnrichmentAgent`.

- [ ] **Step 3: Update `cache_hooks.py` to run enrichment after structuring**

```python
from compass.structuring import ProfileEnrichmentAgent, ProfileStructuringAgent
from documents.career_profile import from_profile_structured_v1, load_career_profile, to_experience_dicts

# ... inside run_profile_cache_hooks(...)
agent = ProfileStructuringAgent()
agent_result = agent.run(
    {
        "career_profile": career_profile_dict,
        "raw_profile": dict(profile),
        "canonical_skills": list(canonical_skills or profile.get("canonical_skills") or []),
        "unresolved": list(unresolved or profile.get("unresolved") or []),
        "removed": list(
            removed
            or profile.get("generic_filter_removed")
            or profile.get("removed")
            or []
        ),
    }
)
career_profile_dict = agent_result["career_profile_enriched"]
structuring_report = agent_result["structuring_report"]

enrichment = ProfileEnrichmentAgent().run(
    {
        "career_profile": career_profile_dict,
        "structuring_report": structuring_report,
        "canonical_skills": list(canonical_skills or profile.get("canonical_skills") or []),
        "unresolved": list(unresolved or profile.get("unresolved") or []),
        "rejected_noise": list(
            removed
            or profile.get("generic_filter_removed")
            or profile.get("removed")
            or []
        ),
    }
)
career_profile_dict = enrichment["career_profile_enriched"]
profile["career_profile"] = career_profile_dict
profile["structuring_report"] = structuring_report
profile["enrichment_report"] = enrichment["enrichment_report"]

enriched_career_profile = load_career_profile(career_profile_dict)
if enriched_career_profile.experiences:
    profile["experiences"] = to_experience_dicts(enriched_career_profile)

enrichment_stats = profile["enrichment_report"].get("stats", {})
logger.info(
    "ENRICHMENT_STATS suggestions=%d auto_filled=%d questions=%d",
    int(enrichment_stats.get("suggestions_count", 0) or 0),
    int(enrichment_stats.get("auto_filled_count", 0) or 0),
    int(enrichment_stats.get("questions_count", 0) or 0),
)
```

- [ ] **Step 4: Run the targeted integration test to verify it passes**

Run: `./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_persists_enrichment_report -q`
Expected: PASS

### Task 5: Tighten the enrichment agent against destructive updates

**Files:**
- Modify: `apps/api/src/compass/structuring/profile_enrichment_agent.py`
- Test: `apps/api/tests/test_profile_enrichment_agent.py`

- [ ] **Step 1: Add the failing safety test for protected links**

```python
def test_enrichment_agent_does_not_replace_existing_context_or_tools():
    payload = _payload()
    payload["career_profile"]["experiences"][0]["skill_links"][0]["context"] = "Contexte deja valide"
    payload["career_profile"]["experiences"][0]["skill_links"][0]["autonomy_level"] = "partial"

    result = ProfileEnrichmentAgent().run(payload)
    link = result["career_profile_enriched"]["experiences"][0]["skill_links"][0]

    assert link["context"] == "Contexte deja valide"
    assert link["autonomy_level"] == "partial"
    assert [tool["label"] for tool in link["tools"]] == ["Python"] or "Power BI" in [tool["label"] for tool in link["tools"]]
```

- [ ] **Step 2: Run the single safety test and confirm the failure mode**

Run: `./.venv/bin/pytest apps/api/tests/test_profile_enrichment_agent.py::test_enrichment_agent_does_not_replace_existing_context_or_tools -q`
Expected: FAIL if the implementation rewrites protected fields or behaves ambiguously.

- [ ] **Step 3: Tighten the implementation to append-only semantics on protected links**

```python
if link.context:
    pass
elif confidence >= 0.75:
    link.context = best_sentence
    link_meta["context"] = {"source": "enrichment", "confidence": confidence}

if link.autonomy_level:
    pass
elif exp.autonomy_level:
    link.autonomy_level = exp.autonomy_level
    link_meta["autonomy_level"] = {"source": "enrichment", "confidence": 0.8}

existing_tool_keys = {_canon(tool.label) for tool in link.tools}
if len(tool_candidates) == 1 and tool_candidates[0][1] and _canon(tool_candidates[0][1]) not in existing_tool_keys:
    # append only; never replace
    ...
```

- [ ] **Step 4: Run the full enrichment test file again**

Run: `./.venv/bin/pytest apps/api/tests/test_profile_enrichment_agent.py -q`
Expected: PASS

### Task 6: Add pipeline regression assertions for downstream compatibility

**Files:**
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`
- Verify only: `apps/api/tests/test_apply_pack_cv_engine.py`
- Verify only: `apps/api/tests/test_html_renderer.py`

- [ ] **Step 1: Add integration assertions for `profile["experiences"]` and additive reports**

```python
def test_run_profile_cache_hooks_keeps_experience_dicts_compatible_after_enrichment():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Francais", "Anglais"],
    }

    run_profile_cache_hooks(
        cv_text="Analyse de performance avec Python SQL et Power BI pour le reporting.",
        profile=profile,
        canonical_skills=[{"label": "Analyse de donnees", "uri": "skill:data_analysis", "raw": "analyse"}],
        unresolved=[{"raw": "powerbi dashboards"}],
        removed=[{"value": "communication", "reason": "generic_without_context"}],
    )

    assert profile["experiences"]
    assert "skill_links" in profile["experiences"][0]
    assert "enrichment_meta" in profile["career_profile"]
    assert "priority_signals" in profile["enrichment_report"]
```

- [ ] **Step 2: Run the integration test module**

Run: `./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q`
Expected: PASS

- [ ] **Step 3: Run downstream regression tests**

Run: `./.venv/bin/pytest apps/api/tests/test_apply_pack_cv_engine.py apps/api/tests/test_html_renderer.py -q`
Expected: PASS

### Task 7: Run the full verification batch and refresh the graph

**Files:**
- Verify only: `apps/api/tests/test_profile_enrichment_agent.py`
- Verify only: `apps/api/tests/test_profile_structuring_agent.py`
- Verify only: `apps/api/tests/test_career_profile_v2_integration.py`
- Verify only: `apps/api/tests/test_apply_pack_cv_engine.py`
- Verify only: `apps/api/tests/test_html_renderer.py`

- [ ] **Step 1: Run the full backend verification batch**

Run: `./.venv/bin/pytest apps/api/tests/test_profile_enrichment_agent.py apps/api/tests/test_profile_structuring_agent.py apps/api/tests/test_career_profile_v2_integration.py apps/api/tests/test_apply_pack_cv_engine.py apps/api/tests/test_html_renderer.py -q`
Expected: PASS

- [ ] **Step 2: Update the graph after code changes**

Run: `graphify update .`
Expected: graph update completes successfully.

- [ ] **Step 3: Inspect git diff for the exact touched files**

Run: `git diff -- apps/api/src/compass/structuring/profile_enrichment_agent.py apps/api/src/compass/structuring/__init__.py apps/api/src/documents/career_profile.py apps/api/src/compass/pipeline/cache_hooks.py apps/api/tests/test_profile_enrichment_agent.py apps/api/tests/test_career_profile_v2_integration.py`
Expected: diff shows only the planned additive enrichment changes.
