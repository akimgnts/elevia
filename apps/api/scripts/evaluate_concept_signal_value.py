from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Sequence

from api.utils.inbox_catalog import load_catalog_offers
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.offer.offer_intelligence import build_offer_intelligence
from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload
from compass.scoring.scoring_v2 import build_scoring_v2
from matching import MatchingEngine
from matching.extractors import extract_profile

_ROOT = Path(__file__).resolve().parents[1]
_OUT_JSON = _ROOT / "data" / "eval" / "concept_signal_value_eval_results.json"

_GENERIC_NOISE = {
    "reporting",
    "excel",
    "python",
    "sql",
    "sap",
    "crm",
    "sirh",
    "tms",
    "communication",
}


def _normalize(value: Any) -> str:
    from compass.canonical.canonical_store import normalize_canonical_key

    return normalize_canonical_key(str(value or ""))


def _token_set(value: str) -> set[str]:
    return {token for token in _normalize(value).split() if token}



def _signals_match(left: str, right: str) -> bool:
    left_key = _normalize(left)
    right_key = _normalize(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    if left_key in right_key or right_key in left_key:
        return True
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    return len(overlap) >= min(len(left_tokens), len(right_tokens)) or len(overlap) >= 2



def _clearly_present_in_canonical(concept: str, canonical_labels: Sequence[str]) -> bool:
    concept_key = _normalize(concept)
    if not concept_key:
        return False
    for label in canonical_labels:
        label_key = _normalize(label)
        if not label_key:
            continue
        if concept_key == label_key:
            return True
        if len(concept_key) > 4 and len(label_key) > 4 and (concept_key in label_key or label_key in concept_key):
            return True
        if _signals_match(concept_key, label_key):
            return True
    return False



def _noise_concepts(concept_signals: Sequence[dict]) -> list[str]:
    noise: list[str] = []
    for item in concept_signals:
        concept = str(item.get("concept") or "").strip()
        key = _normalize(concept)
        domain = str(item.get("domain") or "unknown")
        tokens = list(item.get("tokens") or [])
        if not key:
            continue
        if domain == "unknown":
            noise.append(concept)
            continue
        if len(tokens) <= 1 and key in _GENERIC_NOISE:
            noise.append(concept)
            continue
    return sorted(dict.fromkeys(noise))



def _case_verdict(*, matched_concepts: Sequence[str], missed: Sequence[str], noise: Sequence[str], score_pct: int) -> str:
    if missed:
        return "PROBLEM"
    if matched_concepts and not noise and score_pct >= 70:
        return "GOOD"
    return "PARTIAL"


CV_CASES = [
    {
        "domain": "Finance",
        "offer_id": "BF-AZ-0001",
        "cv_text": textwrap.dedent(
            """
            Profil: 3 ans en contrôle / reporting, un peu couteau suisse. J'ai touché compta, budget, closing, fichiers Excel pas toujours propres, participation à des points avec finance manager + ops. English ok, Francais natif.

            Expériences
            Junior controlling analyst - PME industrielle
            - reporting mensuel, analyse des coûts, budget follow-up, variance / ecarts
            - participation à la cloture, rapprochements, support audit interne
            - mise a jour dashboards Excel / power bi, controle données, checks SAP
            - worked with plant manager on KPI / stock / margins, not only finance pure
            - gestion tableaux, suivi factures fournisseurs, cash forecast parfois

            Avant: assistanat comptable / admin
            * saisie facture, paiements, relances soft
            * support admin, documents, participation process

            Skills / tools
            Excel, Power BI, SAP, reporting, analyse financière, data analysis, budget, budget, audit, comptabilité, anglais, teamwork
            """
        ).strip(),
    },
    {
        "domain": "Sales / Business Dev",
        "offer_id": "BF-AZ-0004",
        "cv_text": textwrap.dedent(
            """
            Je viens du commercial B2B avec un côté structuration / CRM mais pas super carré sur le CV. Business dev, prospection, suivi pipeline, un peu d'analyse data pour mieux voir les conversions.

            Experience
            Chargé d'affaires / Biz dev
            - gestion portefeuille clients et prospection outbound / calls / mails
            - qualification leads, rdv, devis, closing parfois avec le manager
            - CRM update, Salesforce / Hubspot selon période, reporting weekly
            - participation à salons, benchmark marché, customer needs analysis
            - suivi commercial + relances + un peu de data cleaning dans les contacts

            autre poste vente terrain
            • relation client • fidélisation • objectifs • mise en rayon aussi au début
            • online prospecting, support offre, participation à des réponses AO

            Outils / skills
            CRM, Salesforce, Hubspot, prospection, business development, vente, reporting, Excel, communication, négo, portefeuille clients, customer journey
            """
        ).strip(),
    },
    {
        "domain": "Marketing / Communication",
        "offer_id": "BF-AZ-0012",
        "cv_text": textwrap.dedent(
            """
            Profil marketing/com un peu hybride. J'ai fait contenu, campagnes, coordination, emailing, events. Pas mal de choses en même temps donc CV pas ultra précis.

            Exp pro
            Marketing & communication assistant
            - newsletters, emailing, content creation, support social media
            - campaign analysis, open rates / clicks, petit reporting Power BI/Excel
            - participation à l'organisation event / salon / supports print
            - rédaction contenus FR/EN, website updates wordpress, coordination agences
            - communication interne aussi, demandes diverses, visuals Canva/Adobe

            Stage com
            - mise à jour site, articles, participation campagnes
            - help on branding / visuels / brochure / event follow-up

            Skills
            communication, marketing digital, content, contenus, newsletter, emailing, Mailchimp, Canva, Photoshop, Illustrator, Wordpress, campaign analysis, anglais, organisation
            """
        ).strip(),
    },
    {
        "domain": "Supply Chain / Operations",
        "offer_id": "BF-AZ-0005",
        "cv_text": textwrap.dedent(
            """
            Coordinateur ops/logistique, parcours pas linéaire. J'ai fait appro, flux, fournisseurs, transport mais aussi reporting et sujets process. Quelques phrases sont vagues parce que plusieurs missions à la fois.

            Experience
            Supply chain coordinator
            - suivi approvisionnement, fournisseurs, commandes achat / purchase orders
            - coordination transport, livraisons, stocks, incidents entrepot
            - reporting KPI service + update fichiers excel + SAP
            - participation amélioration process / flux / performance opérationnelle
            - vendor follow-up, planning, claims, litiges, sometimes customs docs

            Avant operations assistant
            - gestion tableaux, suivi activité, support exploitation, dispatch
            - participation projets, mise a jour master data

            Tools & skills
            SAP, Excel, TMS, supply chain, logistique, approvisionnement, stock management, transport operations, fournisseur, reporting, process improvement
            """
        ).strip(),
    },
    {
        "domain": "HR",
        "offer_id": "BF-AZ-0010",
        "cv_text": textwrap.dedent(
            """
            Profil RH généraliste junior, surtout admin du personnel + recrutement + onboarding. J'ai aussi fait beaucoup de support un peu flou / transversal.

            Experience
            Assistant RH
            - administration du personnel, dossiers salariés, contrats / avenants
            - recrutement: tri CV, entretiens tel, suivi candidats, onboarding
            - participation formation / planning / tableaux de suivi RH
            - reporting, KPI recrutement, mise à jour SIRH / Excel
            - support managers sur besoins staffing, questions RH simples

            autre expérience office/admin
            - participation paie / absences / documents
            - organisation sessions intégration, communication interne ponctuelle

            Outils / compétences
            recrutement, onboarding, administration du personnel, SIRH, Excel, reporting, RH, entretiens, formation, communication, anglais professionnel
            """
        ).strip(),
    },
    {
        "domain": "Data / BI",
        "offer_id": "BF-AZ-SAMPLE-0001",
        "cv_text": textwrap.dedent(
            """
            Data / BI profile but not pure tech. I worked on dashboards, analyse de données, cleaning, business requests and some automation. Mixed French/English because teams were international.

            Experience
            Data analyst / BI support
            - data analysis sur ventes + operations, multi-source analysis
            - data cleaning, anomaly detection, dashboarding Power BI
            - SQL queries, extraction, KPI design, forecasting support
            - participation à des sujets marketing & finance, reporting automatique Python / Excel
            - understanding business needs, process analysis, signal extraction from messy files
            - pas mal de support ad hoc / visualisation / present results

            Project
            - scoring models, matching logic, APIs, datasets structuring
            - some ML curiosity but not real production ML

            Stack / skills
            Python, SQL, Power BI, Excel, Power Query, REST APIs, data analysis, analyse de données, forecasting, data quality, dashboard, reporting, communication
            """
        ).strip(),
    },
]


def _parse_profile(cv_text: str, domain: str) -> Dict[str, Any]:
    return build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id=f"concept-eval-{domain.lower().replace(' ', '-')}",
            raw_filename=f"{domain.lower().replace(' ', '_')}.txt",
            content_type="text/plain",
            file_bytes=cv_text.encode("utf-8"),
            enrich_llm=0,
        )
    )



