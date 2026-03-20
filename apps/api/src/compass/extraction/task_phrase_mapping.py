from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from compass.canonical.canonical_store import normalize_canonical_key


@dataclass(frozen=True)
class TaskPhraseRule:
    label: str
    phrases: tuple[str, ...]
    source_confidence: float = 0.92


@dataclass(frozen=True)
class TaskPhraseMatch:
    label: str
    matched_phrase: str
    source_section: str
    source_confidence: float
    keep_reason: str


TASK_PHRASE_RULES: tuple[TaskPhraseRule, ...] = (
    TaskPhraseRule("Lead Qualification", ("qualification de leads", "qualification d opportunites", "qualification de demandes")),
    TaskPhraseRule("Prospecting", ("prospection telephonique", "prospection", "appels sortants")),
    TaskPhraseRule("Sales Follow-up", ("suivi portefeuille clients", "suivi de prospects", "suivi des opportunites")),
    TaskPhraseRule("Quote Preparation", ("preparation de devis", "preparation d offres", "preparation d offres tarifaires")),
    TaskPhraseRule("Business Development", ("developpement commercial", "business development export")),
    TaskPhraseRule("Market Analysis", ("veille marche", "analyses de concurrence", "benchmark distributeurs")),
    TaskPhraseRule("Commercial Reporting", ("reporting commercial", "suivi d indicateurs simples")),
    TaskPhraseRule("Sales Argumentation", ("argumentaire commercial", "argumentaires marche")),
    TaskPhraseRule("Email Marketing", ("campagnes email", "envois emailing", "emailing")),
    TaskPhraseRule("Internal Communication", ("communication interne", "contenus intranet")),
    TaskPhraseRule("Content Writing", ("redaction de contenus", "redaction breves", "publication d articles")),
    TaskPhraseRule("Newsletter Production", ("redaction de newsletters", "newsletter", "newsletters mensuelles")),
    TaskPhraseRule("Event Coordination", ("coordination evenementielle", "organisation de deux seminaires internes", "aide logistique sur evenements")),
    TaskPhraseRule("Editorial Planning", ("planning editorial", "calendrier editorial", "planning de publication")),
    TaskPhraseRule("Campaign Reporting", ("reporting mensuel", "suivi taux d ouverture clics conversions")),
    TaskPhraseRule("Management Control", ("controle de gestion",)),
    TaskPhraseRule("Budget Tracking", ("suivi budgetaire", "ecarts budget realise", "suivi de budgets")),
    TaskPhraseRule("Monthly Closing", ("cloture mensuelle", "participation a cloture mensuelle")),
    TaskPhraseRule("Accounts Payable", ("comptabilite fournisseurs",)),
    TaskPhraseRule("Invoice Processing", ("traitement des factures", "controle des factures", "traitement factures fournisseurs")),
    TaskPhraseRule("Reconciliation", ("rapprochement avec commandes et receptions", "rapprochement", "rapprochement bancaire")),
    TaskPhraseRule("Dispute Handling", ("suivi des litiges", "gestion des litiges")),
    TaskPhraseRule("Payment Scheduling", ("preparation des paiements hebdomadaires", "preparation des echeanciers", "suivi paiements")),
    TaskPhraseRule("HR Administration", ("administration du personnel", "suivi rh")),
    TaskPhraseRule("Recruitment", ("entretiens de recrutement", "recrutement operationnel", "prequalification telephonique")),
    TaskPhraseRule("Onboarding", ("parcours d onboarding", "support integration", "integration")),
    TaskPhraseRule("Personnel File Management", ("suivi dossiers salaries", "dossiers candidats")),
    TaskPhraseRule("Training Coordination", ("plan de formation",)),
    TaskPhraseRule("ERP Usage", ("dans sap", "outil transport", "parametres d approvisionnement")),
    TaskPhraseRule("Inventory Management", ("gestion des stocks", "suivi des stocks")),
    TaskPhraseRule("Vendor Follow-up", ("suivi fournisseurs", "relances fournisseurs")),
    TaskPhraseRule("Purchase Order Management", ("passation de commandes fournisseurs", "commandes fournisseurs")),
    TaskPhraseRule("Logistics Coordination", ("coordination avec les prestataires", "coordinateur logistique")),
    TaskPhraseRule("Transport Operations", ("operations transport", "organisation de tournees", "outil transport")),
    TaskPhraseRule("Incident Management", ("incidents de livraison", "traitement d incidents de livraison")),
    TaskPhraseRule("Operational Coordination", ("coordination production", "coordination avec achats et magasin")),
    TaskPhraseRule("Reporting", ("reporting hebdomadaire", "tableaux de suivi")),
)


def _matches_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    if not normalized_text or not normalized_phrase:
        return False
    pattern = rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)"
    return re.search(pattern, normalized_text) is not None


def detect_task_phrase_matches(
    *,
    section_lines: Iterable[tuple[str, str]],
    mapping_inputs: Iterable[str],
) -> Dict[str, TaskPhraseMatch]:
    normalized_mapping = [
        normalize_canonical_key(token)
        for token in mapping_inputs
        if isinstance(token, str) and normalize_canonical_key(token)
    ]
    best: Dict[str, TaskPhraseMatch] = {}

    for rule in TASK_PHRASE_RULES:
        for raw_phrase in rule.phrases:
            normalized_phrase = normalize_canonical_key(raw_phrase)
            if not normalized_phrase:
                continue
            for line_norm, section in section_lines:
                if not _matches_phrase(line_norm, normalized_phrase):
                    continue
                candidate = TaskPhraseMatch(
                    label=rule.label,
                    matched_phrase=raw_phrase,
                    source_section=section,
                    source_confidence=rule.source_confidence,
                    keep_reason=f"kept:task_phrase_match:{normalized_phrase}",
                )
                current = best.get(rule.label)
                if current is None or candidate.source_confidence > current.source_confidence:
                    best[rule.label] = candidate
                break

            if rule.label in best:
                continue
            for token in normalized_mapping:
                if _matches_phrase(token, normalized_phrase):
                    best[rule.label] = TaskPhraseMatch(
                        label=rule.label,
                        matched_phrase=raw_phrase,
                        source_section="unknown",
                        source_confidence=rule.source_confidence - 0.02,
                        keep_reason=f"kept:task_phrase_mapping_input:{normalized_phrase}",
                    )
                    break

    return best
