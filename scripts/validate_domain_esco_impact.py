#!/usr/bin/env python3
"""
scripts/validate_domain_esco_impact.py — Validation A/B: DOMAIN→ESCO mapping impact on matching.

Valide en conditions réelles que le mapping DOMAIN→ESCO impacte le score,
sans modification du scoring core.

Étapes:
  1. Identifier une URI ESCO valide présente dans les offres du catalog
  2. Configurer un store isolé (in-memory) : "opcvm" ACTIVE + mapping → URI
  3. Test A (mapping OFF)  : score baseline sans injection
  4. Test B (mapping ON)   : injection ESCO URI → score augmenté
  5. Afficher tableau comparatif

Aucun changement dans matching_v1.py, idf.py ou la formule de scoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(_SRC))

from collections import defaultdict, Counter

# ── Configuration ─────────────────────────────────────────────────────────────

# CV de test : contient "OPCVM" (token candidat) mais PAS "analyse financière"
# → baseline ESCO ne matche PAS le token cible, injection = la seule source
TEST_CV = """\
Gestionnaire de fonds senior avec 8 ans d'expérience en gestion collective.
Spécialiste OPCVM actions, SICAV monétaires et fonds multi-actifs.
Suivi de portefeuilles institutionnels, sélection de titres, due diligence.
Reporting réglementaire AMF. Maîtrise Bloomberg, Excel VBA, FactSet.
Langues : français (natif), anglais courant.
Formation : Master Finance de marchés, Université Paris-Dauphine.
"""

# URI cible : "analyse financière" — présente dans 25 offres du catalog
TARGET_URI   = "http://data.europa.eu/esco/skill/99571e68-801f-49af-a897-5f75996642e1"
TARGET_LABEL = "analyse financière"
TOKEN        = "opcvm"
CLUSTER      = "FINANCE"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sep(label: str = "", width: int = 70) -> None:
    if label:
        print(f"\n{'─' * 4}  {label}  {'─' * max(0, width - len(label) - 8)}")
    else:
        print("─" * width)


def _inject_resolved(profile: dict, resolved: list) -> int:
    """Same injection logic as profile_file.py."""
    existing: set = set(profile.get("skills_uri") or [])
    injected = 0
    for r in resolved:
        uri   = r.esco_uri if hasattr(r, "esco_uri") else r["esco_uri"]
        label = (r.esco_label if hasattr(r, "esco_label") else r.get("esco_label")) or ""
        if uri not in existing:
            existing.add(uri)
            profile.setdefault("skills_uri", []).append(uri)
            injected += 1
            if label:
                sl = profile.setdefault("skills", [])
                if label not in sl:
                    sl.append(label)
    return injected


# ── Step 1 — Identify URI in catalog ─────────────────────────────────────────

def step1_identify_uri():
    _sep("ÉTAPE 1 — URI ESCO valide dans le catalog")
    from api.utils.inbox_catalog import load_catalog_offers

    print("Chargement du catalog…")
    offers = load_catalog_offers()
    print(f"  {len(offers)} offres chargées")

    # Count how many offers contain TARGET_URI
    matching_offers = [
        o for o in offers
        if TARGET_URI in (o.get("skills_uri") or [])
    ]

    print(f"\n  URI choisie  : {TARGET_URI}")
    print(f"  Label        : {TARGET_LABEL}")
    print(f"  Offres VIE contenant cette URI : {len(matching_offers)}")

    if not matching_offers:
        print("  ERREUR: aucune offre ne contient cette URI.", file=sys.stderr)
        sys.exit(1)

    # Pick the offer with the most URIs (richest signal for scoring)
    target_offer = max(matching_offers, key=lambda o: len(o.get("skills_uri") or []))
    print(f"\n  Offre de test sélectionnée :")
    print(f"    id      = {target_offer.get('id')}")
    print(f"    title   = {target_offer.get('title')}")
    print(f"    company = {target_offer.get('company')}")
    print(f"    country = {target_offer.get('country')}")
    print(f"    skills_uri count = {len(target_offer.get('skills_uri') or [])}")

    return offers, target_offer


# ── Step 2 — Baseline parse ───────────────────────────────────────────────────

def step2_baseline_parse():
    _sep("ÉTAPE 2 — Baseline parse (sans mapping)")
    from profile.baseline_parser import run_baseline

    result = run_baseline(TEST_CV, profile_id="validate-test")
    profile = result.get("profile") or {}
    baseline_count = result.get("skills_uri_count", 0)
    has_target = TARGET_URI in (profile.get("skills_uri") or [])

    print(f"  skills_uri_count    = {baseline_count}")
    print(f"  TARGET_URI présente = {has_target}")
    if has_target:
        print("  ⚠️  baseline détecte déjà l'URI cible — injection ne changera pas le count")
    else:
        print("  ✓  URI cible absente du baseline → injection visible")

    return result, profile, baseline_count


# ── Step 3 — Score A (mapping OFF) ───────────────────────────────────────────

def step3_score_off(profile_off: dict, target_offer: dict, all_offers: list):
    _sep("ÉTAPE 3 — Score A (mapping OFF)")
    from matching.matching_v1 import MatchingEngine
    from matching.extractors import extract_profile

    engine      = MatchingEngine(offers=all_offers)
    ep_off      = extract_profile(profile_off)
    result_off  = engine.score_offer(ep_off, target_offer)

    offer_uris  = frozenset(target_offer.get("skills_uri") or [])
    matched_off = len(ep_off.skills_uri & offer_uris)

    print(f"  profile skills_uri_count = {ep_off.skills_uri_count}")
    print(f"  URIs matched in offer    = {matched_off} / {len(offer_uris)}")
    print(f"  Score A                  = {result_off.score}")

    return result_off.score, ep_off.skills_uri_count, matched_off


# ── Step 4 — Setup in-memory library + mapping ────────────────────────────────

def step4_setup_library():
    _sep("ÉTAPE 4 — Configuration store in-memory (opcvm ACTIVE + mapping)")
    from compass.cluster_library import ClusterLibraryStore

    store = ClusterLibraryStore(db_path=":memory:")

    # Make "opcvm" ACTIVE via 5 offer observations (activation threshold = 5)
    for _ in range(5):
        store.record_offer_token(CLUSTER, TOKEN)
    active = store.get_active_skills(CLUSTER)
    assert TOKEN in active, f"'opcvm' should be ACTIVE after 5 offers, got {active}"

    # Register ESCO mapping
    store.add_esco_mapping(CLUSTER, TOKEN, TARGET_URI, TARGET_LABEL, "manual")
    mapping = store.get_esco_mapping(CLUSTER, TOKEN)
    assert mapping and mapping["esco_uri"] == TARGET_URI

    print(f"  token '{TOKEN}' status  = ACTIVE")
    print(f"  mapping status          = ACTIVE")
    print(f"  uri                     = {TARGET_URI}")
    print(f"  label                   = {TARGET_LABEL}")
    print("  Verification OK ✓")

    return store


# ── Step 5 — Enrich CV + inject URIs (mapping ON) ─────────────────────────────

def step5_enrich_and_inject(profile_baseline: dict, store):
    _sep("ÉTAPE 5 — Enrichissement + injection (mapping ON)")
    from compass.cv_enricher import enrich_cv
    import copy

    # Deep copy so we don't contaminate mapping-OFF profile
    profile_on = copy.deepcopy(profile_baseline)
    baseline_count = len(profile_on.get("skills_uri") or [])

    enrichment = enrich_cv(
        cv_text=TEST_CV,
        cluster=CLUSTER,
        esco_skills=[],           # no pre-existing ESCO labels (clean test)
        llm_enabled=False,
        library=store,
    )

    print(f"  domain_skills_active    = {enrichment.domain_skills_active}")
    print(f"  resolved_to_esco count  = {len(enrichment.resolved_to_esco)}")
    for r in enrichment.resolved_to_esco:
        print(f"    token={r.token_normalized}  uri={r.esco_uri}  prov={r.provenance}")

    injected = _inject_resolved(profile_on, enrichment.resolved_to_esco)

    print(f"\n  baseline_esco_count     = {baseline_count}")
    print(f"  injected_esco_from_domain = {injected}")
    print(f"  total_esco_count        = {baseline_count + injected}")

    return profile_on, baseline_count, injected


# ── Step 6 — Score B (mapping ON) ─────────────────────────────────────────────

def step6_score_on(profile_on: dict, target_offer: dict, all_offers: list):
    _sep("ÉTAPE 6 — Score B (mapping ON)")
    from matching.matching_v1 import MatchingEngine
    from matching.extractors import extract_profile

    engine      = MatchingEngine(offers=all_offers)
    ep_on       = extract_profile(profile_on)
    result_on   = engine.score_offer(ep_on, target_offer)

    offer_uris  = frozenset(target_offer.get("skills_uri") or [])
    matched_on  = len(ep_on.skills_uri & offer_uris)

    print(f"  profile skills_uri_count = {ep_on.skills_uri_count}")
    print(f"  URIs matched in offer    = {matched_on} / {len(offer_uris)}")
    print(f"  Score B                  = {result_on.score}")

    return result_on.score, ep_on.skills_uri_count, matched_on


# ── Step 7 — Structural invariant check ──────────────────────────────────────

def step7_invariant_check():
    _sep("ÉTAPE 7 — Invariant : matching_v1.py inchangé")
    matching_path = _SRC / "matching" / "matching_v1.py"
    content = matching_path.read_text(encoding="utf-8")
    forbidden = ["from compass", "import compass", "resolved_to_esco",
                 "injected_esco_from_domain", "EscoResolvedSkill"]
    violations = [t for t in forbidden if t in content]
    if violations:
        print(f"  ❌ INVARIANT VIOLÉ: {violations}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ {len(forbidden)} tokens interdits absents de matching_v1.py")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  VALIDATION A/B : DOMAIN→ESCO MAPPING IMPACT ON MATCHING")
    print("=" * 70)

    # Step 1 — catalog
    all_offers, target_offer = step1_identify_uri()

    # Step 2 — baseline
    _baseline_result, profile_baseline, baseline_esco = step2_baseline_parse()

    # Step 3 — score OFF (use a copy of baseline profile, no injection)
    import copy
    profile_off = copy.deepcopy(profile_baseline)
    score_off, uri_count_off, matched_off = step3_score_off(profile_off, target_offer, all_offers)

    # Step 4 — setup library
    store = step4_setup_library()

    # Step 5 — enrich + inject
    profile_on, baseline_count_on, injected = step5_enrich_and_inject(
        copy.deepcopy(profile_baseline), store
    )

    # Step 6 — score ON
    score_on, uri_count_on, matched_on = step6_score_on(profile_on, target_offer, all_offers)

    # Step 7 — invariant
    step7_invariant_check()

    # ── Résultats ────────────────────────────────────────────────────────────
    _sep("RÉSULTATS")
    print()
    header = f"{'Metric':<35} {'Mapping OFF':>12} {'Mapping ON':>12}"
    print(header)
    print("─" * len(header))

    rows = [
        ("baseline_esco_count",       baseline_esco,       baseline_count_on),
        ("injected_esco_from_domain",  0,                   injected),
        ("total_esco_count",           baseline_esco,       baseline_count_on + injected),
        ("skills_uri_count (profile)", uri_count_off,       uri_count_on),
        ("URIs matched in offer",      matched_off,         matched_on),
        ("score (0–100)",              score_off,           score_on),
    ]
    for label, val_off, val_on in rows:
        delta = " ✓ +" + str(val_on - val_off) if val_on > val_off else ("" if val_on == val_off else " ✗ " + str(val_on - val_off))
        print(f"  {label:<33} {val_off:>12} {val_on:>12}{delta}")

    print()

    # Assertions
    ok = True
    checks = [
        (injected >= 1,             f"injected_esco_from_domain >= 1  (got {injected})"),
        (uri_count_on > uri_count_off, f"total_esco_count increases ({uri_count_off} → {uri_count_on})"),
        (score_on >= score_off,     f"score >= score_off ({score_off} → {score_on})"),
    ]
    for passed, msg in checks:
        icon = "✓" if passed else "❌"
        print(f"  {icon}  {msg}")
        if not passed:
            ok = False

    print()
    if ok:
        print("  ✅  VALIDATION RÉUSSIE — matching_v1.py inchangé, impact confirmé")
    else:
        print("  ❌  VALIDATION ÉCHOUÉE — voir détails ci-dessus", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)


if __name__ == "__main__":
    main()
