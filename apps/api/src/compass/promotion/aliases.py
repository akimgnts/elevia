"""
aliases.py — Deterministic alias pack for ESCO promotion (Sprint 6 Step 2).

Keys are raw aliases; values are canonical labels expected to exist in ESCO.
Do NOT add fuzzy matches here.
"""

ALIAS_TO_CANONICAL_RAW = {
    # Machine learning
    "machine learning": "apprentissage automatique",
    "machine-learning": "apprentissage automatique",
    "ml": "apprentissage automatique",
    "apprentissage automatique": "apprentissage automatique",

    # Power BI / data visualization
    "power bi": "logiciel de visualisation des données",
    "powerbi": "logiciel de visualisation des données",
    "data visualization": "logiciel de visualisation des données",
    "data visualisation": "logiciel de visualisation des données",
    "visualisation de données": "logiciel de visualisation des données",
    "visualisation des données": "logiciel de visualisation des données",
    "data viz": "logiciel de visualisation des données",

    # Data engineering / ETL
    "data engineering": "ingénierie de données",
    "data engineer": "ingénierie de données",

    # Core skills
    "sql": "sql",
    "python": "python (programmation informatique)",
}
