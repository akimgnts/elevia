#!/usr/bin/env python3
"""
discover_skills_from_corpus.py - Explore skill term frequencies in the BF corpus.

Read-only exploration. Does not modify the pipeline or write to the database.
Produces a CSV report of candidate skill terms by cluster.

Usage:
    DATABASE_URL=... python3 apps/api/scripts/discover_skills_from_corpus.py [--min-freq N] [--out FILE]
"""

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ── already-covered aliases (keys only) ──────────────────────────────────────
KNOWN_ALIASES: Set[str] = {
    "python", "javascript", "java", "react", "nodejs", "node.js", "typescript",
    "c++", "php", "ruby", "swift", "kotlin", "rust", "sql", "mysql",
    "postgresql", "nosql", "excel", "tableur", "microsoft excel", "powerbi",
    "power bi", "aws", "docker", "kubernetes", "git", "agile", "scrum",
    "jira", "project_management", "gestion de projet", "seo", "référencement",
    "crm", "sap", "salesforce", "adobe_xd", "procurement", "sales", "vente",
    "negotiation", "négociation", "data_visualization", "data visualization",
    "data", "data analysis", "data analyst", "analyst", "analyse",
    "machine_learning", "tensorflow", "financial_modeling", "financial modeling",
    "modélisation financière", "financier", "accounting", "communication",
    "leadership", "teamwork", "travail en équipe", "ux_design", "figma",
    "django", "wordpress", "html", "css", "design", "marketing",
    "marketing digital", "marketing_digital", "google_analytics",
    "google analytics", "erp", "supply_chain",
}

# ── stopwords (FR + EN) ───────────────────────────────────────────────────────
STOPWORDS: Set[str] = {
    # French
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "à", "au",
    "aux", "en", "pour", "par", "sur", "dans", "avec", "sans", "nous", "vous",
    "ils", "notre", "votre", "leur", "ce", "cette", "ces", "son", "sa", "ses",
    "est", "sont", "être", "avoir", "faire", "très", "plus", "moins", "mais",
    "car", "donc", "or", "ni", "que", "qui", "quoi", "dont", "où", "si",
    "il", "elle", "on", "y", "en", "chez", "tant", "mois", "mission",
    "poste", "profil", "candidat", "entreprise", "equipe", "sein", "cadre",
    "contrat", "cdi", "cdd", "stage", "vie", "vos", "vot", "nos",
    "tout", "tous", "toute", "toutes", "bien", "aussi", "même", "comme",
    "après", "avant", "lors", "chez", "entre", "vers", "sous", "jusque",
    "puis", "lors", "ainsi", "afin", "notamment", "également", "dès",
    # English
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "as", "at", "by", "from", "is", "are", "be", "was", "were", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "this", "that",
    "these", "those", "your", "our", "their", "its", "his", "her", "my",
    # Filler
    "requis", "required", "souhaite", "souhaité", "preferred", "etc", "niveau",
    "level", "ans", "years", "experience", "expérience", "minimum", "maximum",
    "bonne", "bon", "bons", "bonnes", "forte", "fort", "solide", "excellent",
    "excellente", "recherche", "recherchons", "souhait", "idealement",
    "idéalement", "idéale", "idéal",
}

