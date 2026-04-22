"""Generic skill candidates — empirical frequency & dispersion analysis.

Source: apps/api/data/db/offers.db (local SQLite, source='business_france', 839 offers).
Runner: in-process Python. Read-only — no production code touched.

Outputs (under baseline/generic_skill_candidates/):
- _raw_offers.json             : all offers + their skills + computed cluster
- skill_frequency.csv          : per-URI frequency
- skill_dispersion.csv         : per-URI cluster dispersion + concentration
- generic_skill_candidates.json: candidate classification (hard/weak/ambiguous)
- ambiguous_skills.json        : skills not classified (edge cases)
- sample_offer_evidence.json   : 3-5 offer examples per candidate
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_SRC = ROOT / "apps" / "api" / "src"
DB_PATH = ROOT / "apps" / "api" / "data" / "db" / "offers.db"

sys.path.insert(0, str(API_SRC))
from offer.offer_cluster import detect_offer_cluster  # noqa: E402


OUT_DIR = Path(__file__).parent


def load_offers_and_skills():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    offers = {}
    for row in conn.execute(
        "SELECT id, source, title, description, country, city, publication_date FROM fact_offers "
        "WHERE source = 'business_france'"
    ):
        offers[row["id"]] = {
            "id": row["id"],
            "source": row["source"],
            "title": row["title"],
            "description": row["description"],
            "country": row["country"],
            "city": row["city"],
            "publication_date": row["publication_date"],
            "skills_with_uri": [],
            "skills_label_only": [],
        }
    for row in conn.execute(
        "SELECT offer_id, skill, skill_uri FROM fact_offer_skills"
    ):
        off = offers.get(row["offer_id"])
        if off is None:
            continue
        label = (row["skill"] or "").strip()
        uri = (row["skill_uri"] or "").strip()
        if uri:
            off["skills_with_uri"].append({"label": label, "uri": uri})
        elif label:
            off["skills_label_only"].append(label)
    conn.close()
    return list(offers.values())


def compute_clusters(offers):
    for off in offers:
        labels = [s["label"] for s in off["skills_with_uri"]] + off["skills_label_only"]
        cluster, conf, _ = detect_offer_cluster(
            off.get("title"), off.get("description"), labels
        )
        off["cluster"] = cluster or "OTHER"
        off["cluster_confidence"] = conf


def compute_frequency_and_dispersion(offers):
    N = len(offers)
    # URI-keyed stats
    uri_count = Counter()
    uri_label = {}
    uri_cluster_count = defaultdict(Counter)  # uri -> Counter({cluster: count})
    uri_offers = defaultdict(list)
    label_count = Counter()
    label_cluster_count = defaultdict(Counter)
    label_offers = defaultdict(list)
    cluster_sizes = Counter()

    for off in offers:
        cluster_sizes[off["cluster"]] += 1
        seen_uri = set()
        seen_label = set()
        for s in off["skills_with_uri"]:
            if s["uri"] in seen_uri:
                continue
            seen_uri.add(s["uri"])
            uri_count[s["uri"]] += 1
            uri_label[s["uri"]] = s["label"]  # latest wins (labels are stable for same URI)
            uri_cluster_count[s["uri"]][off["cluster"]] += 1
            if len(uri_offers[s["uri"]]) < 8:
                uri_offers[s["uri"]].append({"id": off["id"], "title": off["title"], "cluster": off["cluster"]})
        for lab in off["skills_label_only"]:
            if lab in seen_label:
                continue
            seen_label.add(lab)
            label_count[lab] += 1
            label_cluster_count[lab][off["cluster"]] += 1
            if len(label_offers[lab]) < 8:
                label_offers[lab].append({"id": off["id"], "title": off["title"], "cluster": off["cluster"]})

    rows = []
    for uri, cnt in uri_count.items():
        df = cnt / N
        cluster_hits = uri_cluster_count[uri]
        n_clusters = len(cluster_hits)
        # concentration = max(df_per_cluster) / df_overall
        # df_per_cluster[c] = cluster_hits[c] / cluster_sizes[c]
        concentrations = {
            c: (cluster_hits[c] / cluster_sizes[c]) / df if df > 0 else 0
            for c in cluster_hits
        }
        max_conc = max(concentrations.values()) if concentrations else 0.0
        dominant = max(cluster_hits, key=cluster_hits.get) if cluster_hits else "OTHER"
        dominant_share = cluster_hits[dominant] / cnt if cnt else 0.0
        rows.append({
            "skill_uri": uri,
            "label": uri_label[uri],
            "count": cnt,
            "frequency_ratio": round(df, 5),
            "cluster_count": n_clusters,
            "dominant_cluster": dominant,
            "dominant_cluster_share": round(dominant_share, 3),
            "max_concentration": round(max_conc, 3),
            "cluster_distribution": dict(cluster_hits),
            "sample_offers": uri_offers[uri][:5],
            "is_uri_backed": True,
        })

    # Add label-only rows (no URI mapped) — useful to catch canonical labels that miss URI
    for lab, cnt in label_count.items():
        if cnt < 10:  # label-only tail too noisy below this; focus on top labels
            continue
        df = cnt / N
        cluster_hits = label_cluster_count[lab]
        n_clusters = len(cluster_hits)
        concentrations = {
            c: (cluster_hits[c] / cluster_sizes[c]) / df if df > 0 else 0
            for c in cluster_hits
        }
        max_conc = max(concentrations.values()) if concentrations else 0.0
        dominant = max(cluster_hits, key=cluster_hits.get) if cluster_hits else "OTHER"
        dominant_share = cluster_hits[dominant] / cnt if cnt else 0.0
        rows.append({
            "skill_uri": None,
            "label": lab,
            "count": cnt,
            "frequency_ratio": round(df, 5),
            "cluster_count": n_clusters,
            "dominant_cluster": dominant,
            "dominant_cluster_share": round(dominant_share, 3),
            "max_concentration": round(max_conc, 3),
            "cluster_distribution": dict(cluster_hits),
            "sample_offers": label_offers[lab][:5],
            "is_uri_backed": False,
        })

    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows, dict(cluster_sizes), N


CLUSTER_SIZES = {
    "FINANCE_LEGAL": 62, "MARKETING_SALES": 102, "SUPPLY_OPS": 84,
    "ENGINEERING_INDUSTRY": 155, "DATA_IT": 382, "ADMIN_HR": 53, "OTHER": 1,
}


def _uniformity_ratio(r):
    """dom_share / cluster_prop. ~1.0 = uniform; >>1 = cluster-concentrated."""
    total = sum(CLUSTER_SIZES.values())
    dom = r["dominant_cluster"]
    clp = CLUSTER_SIZES.get(dom, 1) / total
    return (r["dominant_cluster_share"] / clp) if clp > 0 else 0.0


# Semantic tags: labels that are intrinsically tied to a specific domain,
# even when their statistical distribution looks "generic" (often due to alias
# over-injection upstream). These flags are NOT the main decision criterion —
# they flag candidates for product review under AMBIGUOUS.
_DOMAIN_INTRINSIC_LABELS = frozenset({
    "cycle de développement logiciel",
    "programmation informatique",
    "informatique décisionnelle",
    "exploration de données",
    "schéma de conception dinterface utilisateur",
    "mettre en œuvre le design front end dun site web",
    "python programmation informatique",
    "java programmation informatique",
    "sql", "mysql", "postgresql", "nosql",
    "devops", "ci",
    "argumentaire de vente",
    "analyse marketing",
    "analyse financière",
    "gestion de la relation client",
    "logistique",
    "gérer la chaîne logistique",
    "apprentissage automatique",
    "statistiques",
    "science des big data",
    "outils de gestion de configuration logicielle",
    "outils d'extraction de transformation et de chargement",
    "logiciel de visualisation des données",
    "méthodes de prospection",
    "négocier avec des parties prenantes",
    "recruter des employés",
    "gérer un cycle d'achat",
})


def classify(rows):
    """Empirical classification calibrated on real BF distribution (839 offers).

    Decision axes (all empirical except _DOMAIN_INTRINSIC_LABELS which flags
    ambiguity for product review):
      - df (frequency_ratio): how frequent in the corpus
      - cluster_count: how many of the 7 clusters contain it
      - ratio = dominant_cluster_share / dominant_cluster_prop: near 1.0 means
        the skill's distribution tracks cluster sizes (uniform); >>1 means it's
        concentrated in one cluster (domain-ish)

    Categories:
      HARD_GENERIC: df >= 5%, cluster_count == 6 (all real clusters), ratio in
        [0.7, 1.25], label NOT in _DOMAIN_INTRINSIC_LABELS
      WEAK_GENERIC: 3% <= df < 8%, cluster_count >= 5, ratio in (1.25, 2.0],
        label NOT in _DOMAIN_INTRINSIC_LABELS
      AMBIGUOUS: df >= 5% AND label in _DOMAIN_INTRINSIC_LABELS (data says
        generic, label says domain — product review needed) OR df >= 10% with
        dom_share > 0.6 and ratio > 1.6 (high-signal but cluster-tied)
      DOMAIN (implicit): everything else — not emitted as a candidate
    """
    hard_generic = []
    weak_generic = []
    ambiguous = []

    for r in rows:
        if not r["is_uri_backed"]:
            # Label-only rows are extraction artefacts (unmapped free-text like
            # "support", "team", "english") — not actionable skill candidates.
            continue

        df = r["frequency_ratio"]
        n_cl = r["cluster_count"]
        conc = r["max_concentration"]
        dom_share = r["dominant_cluster_share"]
        ratio = _uniformity_ratio(r)
        label = r["label"].strip().lower()
        r["uniformity_ratio"] = round(ratio, 3)
        r["is_domain_intrinsic_label"] = label in _DOMAIN_INTRINSIC_LABELS

        # HARD: broad, uniform, semantically transversal
        if (df >= 0.05
                and n_cl >= 6
                and 0.70 <= ratio <= 1.25
                and not r["is_domain_intrinsic_label"]):
            r["rationale"] = (
                f"df={df:.1%} across {n_cl} clusters, dom_share/cluster_prop={ratio:.2f} "
                f"→ statistically uniform; label is semantically transversal."
            )
            r["risk_if_misclassified"] = (
                "If left in scoring set, produces cross-cluster false positives "
                "(e.g. a CV mentioning 'communication' matches offers regardless of role)."
            )
            hard_generic.append(r)
            continue

        # WEAK: frequent, somewhat uniform, but slightly cluster-biased.
        # Covers mid-concentration skills in 5-6 clusters, including some with
        # higher df that don't qualify as HARD (ratio > 1.25).
        if (df >= 0.03
                and n_cl >= 5
                and 1.25 < ratio <= 2.0
                and not r["is_domain_intrinsic_label"]):
            r["rationale"] = (
                f"df={df:.1%} across {n_cl} clusters, ratio={ratio:.2f} → frequent and "
                f"diffuse but mildly concentrated; label not intrinsically domain."
            )
            r["risk_if_misclassified"] = (
                "Less disruptive than HARD; filtering yields minor improvement in "
                "cross-cluster precision. Safe to tag but low-impact."
            )
            weak_generic.append(r)
            continue

        # AMBIGUOUS case A: label is intrinsically domain but statistics look generic
        if df >= 0.05 and r["is_domain_intrinsic_label"] and 0.7 <= ratio <= 1.5:
            r["rationale"] = (
                f"Statistically spread (df={df:.1%}, {n_cl} clusters, ratio={ratio:.2f}) "
                f"but label is intrinsically domain ({r['dominant_cluster']}). "
                f"Apparent genericness likely comes from alias over-injection upstream, "
                f"not true transversality."
            )
            r["risk_if_misclassified"] = (
                "Tagging as generic would drop a legitimate DATA_IT / MKT / FIN signal "
                "on genuinely-domain candidates. Product review required."
            )
            ambiguous.append(r)
            continue

        # AMBIGUOUS case B: high df AND strongly cluster-tied
        if df >= 0.10 and dom_share > 0.60 and ratio > 1.6:
            r["rationale"] = (
                f"df={df:.1%}, but {dom_share:.0%} concentrated in {r['dominant_cluster']} "
                f"(ratio={ratio:.2f}) → behaves as domain within its cluster; not generic. "
                f"Listed as ambiguous only because high df makes naive filters flag it."
            )
            r["risk_if_misclassified"] = (
                "Removing it would destroy the scoring signal within its native cluster "
                "(e.g. programmation informatique for DATA_IT candidates)."
            )
            ambiguous.append(r)
            continue

    return hard_generic, weak_generic, ambiguous


def write_csv(rows, path, keys):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})


def main():
    print("[1/5] loading offers + skills from local SQLite …")
    offers = load_offers_and_skills()
    print(f"  {len(offers)} offers loaded")

    print("[2/5] computing cluster per offer …")
    compute_clusters(offers)

    print("[3/5] frequency + dispersion per URI …")
    rows, cluster_sizes, N = compute_frequency_and_dispersion(offers)
    print(f"  {len(rows)} skill rows, cluster sizes = {cluster_sizes}")

    # Raw offers snapshot (light)
    light_offers = [
        {
            "id": o["id"],
            "title": o["title"],
            "country": o.get("country"),
            "city": o.get("city"),
            "publication_date": o.get("publication_date"),
            "cluster": o["cluster"],
            "n_skills_with_uri": len(o["skills_with_uri"]),
            "n_skills_label_only": len(o["skills_label_only"]),
        }
        for o in offers
    ]
    (OUT_DIR / "_raw_offers.json").write_text(
        json.dumps({"N": N, "cluster_sizes": cluster_sizes, "offers": light_offers}, ensure_ascii=False, indent=2)
    )

    # CSV: frequency
    freq_rows = [
        {"skill_uri": r["skill_uri"] or "", "label": r["label"], "count": r["count"],
         "frequency_ratio": r["frequency_ratio"], "is_uri_backed": r["is_uri_backed"]}
        for r in rows
    ]
    write_csv(
        freq_rows,
        OUT_DIR / "skill_frequency.csv",
        keys=["skill_uri", "label", "count", "frequency_ratio", "is_uri_backed"],
    )

    # CSV: dispersion
    disp_rows = [
        {
            "skill_uri": r["skill_uri"] or "",
            "label": r["label"],
            "count": r["count"],
            "cluster_count": r["cluster_count"],
            "dominant_cluster": r["dominant_cluster"],
            "dominant_cluster_share": r["dominant_cluster_share"],
            "max_concentration": r["max_concentration"],
            "frequency_ratio": r["frequency_ratio"],
        }
        for r in rows
    ]
    write_csv(
        disp_rows,
        OUT_DIR / "skill_dispersion.csv",
        keys=["skill_uri", "label", "count", "frequency_ratio", "cluster_count",
              "dominant_cluster", "dominant_cluster_share", "max_concentration"],
    )

    print("[4/5] classifying candidates …")
    hard, weak, amb = classify(rows)
    print(f"  hard={len(hard)} weak={len(weak)} ambiguous={len(amb)}")

    # Candidates JSON
    def _simplify(r, verdict_family):
        return {
            "skill_uri": r["skill_uri"],
            "label": r["label"],
            "is_uri_backed": r["is_uri_backed"],
            "count": r["count"],
            "frequency_ratio": r["frequency_ratio"],
            "cluster_count": r["cluster_count"],
            "dominant_cluster": r["dominant_cluster"],
            "dominant_cluster_share": r["dominant_cluster_share"],
            "max_concentration": r["max_concentration"],
            "uniformity_ratio": r.get("uniformity_ratio"),
            "is_domain_intrinsic_label": r.get("is_domain_intrinsic_label", False),
            "cluster_distribution": r["cluster_distribution"],
            "rationale": r.get("rationale", ""),
            "risk_if_misclassified": r.get("risk_if_misclassified", ""),
            "verdict_family": verdict_family,
        }

    candidates = {
        "GENERIC_HARD_CANDIDATES": [_simplify(r, "generic_hard") for r in hard],
        "GENERIC_WEAK_CANDIDATES": [_simplify(r, "generic_weak") for r in weak],
    }
    (OUT_DIR / "generic_skill_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2)
    )

    (OUT_DIR / "ambiguous_skills.json").write_text(
        json.dumps(
            {"AMBIGUOUS_SKILLS_TO_REVIEW": [_simplify(r, "ambiguous") for r in amb]},
            ensure_ascii=False, indent=2
        )
    )

    # Sample offer evidence — 3-5 offers per candidate
    evidence = {}
    for r in hard + weak + amb:
        key = r["skill_uri"] or f"label::{r['label']}"
        evidence[key] = {
            "label": r["label"],
            "uri": r["skill_uri"],
            "frequency_ratio": r["frequency_ratio"],
            "sample_offers": r["sample_offers"],
        }
    (OUT_DIR / "sample_offer_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2)
    )

    print("[5/5] done. Summary:")
    print(f"  GENERIC_HARD_CANDIDATES: {len(hard)}")
    print(f"  GENERIC_WEAK_CANDIDATES: {len(weak)}")
    print(f"  AMBIGUOUS_SKILLS_TO_REVIEW: {len(amb)}")

    # Stats for README
    total_skills_uri = sum(r["count"] for r in rows if r["is_uri_backed"])
    unique_uris = sum(1 for r in rows if r["is_uri_backed"])
    print(f"  total_skill_rows_uri={total_skills_uri} unique_uris={unique_uris}")


if __name__ == "__main__":
    main()
