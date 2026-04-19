"""
extract.py - Raw Skill Extraction Helpers
Sprint 24 - Phase 3

Improved skill extraction from offers and profiles using multiple fields.
Includes skill alias expansion to match ESCO vocabulary better.
"""

import re
import unicodedata
from typing import Any, Dict, List, Set

# Skill aliases: map common short forms to EXACT ESCO labels
# These expand tokens to increase ESCO match probability
# Labels verified against ESCO v1.2.1-fr CSV
SKILL_ALIASES: Dict[str, List[str]] = {
    # Programming languages - use EXACT ESCO preferred labels
    "python": ["python (programmation informatique)"],
    "javascript": ["javascript"],
    "java": ["java (programmation informatique)"],
    "react": ["javascript framework"],
    "nodejs": ["javascript"],
    "node.js": ["javascript"],
    "typescript": ["typescript"],
    "c++": ["c++"],
    "php": ["php"],
    "ruby": ["ruby"],
    "swift": ["swift"],
    "kotlin": ["kotlin"],
    "rust": ["rust"],
    # Data tools - use EXACT ESCO labels
    "sql": ["sql"],
    "mysql": ["mysql"],
    "postgresql": ["postgresql"],
    "nosql": ["nosql"],
    # Excel - ESCO has "utiliser un logiciel de tableur" and alt "microsoft office excel"
    "excel": ["utiliser un logiciel de tableur", "microsoft office excel"],
    "tableur": ["utiliser un logiciel de tableur"],
    "microsoft excel": ["utiliser un logiciel de tableur", "microsoft office excel"],
    # Power BI - check if exists in ESCO
    "powerbi": ["logiciel de visualisation des données", "utiliser un logiciel danalyse de données spécifique"],
    "power bi": ["logiciel de visualisation des données", "utiliser un logiciel danalyse de données spécifique"],
    # Cloud/DevOps
    "aws": ["amazon web services"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes"],
    "git": ["git"],
    # Methodologies - use EXACT ESCO labels
    "agile": ["gestion de projets par méthode agile", "développement par itérations"],
    "scrum": ["scrum"],
    "jira": ["gestion de projets par méthode agile", "gestion de projets", "développement par itérations"],
    # Project management - ESCO has "gestion de projets"
    # Sprint4-C1: key aligned with BIGRAM_WHITELIST entry "project management" (space, not underscore)
    "project management": ["gestion de projets", "gestion de projets par méthode agile", "développement par itérations"],
    "gestion de projet": ["gestion de projets"],
    # Marketing - ESCO has "optimisation des moteurs de recherche"
    "seo": ["optimisation des moteurs de recherche"],
    "référencement": ["optimisation des moteurs de recherche"],
    # CRM, SAP - check exact labels
    "crm": ["gestion de la relation client"],
    "sap": ["gérer le système normalisé de planification des ressources dune entreprise"],
    "salesforce": ["gestion de la relation client"],
    "adobe_xd": ["concevoir une interface utilisateur", "créer un prototype de solution en matière dexpérience utilisateur"],
    "procurement": ["gérer un cycle dachat", "coordonner les activités dachat"],
    # Sales - ESCO has "argumentaire de vente", "gérer des équipes de vente"
    # Sprint4-N3: 'sales' removed — context-free trigger produced noise on CVs where 'sales' denotes the client team, not a skill
    "vente": ["argumentaire de vente"],
    "negotiation": ["négocier des conditions avec les fournisseurs", "négocier les prix"],
    "négociation": ["négocier des conditions avec les fournisseurs", "négocier les prix"],
    # Data viz - check ESCO
    "data_visualization": ["logiciel de visualisation des données", "utiliser un logiciel danalyse de données spécifique"],
    "data visualization": ["logiciel de visualisation des données", "utiliser un logiciel danalyse de données spécifique"],
    "data": ["analyse de données", "exploration de données"],
    "data analysis": ["analyse de données", "exploration de données"],
    "data analyst": ["analyse de données"],
    "analyst": ["analyse de données"],
    "analyse": ["analyse de données"],
    # Machine learning - ESCO has "apprentissage automatique"
    "machine_learning": ["apprentissage automatique"],
    "tensorflow": ["tensorflow"],
    # Finance
    "financial_modeling": ["analyse financière", "effectuer une analyse financière de stratégies de prix"],
    "financial modeling": ["analyse financière", "effectuer une analyse financière de stratégies de prix"],
    "modélisation financière": ["analyse financière"],
    "financier": ["analyse financière"],
    "accounting": ["comptabilité"],
    # Communication/soft skills
    "communication": ["communication"],
    "leadership": ["leadership"],
    "teamwork": ["travail en équipe"],
    "travail en équipe": ["travail en équipe"],
    # Design
    "ux_design": ["concevoir une interface utilisateur", "créer un prototype de solution en matière dexpérience utilisateur", "schéma de conception dinterface utilisateur"],
    "figma": ["figma"],
    # Other tech
    "django": ["django"],
    "wordpress": ["wordpress"],
    "html": ["html"],
    "css": ["css"],
    "design": ["mettre en œuvre le design front end dun site web", "schéma de conception dinterface utilisateur"],
    "figma": ["schéma de conception dinterface utilisateur"],
    # Marketing / digital
    "marketing": ["analyse marketing"],
    "marketing digital": ["techniques de marketing numérique"],
    "marketing_digital": ["techniques de marketing numérique"],
    "google_analytics": ["utiliser un logiciel danalyse de données spécifique"],
    "google analytics": ["utiliser un logiciel danalyse de données spécifique"],
    # ERP / SAP
    "erp": ["gérer le système normalisé de planification des ressources dune entreprise"],
    # Supply chain
    "supply_chain": ["gestion de la chaîne logistique"],
    # ── Corpus BF — batch 1 (2026-04-18) ─────────────────────────────────────
    # Data science / analytics
    "data science": ["science des big data"],
    "big data": ["science des big data", "analyser des mégadonnées"],
    "machine learning": ["apprentissage automatique"],  # space variant of machine_learning
    "statistics": ["statistiques"],
    "statistiques": ["statistiques"],
    "dashboards": ["logiciel de visualisation des données"],
    # Marketing digital / content
    "evenementiel": ["mener à bien la gestion d'événements"],
    "relations presse": ["relations publiques"],
    "social media": ["gestion des réseaux sociaux", "techniques de marketing des médias sociaux"],
    "reseaux sociaux": ["gestion des réseaux sociaux", "techniques de marketing des médias sociaux"],
    "medias sociaux": ["gestion des réseaux sociaux", "techniques de marketing des médias sociaux"],
    # HR
    "recrutement": ["recruter du personnel"],
    "ressources humaines": ["gérer les ressources humaines"],
    "gestion des talents": ["stratégies de gestion des talents"],
    # Supply / logistics
    "logistique": ["gérer la chaîne logistique"],
    "gestion des stocks": ["règles de gestion des stocks"],
    # Finance
    "banque": ["activités bancaires"],
    "banking": ["activités bancaires"],
    "vba": ["Visual Basic"],
    # Sales
    "prospection": ["méthodes de prospection"],
    # Engineering (high-signal, verified ESCO)
    "mecanique": ["mécanique"],
    "genie industriel": ["génie industriel"],
}


def _expand_aliases(tokens: Set[str]) -> Set[str]:
    """Expand tokens using skill aliases to improve ESCO matching."""
    expanded = set(tokens)
    for token in tokens:
        token_lower = token.lower()
        if token_lower in SKILL_ALIASES:
            expanded.update(SKILL_ALIASES[token_lower])
    return expanded


# Common stopwords to filter out (French + English)
STOPWORDS = {
    # French articles/prepositions
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "à", "au", "aux",
    "en", "pour", "par", "sur", "dans", "avec", "sans", "nous", "vous", "ils",
    "notre", "votre", "leur", "ce", "cette", "ces", "son", "sa", "ses",
    "est", "sont", "être", "avoir", "faire", "très", "plus", "moins",
    # French job description noise
    "chez", "tant", "que", "mois", "mission", "vie", "poste", "profil", "candidat",
    "entreprise", "equipe", "sein", "cadre", "contrat", "cdi", "cdd", "stage",
    # English
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "as", "at", "by", "from", "is", "are", "be", "was", "were", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "this", "that",
    "these", "those", "your", "our", "their", "its", "his", "her", "my",
    # Common filler words
    "requis", "required", "souhaité", "preferred", "etc", "niveau", "level",
    "ans", "years", "experience", "expérience", "minimum", "maximum",
    # Sprint4-N1: geographic homonym with ESCO concept 'paris' (wager)
    "paris",
}

# Minimum token length
MIN_TOKEN_LENGTH = 2

# Regex patterns for splitting
SPLIT_PATTERN = re.compile(r"[,;/|•\-–—\n\t()[\]{}]+")
WHITESPACE_PATTERN = re.compile(r"\s+")
PUNCT_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)