# ── cluster rules (ordered; first match wins) ────────────────────────────────
CLUSTER_RULES: List[Tuple[str, List[str]]] = [
    ("finance",     ["finance", "financier", "financière", "comptable", "audit",
                     "trésor", "tresor", "contrôle de gestion", "controle de gestion",
                     "budget", "investment", "banking", "fiscal", "fiscale", "cfo",
                     "m&a", "fusion"]),
    ("data",        ["data", "analyst", "analytics", "données", "reporting",
                     "bi ", " bi ", "business intelligence", "statistique",
                     "machine learning", "ia ", "intelligence artificielle"]),
    ("marketing",   ["marketing", "communication", "digital", "brand", "content",
                     "rédacteur", "redacteur", "influence", "social media",
                     "seo", "sem", "emailing", "growth"]),
    ("supply",      ["supply", "logistique", "logistic", "achats", "achat",
                     "procurement", "approvision", "stock", "entrepôt", "entrepot",
                     "transport", "douane", "import", "export"]),
    ("engineering", ["engineer", "ingénieur", "ingenieur", "technique", "dev ",
                     "développeur", "developpeur", "software", "backend", "frontend",
                     "fullstack", "cloud", "devops", "infrastructure", "réseau",
                     "système", "systeme", "embedded", "electronic"]),
    ("sales",       ["commercial", "vente", "sales", "business development",
                     "business dev", "account manager", "account executive",
                     "relation client", "crm", "grands comptes"]),
    ("hr",          ["ressources humaines", "human resources", "recrutement",
                     "rh ", " rh", "talent", "formation", "learning",
                     "compensation", "paie", "payroll"]),
    ("consulting",  ["consultant", "conseil", "advisory", "strategy", "stratégie",
                     "strategie", "transformation", "management consulting"]),
    ("project",     ["chef de projet", "project manager", "project management",
                     "programme manager", "pmo", "product owner", "product manager",
                     "scrum master"]),
]


# ── text normalization ────────────────────────────────────────────────────────

_STRIP_TAGS = re.compile(r"<[^>]+>")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    text = _STRIP_TAGS.sub(" ", text)
    text = _strip_accents(text.lower())
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


# ── cluster assignment ────────────────────────────────────────────────────────

def assign_cluster(title: str) -> str:
    t = _normalize(title or "")
    for cluster, keywords in CLUSTER_RULES:
        for kw in keywords:
            if kw in t:
                return cluster
    return "other"


# ── n-gram extraction ─────────────────────────────────────────────────────────