def _evaluate_case(case: Dict[str, Any], offer: Dict[str, Any]) -> Dict[str, Any]:
    profile_payload = _parse_profile(case["cv_text"], case["domain"])
    canonical_labels = [
        str(item.get("label") or item.get("raw") or "")
        for item in list(profile_payload.get("canonical_skills") or [])
        if str(item.get("label") or item.get("raw") or "").strip()
    ]
    concept_signals = list(profile_payload.get("concept_signals") or [])
    added_concepts = [
        item for item in concept_signals if not _clearly_present_in_canonical(str(item.get("concept") or ""), canonical_labels)
    ]

    offer_intelligence = build_offer_intelligence(offer=offer)
    offer_targets = list(offer_intelligence.get("top_offer_signals") or []) + list(offer_intelligence.get("required_skills") or [])
    matched_concepts = [
        str(item.get("concept") or "")
        for item in added_concepts
        if any(_signals_match(str(item.get("concept") or ""), target) for target in offer_targets)
    ]
    matched_concepts = list(dict.fromkeys([item for item in matched_concepts if item]))

    profile_intelligence = dict(profile_payload.get("profile_intelligence") or {})
    semantic = build_semantic_explainability(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        explanation=None,
    )
    engine = MatchingEngine([offer])
    extracted = extract_profile(profile_payload.get("profile") or {})
    match = engine.score_offer(extracted, offer)
    scoring_v2 = build_scoring_v2(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        semantic_explainability=semantic,
        matching_score=match.score,
    )
    score_pct = int((scoring_v2 or {}).get("score_pct") or 0)

    missed_matches = matched_concepts if matched_concepts and score_pct < 70 else []
    captured_matches = matched_concepts if matched_concepts and score_pct >= 70 else []
    noise = _noise_concepts(concept_signals)

    return {
        "domain": case["domain"],
        "offer_id": case["offer_id"],
        "offer_title": offer.get("title"),
        "canonical_skills": canonical_labels,
        "concept_signals": concept_signals,
        "top_offer_signals": offer_intelligence.get("top_offer_signals") or [],
        "required_skills": offer_intelligence.get("required_skills") or [],
        "scoring_v2": scoring_v2,
        "added_concepts": [str(item.get("concept") or "") for item in added_concepts],
        "matched_concepts": matched_concepts,
        "missed_matches": missed_matches,
        "captured_matches": captured_matches,
        "noise": noise,
        "verdict": _case_verdict(
            matched_concepts=matched_concepts,
            missed=missed_matches,
            noise=noise,
            score_pct=score_pct,
        ),
    }



