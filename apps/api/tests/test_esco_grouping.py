"""
test_esco_grouping.py — Tests for ESCO collection-based skill grouping.

Covers:
  - validated_items labels never contain digits or '@'
  - groups are stable (deterministic)
  - group counts sum to validated_skills
  - group items are non-empty lists of strings
  - each item appears in exactly one group
  - empty validated_items returns empty groups
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from profile.esco_grouping import group_validated_items
from profile.skill_filter import strict_filter_skills


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_items(raw: list[str]) -> list[dict]:
    """Run strict_filter_skills and return validated_items."""
    result = strict_filter_skills(raw)
    return result["validated_items"]


# ── Label cleanliness ─────────────────────────────────────────────────────────

def test_validated_items_labels_no_digits():
    """Labels in validated_items must not contain digits (ESCO preferred labels are clean)."""
    raw = [
        "python (programmation informatique)",  # valid ESCO
        "2023",                                 # digit-only: filtered by noise
        "user@example.com",                     # email: filtered by noise
    ]
    items = _make_items(raw)
    for item in items:
        label = item["label"]
        assert not any(c.isdigit() for c in label), (
            f"Label contains digit: {label!r}"
        )


def test_validated_items_labels_no_at():
    """Labels in validated_items must not contain '@'."""
    raw = ["python (programmation informatique)", "admin@company.fr"]
    items = _make_items(raw)
    for item in items:
        assert "@" not in item["label"], f"Label contains @: {item['label']!r}"


def test_validated_items_have_uri_and_label():
    """Each validated_item must have non-empty 'uri' and 'label' keys."""
    raw = ["python (programmation informatique)", "SQL"]
    items = _make_items(raw)
    assert len(items) >= 1
    for item in items:
        assert "uri" in item and item["uri"], f"Missing uri in {item}"
        assert "label" in item and item["label"], f"Missing label in {item}"


# ── Group structure ───────────────────────────────────────────────────────────

def test_group_counts_sum_to_validated():
    """Sum of group counts must equal total validated_items count."""
    raw = [
        "python (programmation informatique)",
        "SQL",
        "analyse de données",
        "xyzqwerty_not_esco",  # will be filtered out
    ]
    filter_result = strict_filter_skills(raw)
    items = filter_result["validated_items"]
    validated_count = filter_result["validated_skills"]

    groups = group_validated_items(items)

    total_in_groups = sum(g["count"] for g in groups)
    assert total_in_groups == validated_count == len(items), (
        f"Group sum {total_in_groups} != validated_skills {validated_count}"
    )


def test_each_item_in_exactly_one_group():
    """Every validated item label must appear in exactly one group."""
    raw = [
        "python (programmation informatique)",
        "SQL",
        "analyse de données",
    ]
    items = _make_items(raw)
    groups = group_validated_items(items)

    all_labels_in_groups = []
    for g in groups:
        all_labels_in_groups.extend(g["items"])

    # No duplicates across groups
    assert len(all_labels_in_groups) == len(set(all_labels_in_groups)), (
        "Some labels appear in more than one group"
    )

    # All validated labels present
    validated_labels = {item["label"] for item in items}
    group_label_set = set(all_labels_in_groups)
    assert validated_labels == group_label_set, (
        f"Mismatch: validated={validated_labels}, groups={group_label_set}"
    )


def test_group_items_are_strings():
    """Group items must be plain strings (ESCO preferred labels)."""
    raw = ["python (programmation informatique)", "SQL"]
    items = _make_items(raw)
    groups = group_validated_items(items)
    for g in groups:
        assert isinstance(g["group"], str)
        assert isinstance(g["count"], int)
        assert isinstance(g["items"], list)
        for skill in g["items"]:
            assert isinstance(skill, str), f"Expected str, got {type(skill)}: {skill!r}"


def test_empty_validated_items_returns_empty_groups():
    """Empty input must return empty group list without error."""
    groups = group_validated_items([])
    assert groups == []


# ── Determinism ───────────────────────────────────────────────────────────────

def test_groups_are_stable():
    """Same validated_items must produce identical groups on repeated calls."""
    raw = [
        "python (programmation informatique)",
        "SQL",
        "analyse de données",
        "DevOps",
    ]
    items = _make_items(raw)

    g1 = group_validated_items(items)
    g2 = group_validated_items(items)

    assert g1 == g2, "group_validated_items is not deterministic"


def test_group_order_is_stable():
    """Group ordering must be stable across calls."""
    raw = [
        "python (programmation informatique)",
        "SQL",
        "analyse de données",
    ]
    items = _make_items(raw)
    g1 = group_validated_items(items)
    g2 = group_validated_items(items)

    assert [g["group"] for g in g1] == [g["group"] for g in g2]


# ── Digital group ─────────────────────────────────────────────────────────────

def test_python_assigned_to_numerique():
    """Python (programmation informatique) should be grouped under Numérique."""
    raw = ["python (programmation informatique)"]
    items = _make_items(raw)
    assert len(items) >= 1
    groups = group_validated_items(items)
    group_names = {g["group"] for g in groups}
    assert "Numérique" in group_names, (
        f"Expected 'Numérique' in groups, got: {group_names}"
    )


# ── No-overlap assertion ──────────────────────────────────────────────────────

def test_no_zero_count_groups():
    """No group with count=0 should appear in output."""
    raw = ["python (programmation informatique)", "SQL"]
    items = _make_items(raw)
    groups = group_validated_items(items)
    for g in groups:
        assert g["count"] > 0, f"Group with count=0 found: {g}"
        assert len(g["items"]) > 0, f"Group with empty items found: {g}"