def extract_ngrams(text: str, max_n: int = 3) -> List[str]:
    if not text:
        return []
    norm = _normalize(text)
    words = [w for w in norm.split() if len(w) >= 2 and w not in STOPWORDS and not w.isdigit()]
    ngrams: List[str] = []
    for n in range(1, max_n + 1):
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i: i + n])
            # Filter: all words in bigram/trigram must be non-stopword
            if n > 1:
                parts = gram.split()
                if any(p in STOPWORDS for p in parts):
                    continue
                if any(p.isdigit() for p in parts):
                    continue
            ngrams.append(gram)
    return ngrams


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Explore skill term frequencies in BF corpus")
    parser.add_argument("--min-freq", type=int, default=5, help="Minimum global frequency (default: 5)")
    parser.add_argument("--out", type=str, default="bf_skill_candidates.csv", help="Output CSV path")
    parser.add_argument("--top", type=int, default=20, help="Top N global terms to print")
    parser.add_argument("--top-cluster", type=int, default=10, help="Top N per cluster to print")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERROR] DATABASE_URL not set", file=sys.stderr)
        return 1

    print("=" * 60)
    print("SKILL CORPUS EXPLORER — business_france")
    print("=" * 60)

    # ── load from PostgreSQL ──────────────────────────────────────────────────
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT external_id, title, mission_profile, description
                    FROM clean_offers
                    WHERE source = 'business_france'
                    ORDER BY external_id
                    """
                )
                rows = cur.fetchall()
    except Exception as e:
        print(f"[ERROR] PostgreSQL connection failed: {e}", file=sys.stderr)
        return 1

    print(f"[READ] {len(rows)} BF offers loaded")

    # ── counters ──────────────────────────────────────────────────────────────
    global_counter: Counter = Counter()
    # cluster → Counter of terms
    cluster_counters: Dict[str, Counter] = defaultdict(Counter)
    # term → set of offer external_ids (up to 3)
    term_examples: Dict[str, List[str]] = defaultdict(list)

    cluster_sizes: Counter = Counter()

    for external_id, title, mission_profile, description in rows:
        text = mission_profile or description or ""
        cluster = assign_cluster(title or "")
        cluster_sizes[cluster] += 1

        ngrams = extract_ngrams(text)
        seen_in_offer: Set[str] = set()

        for gram in ngrams:
            if gram in seen_in_offer:
                continue
            seen_in_offer.add(gram)
            global_counter[gram] += 1
            cluster_counters[cluster][gram] += 1
            if len(term_examples[gram]) < 3:
                term_examples[gram].append(external_id)

    print(f"[EXTRACT] {len(global_counter)} unique n-grams extracted")

    # ── filter ────────────────────────────────────────────────────────────────
    total_offers = len(rows)
    candidates = []

    for term, freq in global_counter.items():
        if freq < args.min_freq:
            continue
        # Skip pure numbers
        if term.replace(" ", "").isdigit():
            continue
        # Skip very short single-char tokens
        if len(term) < 2:
            continue

        already_mapped = term.lower() in KNOWN_ALIASES

        # Best cluster for this term
        best_cluster = max(cluster_counters.keys(), key=lambda c: cluster_counters[c].get(term, 0))
        cluster_freq = cluster_counters[best_cluster].get(term, 0)
        cluster_size = cluster_sizes[best_cluster]
        concentration = (cluster_freq / cluster_size) / (freq / total_offers) if freq > 0 and total_offers > 0 and cluster_size > 0 else 0.0

        candidates.append({
            "term": term,
            "frequency": freq,
            "best_cluster": best_cluster,
            "cluster_frequency": cluster_freq,
            "cluster_size": cluster_size,
            "concentration_ratio": round(concentration, 2),
            "examples": "|".join(term_examples[term][:3]),
            "already_mapped": already_mapped,
            "candidate_alias": not already_mapped and freq >= args.min_freq,
        })

    # Sort by frequency descending
    candidates.sort(key=lambda x: -x["frequency"])

    print(f"[FILTER] {len(candidates)} terms with freq >= {args.min_freq}")
    print(f"[FILTER] {sum(1 for c in candidates if not c['already_mapped'])} new (not yet in aliases)")

    # ── top 20 global ─────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"TOP {args.top} GLOBAL TERMS (freq >= {args.min_freq}, new only)")
    print(f"{'─' * 60}")
    new_only = [c for c in candidates if not c["already_mapped"]]
    for i, c in enumerate(new_only[: args.top], 1):
        print(f"  {i:3}. [{c['frequency']:4}]  {c['term']:<40}  cluster={c['best_cluster']}")

    # ── top N per cluster ────────────────────────────────────────────────────
    all_clusters = sorted(set(c["best_cluster"] for c in candidates))
    for cluster in all_clusters:
        cluster_candidates = [c for c in candidates if c["best_cluster"] == cluster and not c["already_mapped"]]
        cluster_candidates.sort(key=lambda x: -x["cluster_frequency"])
        print(f"\n{'─' * 60}")
        print(f"TOP {args.top_cluster} — {cluster.upper()} (size={cluster_sizes[cluster]})")
        print(f"{'─' * 60}")
        for i, c in enumerate(cluster_candidates[: args.top_cluster], 1):
            print(
                f"  {i:2}. [{c['cluster_frequency']:3}/{c['cluster_size']:3}]"
                f"  ratio={c['concentration_ratio']:4.1f}"
                f"  {c['term']}"
            )

    # ── write CSV ─────────────────────────────────────────────────────────────
    out_path = Path(args.out)
    fieldnames = [
        "term", "frequency", "best_cluster", "cluster_frequency", "cluster_size",
        "concentration_ratio", "already_mapped", "candidate_alias", "examples",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"\n[OUT] CSV written → {out_path.resolve()}")
    print(f"[OUT] {len(candidates)} rows total, {sum(1 for c in candidates if c['candidate_alias'])} candidate aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
