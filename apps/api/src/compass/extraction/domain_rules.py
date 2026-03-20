from __future__ import annotations

import re
from typing import Dict

from compass.canonical.canonical_store import normalize_canonical_key

_DOMAIN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sales", ("vente", "ventes", "client", "clients", "prospect", "prospects", "crm", "commercial", "portefeuille", "devis", "opportunite", "opportunites")),
    ("finance", ("finance", "financier", "financiere", "budget", "budgets", "facture", "factures", "comptabilite", "reporting financier", "cloture", "paiement", "paiements", "rapprochement", "controle de gestion")),
    ("hr", ("recrutement", "salaries", "salariés", "personnel", "rh", "onboarding", "formation", "dossiers candidats", "administration du personnel", "entretiens")),
    ("supply_chain", ("logistique", "stocks", "stock", "livraison", "livraisons", "transport", "expedition", "expeditions", "fournisseur", "fournisseurs", "approvisionnement", "entrepot", "entrepôt", "tournees", "tms")),
    ("marketing", ("newsletter", "newsletters", "contenu", "contenus", "campagne", "campagnes", "editorial", "publication", "seo", "emailing", "communication interne", "canva", "wordpress")),
    ("data", ("donnees", "données", "sql", "dashboard", "dashboards", "power bi", "looker", "etl", "dataset", "kpi", "reporting data")),
)

_DOMAIN_WEIGHTS = {
    "sales": 1.0,
    "finance": 1.0,
    "hr": 0.95,
    "supply_chain": 0.95,
    "marketing": 0.9,
    "data": 0.85,
    "generic": 0.3,
    "unknown": 0.0,
}


def infer_domain(*texts: str) -> tuple[str, float, list[str]]:
    haystack = " ".join(normalize_canonical_key(text or "") for text in texts if text)
    if not haystack:
        return "unknown", 0.0, []
    scores: Dict[str, int] = {}
    hits: Dict[str, list[str]] = {}
    for domain, keywords in _DOMAIN_RULES:
        matched = []
        for keyword in keywords:
            normalized_keyword = normalize_canonical_key(keyword)
            if not normalized_keyword:
                continue
            if re.search(rf"(?<!\w){re.escape(normalized_keyword)}(?!\w)", haystack):
                matched.append(keyword)
        if matched:
            scores[domain] = len(matched)
            hits[domain] = matched
    if not scores:
        return "unknown", 0.0, []
    best_domain = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
    weight = _DOMAIN_WEIGHTS.get(best_domain, 0.0)
    return best_domain, weight, hits.get(best_domain, [])
