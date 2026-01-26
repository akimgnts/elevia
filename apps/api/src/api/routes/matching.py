"""
matching.py - Route FastAPI pour le matching
Sprint 7 + Sprint 11 (filtrage légal V.I.E)
Sprint 21 - Inaccessible offers visibility + Observability

Expose le moteur Sprint 6 via POST /v1/match
Applique le filtrage légal V.I.E (Sprint 11)
Expose les offres inaccessibles avec annotations (Sprint 21)
"""

import re
import time
import uuid
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from ..utils.obs_logger import obs_log

from ..schemas.matching import (
    MatchingRequest,
    MatchingResponse,
    ResultItem,
    DiagnosticResult,
    DiagnosticCriterion,
    InaccessibleOffer,
    MatchingMeta,
)

# Import moteur Sprint 6 + diagnostic Sprint 9
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine, compute_diagnostic, Verdict
from matching.extractors import extract_profile


router = APIRouter(tags=["matching"])


# ============================================================================
# SPRINT 21 - Reason to Code Mapping
# ============================================================================

def _map_reasons_to_codes(reasons: List[str]) -> List[str]:
    """
    Map human-readable reasons to stable machine codes.

    Sprint 21: Temporary local mapping until codes are embedded in diagnostic.
    Uses keyword/regex matching for deterministic code generation.

    Codes:
    - AGE_LIMIT: Age-related restrictions (28 ans, age limit)
    - NATIONALITY_INELIGIBLE: Nationality not in EU/EEA
    - COUNTRY_INELIGIBLE: Destination country restrictions
    - VISA_RESTRICTION: Visa or work permit issues
    - VIE_INELIGIBLE: Generic VIE ineligibility (fallback)
    """
    codes = []
    seen = set()

    patterns = [
        (r"(?i)\b(âge|age|28\s*ans|limite.*âge|age.*limit)", "AGE_LIMIT"),
        (r"(?i)\b(nationalité|nationality|citoyen|citizen|eu|eea|ue|eee)", "NATIONALITY_INELIGIBLE"),
        (r"(?i)\b(pays|country|destination|zone)", "COUNTRY_INELIGIBLE"),
        (r"(?i)\b(visa|permis.*travail|work.*permit|autorisation)", "VISA_RESTRICTION"),
    ]

    for reason in reasons:
        matched = False
        for pattern, code in patterns:
            if re.search(pattern, reason):
                if code not in seen:
                    codes.append(code)
                    seen.add(code)
                matched = True
                break

        # Fallback if no pattern matched
        if not matched and "VIE_INELIGIBLE" not in seen:
            codes.append("VIE_INELIGIBLE")
            seen.add("VIE_INELIGIBLE")

    # Ensure at least one code
    if not codes:
        codes.append("VIE_INELIGIBLE")

    return codes


# ============================================================================
# FILTRE LÉGAL V.I.E (Sprint 11 - kept for backwards compatibility)
# ============================================================================

def filter_legal_vie_offers(results: List[ResultItem]) -> List[ResultItem]:
    """
    Filtre les offres légalement inaccessibles (KO V.I.E Eligibility).

    Règle produit (docs/strategy/matching_product_rules.md):
    - Si diagnostic.vie_eligibility.status == KO → offre MASQUÉE
    - Aucun fallback, aucune trace côté client

    Cette fonction est une barrière légale, pas un choix UX.

    Note: Sprint 21 refactored this into the main loop, but kept for backwards compat.
    """
    return [
        r for r in results
        if r.diagnostic is None or r.diagnostic.vie_eligibility.status != "KO"
    ]


# ============================================================================
# ENDPOINT
# ============================================================================

