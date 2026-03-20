import re
from typing import List

_DISPLAY_MAX_WORDS = 4
_DISPLAY_MAX_CHARS = 42
_DISPLAY_ACRONYMS = {
    "sql", "crm", "erp", "kpi", "api", "rest", "bi", "ml", "ai", "ux", "ui", "it",
    "rgpd", "sap", "seo", "sem", "smo",
}
_DISPLAY_CONNECTORS = {
    "and", "et", "avec", "pour", "de", "des", "du", "d'", "la", "le", "les",
    "aux", "au", "sur", "par", "en", "à", "dans", "l'",
}
_DISPLAY_STOPWORDS = _DISPLAY_CONNECTORS | {
    "un", "une", "son", "sa", "ses", "ce", "cet", "cette", "ces",
    "mise", "place", "mettre", "mettre-en", "mettre-en-oeuvre",
    "utiliser", "usage", "développer", "developper", "gérer", "gerer",
    "concevoir", "appliquer", "effectuer", "réaliser", "realiser",
}
_DISPLAY_OVERRIDES = {
    "gestion de projets": "Gestion de projets",
    "gestion de la relation client": "Gestion CRM",
    "développement de logiciels": "Développement logiciel",
    "commerce international": "Commerce int'l",
    "planification des ressources d'entreprise": "ERP / Planning",
    "techniques de négociation": "Négociation",
    "intelligence artificielle": "IA",
    "machine learning": "Machine Learning",
    "cloud computing": "Cloud",
    "business intelligence": "Business Intelligence",
    "power bi": "Power BI",
    "sql": "SQL",
    "python": "Python",
    "python (programmation informatique)": "Python",
    "informatique décisionnelle": "Business Intelligence",
    "exploration de données": "Exploration de données",
    "cycle de développement logiciel": "Développement logiciel",
    "techniques de marketing numérique": "Marketing digital",
    "analyse marketing": "Analyse marketing",
    "argumentaire de vente": "Argumentaire de vente",
    "développer un prototype de logiciel": "Prototype logiciel",
    "mettre en œuvre le design front end d’un site web": "Frontend",
    "mettre en oeuvre le design front end d'un site web": "Frontend",
    "schéma de conception d’interface utilisateur": "UI Design",
    "schema de conception d'interface utilisateur": "UI Design",
    "utiliser un logiciel d’analyse de données spécifique": "Analyse de données",
    "gérer le système normalisé de planification des ressources d'une entreprise": "ERP",
    "gerer le systeme normalise de planification des ressources d'une entreprise": "ERP",
    "logiciel de visualisation des données": "Visualisation de données",
    "java (programmation informatique)": "Java",
    "programmation web": "Développement web",
    "optimisation des moteurs de recherche": "SEO",
}
_DISPLAY_REPAIRS = {
    "donn es": "données",
    "activit": "activité",
    "compr hension": "compréhension",
    "coh rence": "cohérence",
    "d veloppement": "développement",
    "fran ais": "français",
    "d cision": "décision",
}


def display_skill_label(raw: str) -> str:
    base = (raw or "").strip()
    if not base:
        return raw
    key = base.lower().strip()
    if key in _DISPLAY_OVERRIDES:
        return _DISPLAY_OVERRIDES[key]
    for src, dst in _DISPLAY_REPAIRS.items():
        key = key.replace(src, dst)
    key = re.sub(r"[\\[\\](){}]", " ", key)
    key = re.sub(r"[,:;|/]+", " ", key)
    key = re.sub(r"\\s+", " ", key).strip()
    tokens = [t for t in key.split(" ") if t]
    tokens = [t[2:] if t.startswith(("d'", "l'")) and len(t) > 2 else t for t in tokens]
    while tokens and tokens[0] in _DISPLAY_CONNECTORS:
        tokens.pop(0)
    while tokens and tokens[-1] in _DISPLAY_CONNECTORS:
        tokens.pop()
    token_set = set(tokens)
    if "analyse" in token_set and ("données" in token_set or "donnees" in token_set):
        return "Analyse de données"
    if "gestion" in token_set and "projet" in token_set:
        return "Gestion de projet"
    if "automatisation" in token_set:
        return "Automatisation"
    if "tableau" in token_set and "bord" in token_set:
        return "Tableau de bord"
    if "business" in token_set and "intelligence" in token_set:
        return "Business Intelligence"
    if "power" in token_set and "bi" in token_set:
        return "Power BI"
    if "frontend" in token_set or {"front", "end"} <= token_set:
        return "Frontend"
    if "interface" in token_set and "utilisateur" in token_set:
        return "UI Design"
    if "api" in token_set and "rest" in token_set:
        return "API REST"
    if "marketing" in token_set and ("numérique" in token_set or "numerique" in token_set or "digital" in token_set):
        return "Marketing digital"
    if "visualisation" in token_set and ("données" in token_set or "donnees" in token_set):
        return "Visualisation de données"
    if "erp" in token_set:
        return "ERP"
    if "excel" in token_set and ("avance" in token_set or "avancé" in token_set or "croisé" in token_set):
        return "Excel avancé"
    if len(tokens) > _DISPLAY_MAX_WORDS:
        tokens = [t for t in tokens if t not in _DISPLAY_STOPWORDS]
    if len(tokens) > _DISPLAY_MAX_WORDS:
        tokens = tokens[:_DISPLAY_MAX_WORDS]
    if not tokens:
        tokens = [key]
    dedup: List[str] = []
    for t in tokens:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    label = " ".join(dedup)
    if len(label) > _DISPLAY_MAX_CHARS and len(dedup) > 3:
        dedup = dedup[:3]
        label = " ".join(dedup)

    def _title_case_word(word: str) -> str:
        if "-" in word:
            parts = word.split("-")
            return "-".join(_title_case_word(p) for p in parts)
        if word.lower() in _DISPLAY_ACRONYMS:
            return word.upper()
        return word.capitalize()

    return " ".join(_title_case_word(w) for w in label.split())