# Always-capture obvious skills
WHITELIST_SKILLS = {
    "python",
    "excel",
    "react",
    "javascript",
    "sql",
    "aws",
    "sap",
}

# Controlled bigrams — normalized (accent-stripped, lowercase) forms only
BIGRAM_WHITELIST = {
    "data analysis",
    "project management",
    # Corpus BF batch 1 (2026-04-18)
    "data science",
    "big data",
    "machine learning",
    "social media",
    "reseaux sociaux",
    "medias sociaux",
    "ressources humaines",
    "genie industriel",
    "relations presse",
}

# Controlled trigrams — same normalization rules as bigrams
TRIGRAM_WHITELIST = {
    "gestion des talents",
    "gestion des stocks",
}


def _strip_accents(text: str) -> str:
    """Remove accents for normalization."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_text(text: str) -> str:
    """Normalize full text: lowercase, strip accents, punctuation -> spaces."""
    if not text:
        return ""
    text = _strip_accents(text.lower())
    text = PUNCT_PATTERN.sub(" ", text)
    text = WHITESPACE_PATTERN.sub(" ", text).strip()
    return text


def _split_text(text: str) -> List[str]:
    """Split text into candidate tokens without sub-phrase generation."""
    if not text:
        return []

    normalized = _normalize_text(text)
    if not normalized:
        return []

    tokens: List[str] = []
    words = [w for w in normalized.split(" ") if w]

    for word in words:
        if len(word) < MIN_TOKEN_LENGTH:
            continue
        if word in STOPWORDS:
            continue
        if word.isdigit():
            continue
        tokens.append(word)

    # Controlled bigrams
    if BIGRAM_WHITELIST and len(words) >= 2:
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i + 1]}"
            if phrase in BIGRAM_WHITELIST:
                tokens.append(phrase)

    # Controlled trigrams
    if TRIGRAM_WHITELIST and len(words) >= 3:
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i + 1]} {words[i + 2]}"
            if phrase in TRIGRAM_WHITELIST:
                tokens.append(phrase)

    # Whitelist capture (if present in text)
    for skill in WHITELIST_SKILLS:
        if re.search(rf"\\b{re.escape(skill)}\\b", normalized):
            tokens.append(skill)

    return tokens


def _extract_from_text(text: str) -> List[str]:
    """Extract skill candidates from free text."""
    if not text:
        return []

    return _split_text(text)


def _extract_from_list(items: List[Any]) -> List[str]:
    """Extract skill candidates from a list of items."""
    tokens = []
    for item in items:
        if isinstance(item, str):
            tokens.extend(_split_text(item))
        elif isinstance(item, dict):
            for key in ("name", "label", "skill", "competence", "raw_text"):
                if key in item and item[key]:
                    value = str(item[key])
                    tokens.extend(_split_text(value))
    return tokens


def extract_raw_skills_from_offer(offer: Dict[str, Any]) -> List[str]:
    """
    Extract raw skill strings from an offer using multiple fields.

    Fields used:
    - title
    - description
    - skills_required / skills / competences
    - tags

    Returns:
        List of deduplicated skill candidate strings
    """
    tokens: Set[str] = set()

    # Extract from title
    if "title" in offer and offer["title"]:
        tokens.update(_extract_from_text(str(offer["title"])))

    # Extract from description
    if "description" in offer and offer["description"]:
        tokens.update(_extract_from_text(str(offer["description"])))

    # Extract from skills_required (list)
    if "skills_required" in offer:
        tokens.update(_extract_from_list(offer["skills_required"]))

    # Extract from skills (list)
    if "skills" in offer:
        tokens.update(_extract_from_list(offer["skills"]))

    # Extract from competences (list of dicts or strings)
    if "competences" in offer:
        tokens.update(_extract_from_list(offer["competences"]))

    # Extract from tags
    if "tags" in offer:
        tokens.update(_extract_from_list(offer["tags"]))

    # Expand aliases to improve ESCO matching
    tokens = _expand_aliases(tokens)

    # Remove stopwords and return sorted for determinism
    result = [t for t in tokens if t not in STOPWORDS and len(t) >= MIN_TOKEN_LENGTH]
    return sorted(set(result))


def extract_raw_skills_from_profile(profile: Dict[str, Any]) -> List[str]:
    """
    Extract raw skill strings from a profile using multiple fields.

    Fields used:
    - skills
    - capabilities
    - detected_tools
    - unmapped_skills
    - cv_text

    Returns:
        List of deduplicated skill candidate strings
    """
    tokens: Set[str] = set()

    # Extract from skills (list)
    if "skills" in profile:
        tokens.update(_extract_from_list(profile["skills"]))

    # Extract from capabilities (list of dicts)
    if "capabilities" in profile:
        tokens.update(_extract_from_list(profile["capabilities"]))

    # Extract from detected_tools (list)
    if "detected_tools" in profile:
        tokens.update(_extract_from_list(profile["detected_tools"]))

    # Extract from unmapped_skills (list of dicts with raw_text)
    if "unmapped_skills" in profile:
        tokens.update(_extract_from_list(profile["unmapped_skills"]))

    # Extract from cv_text (free text)
    if "cv_text" in profile and profile["cv_text"]:
        tokens.update(_extract_from_text(str(profile["cv_text"])))

    # Expand aliases to improve ESCO matching
    tokens = _expand_aliases(tokens)

    # Remove stopwords and return sorted for determinism
    result = [t for t in tokens if t not in STOPWORDS and len(t) >= MIN_TOKEN_LENGTH]
    return sorted(set(result))