@router.post(
    "/match",
    response_model=MatchingResponse,
    summary="Match un profil contre des offres VIE",
    description="""
Exécute le matching V1 déterministe et explicable.

**Règles métier (Sprint 6 - VERROUILLÉ):**
- Seules les offres avec `is_vie=True` sont considérées
- Seuil par défaut: 80%
- Pondérations: skills=70%, languages=15%, education=10%, country=5%
- Maximum 3 raisons par offre
- Aucun mot IA/probabilité dans les explications

**Filtrage légal (Sprint 11):**
- Les offres KO V.I.E Eligibility sont automatiquement exclues des résultats
- Un candidat ne verra jamais une offre pour laquelle il est légalement inéligible

**Inaccessible offers (Sprint 21):**
- Les offres KO sont retournées dans `inaccessible_offers` avec annotations
- `meta.filtered.legal_vie` indique le nombre d'offres filtrées
- Les offres KO ne sont PAS scorées (performance)
"""
)
async def match_profile(request: MatchingRequest) -> MatchingResponse:
    """
    Match un profil candidat contre une liste d'offres.

    Pipeline (Sprint 21):
    1. Calcule le diagnostic pour chaque offre
    2. Si KO V.I.E → ajoute à inaccessible_offers (pas de score)
    3. Si OK V.I.E → score et ajoute à results
    4. Retourne results (accessibles) + inaccessible_offers + meta
    """
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    try:
        # Construire le moteur avec IDF sur les offres fournies
        engine = MatchingEngine(
            offers=request.offers,
            context_coeffs=request.context_coeffs
        )

        # Extraire le profil une seule fois
        extracted_profile = extract_profile(request.profile)

        # Sprint 21: Separate accessible and inaccessible offers
        results: List[ResultItem] = []
        inaccessible_offers: List[InaccessibleOffer] = []

        for offer in request.offers:
            # 1. Diagnostic FIRST (Sprint 21: before scoring)
            diag = compute_diagnostic(request.profile, offer)

            # 2. Check VIE eligibility - Sprint 21: collect KO offers
            if diag.vie_eligibility.status.value == "KO":
                # Collect reasons from vie_eligibility
                reasons = []
                if diag.vie_eligibility.details:
                    reasons.append(diag.vie_eligibility.details)
                reasons.extend(diag.vie_eligibility.missing)

                # Also include top blocking reasons if VIE-related
                for reason in diag.top_blocking_reasons:
                    if reason not in reasons:
                        reasons.append(reason)

                # Map to stable codes
                codes = _map_reasons_to_codes(reasons)

                # Get offer ID
                offer_id = offer.get("id") or offer.get("offer_id") or str(hash(str(offer)))

                inaccessible_offers.append(InaccessibleOffer(
                    offer_id=str(offer_id),
                    is_accessible=False,
                    inaccessibility_codes=codes,
                    inaccessibility_reasons=reasons[:5],  # Limit to 5 reasons
                ))
                continue  # Don't score KO offers (Sprint 21 requirement)

            # 3. Score only accessible offers
            match_result = engine.score_offer(extracted_profile, offer)

            # 4. Convertir diagnostic en schema
            diagnostic_result = DiagnosticResult(
                global_verdict=diag.global_verdict.value,
                top_blocking_reasons=diag.top_blocking_reasons,
                hard_skills=DiagnosticCriterion(
                    status=diag.hard_skills.status.value,
                    details=diag.hard_skills.details,
                    missing=diag.hard_skills.missing,
                ),
                soft_skills=DiagnosticCriterion(
                    status=diag.soft_skills.status.value,
                    details=diag.soft_skills.details,
                    missing=diag.soft_skills.missing,
                ),
                languages=DiagnosticCriterion(
                    status=diag.languages.status.value,
                    details=diag.languages.details,
                    missing=diag.languages.missing,
                ),
                education=DiagnosticCriterion(
                    status=diag.education.status.value,
                    details=diag.education.details,
                    missing=diag.education.missing,
                ),
                vie_eligibility=DiagnosticCriterion(
                    status=diag.vie_eligibility.status.value,
                    details=diag.vie_eligibility.details,
                    missing=diag.vie_eligibility.missing,
                ),
            )

            results.append(ResultItem(
                offer_id=match_result.offer_id,
                score=match_result.score,
                breakdown=match_result.breakdown,
                reasons=match_result.reasons,
                diagnostic=diagnostic_result,
            ))

        # Tri par score décroissant (accessible offers only)
        results.sort(key=lambda r: r.score, reverse=True)

        # Sprint 21: Build meta with filtered counts
        legal_vie_count = len(inaccessible_offers)
        meta = MatchingMeta(
            total_processed=len(request.offers),
            filtered={"legal_vie": legal_vie_count} if legal_vie_count > 0 else None,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        obs_log("match_run", run_id=run_id, profile_id=extracted_profile.profile_id,
                status="success", duration_ms=duration_ms,
                extra={"offers_processed": len(request.offers),
                       "results_count": len(results),
                       "inaccessible_count": len(inaccessible_offers)})

        return MatchingResponse(
            profile_id=extracted_profile.profile_id,
            threshold=80,
            received_offers=len(request.offers),
            results=results,
            inaccessible_offers=inaccessible_offers,
            meta=meta,
            message=None
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        obs_log("match_run", run_id=run_id, status="error", error_code="MATCH_ERROR",
                duration_ms=duration_ms, extra={"error": str(e)[:100]})
        raise HTTPException(
            status_code=500,
            detail=f"Erreur matching: {str(e)}"
        )