def _final_verdict(results: Sequence[Dict[str, Any]]) -> str:
    missed = sum(1 for row in results if row.get("missed_matches"))
    matched = sum(1 for row in results if row.get("matched_concepts"))
    noisy = sum(1 for row in results if len(row.get("noise") or []) >= 4)
    if noisy > max(1, len(results) // 2):
        return "CONCEPT LAYER NOISY"
    if missed > 0:
        return "CONCEPT LAYER USEFUL BUT NOT EXPLOITED"
    if matched > 0:
        return "CONCEPT LAYER HIGH VALUE"
    return "CONCEPT LAYER NOISY"



def main() -> None:
    offers = load_catalog_offers()
    by_id = {str(offer.get("id") or ""): offer for offer in offers}

    cases: List[Dict[str, Any]] = []
    for case in CV_CASES:
        offer = by_id.get(case["offer_id"])
        if not offer:
            continue
        cases.append(_evaluate_case(case, offer))

    missed_count = sum(1 for row in cases if row.get("missed_matches"))
    weakest_domains = [row["domain"] for row in cases if row.get("verdict") == "PROBLEM"]
    data_bias = any(row["domain"] != "Data / BI" and any("data" in _normalize(item) for item in row.get("matched_concepts") or []) for row in cases)

    results = {
        "case_count": len(cases),
        "missed_match_case_count": missed_count,
        "weakest_domains": weakest_domains,
        "data_analytics_bias_still_visible": data_bias,
        "concept_layer_reveals_business_value": any(bool(row.get("matched_concepts")) for row in cases),
        "final_verdict": _final_verdict(cases),
        "cases": cases,
    }

    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    for row in cases:
        score_pct = int((row.get("scoring_v2") or {}).get("score_pct") or 0)
        print(f"Case: {row['domain']}")
        print("Added concepts:")
        for item in row.get("added_concepts") or []:
            print(f"- {item}")
        print("Matched concepts:")
        for item in row.get("matched_concepts") or []:
            print(f"- {item}")
        print("Missed matches:")
        for item in row.get("missed_matches") or []:
            print(f"- {item}")
        print("Noise:")
        for item in row.get("noise") or []:
            print(f"- {item}")
        print(f"Score: {score_pct}%")
        print(f"Verdict:\n- {row['verdict']}")
        print()

    print("Final analysis")
    print(f"- MISSED_MATCH cases: {missed_count}")
    print(f"- Weakest domains: {', '.join(weakest_domains) if weakest_domains else 'none'}")
    print(f"- Is the system still biased toward data/analytics?: {'yes' if data_bias else 'no'}")
    print(f"- Does concept_signals reveal real business value?: {'yes' if results['concept_layer_reveals_business_value'] else 'no'}")
    print(f"Final verdict: {results['final_verdict']}")


if __name__ == "__main__":
    main()
