from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[4]
ACTION_VERBS_PATH = REPO_ROOT / "data" / "action_verbs.json"

TOOL_TERMS = {
    "excel", "power bi", "powerbi", "sql", "python", "sap", "tableau", "etl", "crm", "salesforce",
    "hubspot", "canva", "wordpress", "mailchimp", "pack office", "google analytics", "jira", "erp",
    "dataiku", "figma", "git", "github", "rest api", "rest apis", "power query", "looker studio",
    "looker", "dbt", "airflow", "spark", "docker", "postgresql", "mysql", "mongodb",
    "photoshop", "illustrator", "premiere pro", "indesign", "adobe", "notion", "trello", "asana",
    "databricks", "kafka", "elasticsearch", "snowflake", "bigquery", "metabase", "streamlit",
    "pandas", "scikit-learn", "tensorflow", "pytorch", "matlab", "vba",
}
LANGUAGE_TERMS = {
    "anglais": "Anglais professionnel",
    "english": "Anglais professionnel",
    "francais": "Français",
    "français": "Français",
    "allemand": "Allemand",
    "german": "Allemand",
    "espagnol": "Espagnol",
    "spanish": "Espagnol",
}
SECTOR_KEYWORDS = {
    "finance": {"finance", "budget", "comptabilite", "comptabilité", "controlling", "cash", "audit", "reporting"},
    "business": {"business", "sales", "vente", "prospection", "crm", "negociation", "négociation", "portefeuille", "client"},
    "operations": {"operations", "supply", "logistique", "transport", "stock", "planification", "coordination", "approvisionnement"},
    "data": {"data", "analytics", "analyse", "sql", "python", "bi", "dashboard", "etl", "reporting"},
    "hr": {"recrutement", "talent", "rh", "ressources humaines", "onboarding", "paie", "sirh"},
    "marketing": {"marketing", "communication", "campaign", "campagne", "newsletter", "contenu", "seo", "social"},
}
ISSUE_KEYWORDS = {
    "fiabiliser le reporting": {"reporting", "tableau de bord", "kpi", "indicateur"},
    "structurer l'analyse": {"analyse", "diagnostic", "forecast", "prevision", "prévision", "modelisation", "modélisation"},
    "coordonner les parties prenantes": {"coordination", "stakeholder", "equipes", "équipes", "transverse"},
    "optimiser les processus": {"optimisation", "amelioration", "amélioration", "process", "efficacite", "efficacité"},
    "soutenir la decision": {"decision", "prise de decision", "pilotage", "business partner"},
}
VERB_FAMILIES = {
    "finance": {
        "analyse": {"analyse", "reporting", "data", "kpi", "forecast", "ecart", "écart", "performance"},
        "gestion": {"budget", "cash", "facture", "consolidation", "closing", "compta", "finance"},
        "pilotage": {"pilotage", "suivi", "controle", "contrôle", "tableau de bord", "coordination"},
    },
    "business": {
        "developpement": {"business", "vente", "prospection", "developpement", "développement", "client", "portefeuille"},
        "negociation": {"negociation", "négociation", "closing", "offre", "deal", "partenariat"},
        "analyse": {"qualification", "reporting", "pipeline", "besoin"},
    },
    "operations": {
        "organisation": {"coordination", "planification", "transport", "logistique", "flux", "stock"},
        "execution": {"execution", "exploitation", "operation", "opération", "approvisionnement"},
        "pilotage": {"suivi", "kpi", "reporting", "qualite", "qualité"},
    },
    "data": {
        "analyse": {"data", "analyse", "sql", "python", "modele", "modèle", "forecast", "segmentation"},
        "reporting": {"reporting", "dashboard", "tableau de bord", "power bi", "bi"},
        "qualite": {"qualite", "qualité", "nettoyage", "fiabilisation", "etl"},
    },
    "hr": {
        "recrutement": {"recrutement", "sourcing", "candidat", "entretien", "onboarding"},
        "gestion": {"administration", "paie", "sirh", "accompagnement", "talent"},
    },
    "marketing": {
        "analyse": {"reporting", "analytics", "performance", "campagne", "seo"},
        "contenu": {"contenu", "newsletter", "redaction", "rédaction", "editorial"},
        "pilotage": {"coordination", "planification", "diffusion", "communication"},
    },
}
GENERIC_VERBS = {"faire", "travailler", "participer", "aider", "assister"}

# ESCO occupation descriptions always start with an infinitive verb (≥ 3 words).
# Used to strip paraphrase-style entries from candidate-facing skill lists.
_ESCO_VERB_RE = re.compile(
    r"^(?:conseiller|g[eé]rer|analyser|coordonner|r[eé]aliser|mettre|assurer|"
    r"participer|contribuer|d[eé]velopper|travailler|effectuer|[eé]tablir|identifier|"
    r"planifier|pr[eé]parer|superviser|organiser|accompagner|[eé]valuer)\b",
    re.IGNORECASE,
)

_SECTOR_LABELS: dict[str, str] = {
    "finance": "finance et contrôle de gestion",
    "data": "data et analyse",
    "business": "développement commercial",
    "operations": "opérations et supply chain",
    "hr": "ressources humaines",
    "marketing": "marketing et communication",
}

STOPWORDS = {
    "the", "and", "with", "pour", "avec", "dans", "des", "les", "une", "sur", "from", "that",
    "this", "vos", "notre", "votre", "son", "ses", "leur", "leurs", "mission", "poste", "profil",
}
AUTONOMY_HIGH = {"piloter", "manager", "coordonner", "superviser", "responsable", "owner", "lead"}
AUTONOMY_MED = {"analyser", "structurer", "optimiser", "suivre", "controler", "contrôler", "realiser", "réaliser"}

# Nominalization → infinitive conversion map.
# Converts leading noun forms in responsibilities to cleaner infinitive bullets.
# Order matters: longer patterns (mise en place) before shorter ones.
_NOMINALIZATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^mise\s+en\s+place\s+", re.IGNORECASE), "Mettre en place "),
    (re.compile(r"^mise\s+en\s+[oœ]euvre\s+", re.IGNORECASE), "Mettre en œuvre "),
    (re.compile(r"^analyse\s+", re.IGNORECASE), "Analyser "),
    (re.compile(r"^gestion\s+", re.IGNORECASE), "Gérer "),
    (re.compile(r"^pilotage\s+", re.IGNORECASE), "Piloter "),
    (re.compile(r"^suivi\s+", re.IGNORECASE), "Assurer le suivi "),
    (re.compile(r"^coordination\s+", re.IGNORECASE), "Coordonner "),
    (re.compile(r"^collaboration\s+", re.IGNORECASE), "Collaborer "),
    (re.compile(r"^d[eé]veloppement\s+", re.IGNORECASE), "Développer "),
    (re.compile(r"^r[eé]daction\s+", re.IGNORECASE), "Rédiger "),
    (re.compile(r"^production\s+", re.IGNORECASE), "Produire "),
    (re.compile(r"^cr[eé]ation\s+", re.IGNORECASE), "Créer "),
    (re.compile(r"^identification\s+", re.IGNORECASE), "Identifier "),
    (re.compile(r"^[eé]laboration\s+", re.IGNORECASE), "Élaborer "),
    (re.compile(r"^d[eé]ploiement\s+", re.IGNORECASE), "Déployer "),
    (re.compile(r"^optimisation\s+", re.IGNORECASE), "Optimiser "),
    (re.compile(r"^automatisation\s+", re.IGNORECASE), "Automatiser "),
    (re.compile(r"^animation\s+", re.IGNORECASE), "Animer "),
    (re.compile(r"^accompagnement\s+", re.IGNORECASE), "Accompagner "),
    (re.compile(r"^construction\s+", re.IGNORECASE), "Construire "),
    (re.compile(r"^conception\s+", re.IGNORECASE), "Concevoir "),
    (re.compile(r"^participation\s+", re.IGNORECASE), "Participer "),
    (re.compile(r"^contribution\s+", re.IGNORECASE), "Contribuer "),
    (re.compile(r"^d[eé]finition\s+", re.IGNORECASE), "Définir "),
    (re.compile(r"^structuration\s+", re.IGNORECASE), "Structurer "),
    (re.compile(r"^pr[eé]paration\s+", re.IGNORECASE), "Préparer "),
    (re.compile(r"^reporting\s+", re.IGNORECASE), "Produire "),
    (re.compile(r"^veille\s+", re.IGNORECASE), "Assurer une veille "),
    (re.compile(r"^support\s+", re.IGNORECASE), "Apporter un support "),
    (re.compile(r"^s[ée]lection\s+", re.IGNORECASE), "Sélectionner "),
    (re.compile(r"^int[eé]gration\s+", re.IGNORECASE), "Intégrer "),
    (re.compile(r"^formation\s+", re.IGNORECASE), "Former "),
    (re.compile(r"^supervision\s+", re.IGNORECASE), "Superviser "),
    (re.compile(r"^validation\s+", re.IGNORECASE), "Valider "),
    (re.compile(r"^animation\s+", re.IGNORECASE), "Animer "),
    (re.compile(r"^n[eé]gociation\s+", re.IGNORECASE), "Négocier "),
]


def _to_infinitive(text: str) -> tuple[str, bool]:
    """
    Convert a leading nominal form to its infinitive equivalent.
    Returns (converted_text, was_converted).
    Preserves the article/preposition that follows.
    """
    for pattern, replacement in _NOMINALIZATION_PATTERNS:
        m = pattern.match(text)
        if m:
            suffix = text[m.end():]
            return (replacement + suffix).strip(), True
    return text, False


@dataclass
class ParsedOffer:
    job_title: str
    core_skills: list[str]
    tools: list[str]
    languages: list[str]
    sector: str
    top_issues: list[str]
    normalized_title_tokens: list[str]


@dataclass
class NormalizedExperience:
    role: str
    company: str
    dates: str
    bullets: list[str]
    text: str
    order_index: int


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    cleaned = _strip_accents(str(text or "")).lower()
    cleaned = re.sub(r"[^a-z0-9%€$+/\-\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize(text: str) -> list[str]:
    return [token for token in _normalize(text).split() if len(token) > 1 and token not in STOPWORDS]


def _dedupe(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        key = _normalize(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(raw)
        if limit is not None and len(out) >= limit:
            break
    return out


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    return [part.strip(" -•\t") for part in re.split(r"[\n;•]+|(?<=[.!?])\s+", text) if part.strip(" -•\t")]


def _load_action_verbs() -> dict[str, dict[str, list[str]]]:
    return json.loads(ACTION_VERBS_PATH.read_text(encoding="utf-8"))


def _clean_job_title(title: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", title or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -|,")
    return cleaned or "Poste visé"


def _extract_tools(text: str, skills: Iterable[str]) -> list[str]:
    haystack = _normalize(text)
    explicit = []
    for skill in skills:
        if _normalize(skill) in TOOL_TERMS:
            explicit.append(skill)
    for term in TOOL_TERMS:
        if term in haystack:
            explicit.append(term.upper() if term in {"sql", "etl", "crm", "sap", "bi"} else term.title())
    return _dedupe(explicit, limit=8)


def _extract_languages(text: str, skills: Iterable[str]) -> list[str]:
    values = []
    haystack = _normalize(text)
    for skill in skills:
        mapped = LANGUAGE_TERMS.get(_normalize(skill))
        if mapped:
            values.append(mapped)
    for raw, label in LANGUAGE_TERMS.items():
        if raw in haystack:
            values.append(label)
    return _dedupe(values, limit=3)


def _infer_sector(title: str, text: str, skills: Iterable[str]) -> str:
    counts: dict[str, int] = {sector: 0 for sector in SECTOR_KEYWORDS}
    haystack = set(_tokenize(f"{title} {text} {' '.join(skills)}"))
    title_norm = _normalize(title)
    skill_norm = [_normalize(skill) for skill in skills]
    if any(marker in title_norm for marker in ("controleur", "contrôleur", "gestion", "finance", "comptable", "budget")):
        counts["finance"] += 6
    if any(marker in title_norm for marker in ("data", "bi", "analyst", "analytics")):
        counts["data"] += 6
    for sector, words in SECTOR_KEYWORDS.items():
        for word in words:
            normalized_word = _normalize(word)
            if normalized_word in title_norm:
                counts[sector] += 3
            if any(normalized_word in item for item in skill_norm):
                counts[sector] += 2
            if normalized_word in haystack or normalized_word in _normalize(text):
                counts[sector] += 1
    best = max(counts.items(), key=lambda item: (item[1], item[0]))
    return best[0] if best[1] > 0 else "operations"


def parse_offer(offer: dict[str, Any]) -> ParsedOffer:
    title = _clean_job_title(str(offer.get("title") or offer.get("job_title") or ""))
    description = str(offer.get("description") or "")
    raw_skills = [str(item) for item in (offer.get("skills") or []) if item]
    title_tokens = _tokenize(title)
    ats_keywords = [kw for kw in _dedupe(raw_skills + _split_sentences(description) + title_tokens, limit=30)]
    tools = _extract_tools(f"{title} {description}", raw_skills)
    languages = _extract_languages(f"{title} {description}", raw_skills)
    sector = _infer_sector(title, description, raw_skills)

    issue_hits: list[str] = []
    text_norm = _normalize(f"{title} {description}")
    for label, words in ISSUE_KEYWORDS.items():
        if any(_normalize(word) in text_norm for word in words):
            issue_hits.append(label)
    core_candidates = []
    for item in raw_skills + ats_keywords:
        key = _normalize(item)
        if not key or key in {_normalize(x) for x in tools} or key in {_normalize(x) for x in languages}:
            continue
        if key in TOOL_TERMS:
            continue
        if len(key) < 3:
            continue
        if any(char in item for char in ".!?:;"):
            continue
        if len(key.split()) > 5:
            continue
        core_candidates.append(item)
    core_skills = _dedupe(core_candidates, limit=8)
    if not core_skills:
        core_skills = _dedupe([word.title() for word in title_tokens], limit=5)

    return ParsedOffer(
        job_title=title,
        core_skills=core_skills,
        tools=tools,
        languages=languages,
        sector=sector,
        top_issues=_dedupe(issue_hits, limit=4),
        normalized_title_tokens=title_tokens,
    )


def _normalize_experience(exp: Any, index: int) -> NormalizedExperience | None:
    if isinstance(exp, str):
        text = exp.strip()
        if not text:
            return None
        return NormalizedExperience(role=f"Expérience {index + 1}", company="", dates="", bullets=_split_sentences(text), text=text, order_index=index)
    if not isinstance(exp, dict):
        return None
    role = str(exp.get("title") or exp.get("role") or exp.get("position") or f"Expérience {index + 1}").strip()
    company = str(exp.get("company") or exp.get("entreprise") or exp.get("employer") or "").strip()
    dates = str(exp.get("dates") or exp.get("duration") or exp.get("period") or exp.get("date") or "").strip()
    raw_parts: list[str] = []
    bullet_values: list[str] = []
    for key in ("bullets", "responsibilities", "highlights", "tasks", "missions", "achievements", "actions", "results"):
        value = exp.get(key)
        if isinstance(value, list):
            bullet_values.extend(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str):
            bullet_values.extend(_split_sentences(value))
    for key in ("description", "summary", "context", "impact", "details"):
        value = exp.get(key)
        if isinstance(value, str) and value.strip():
            raw_parts.append(value.strip())
    if isinstance(exp.get("metrics"), list):
        raw_parts.extend(str(item).strip() for item in exp["metrics"] if str(item).strip())
    text = " ".join([role, company, dates, *raw_parts, *bullet_values]).strip()
    bullets = _dedupe(bullet_values or _split_sentences(" ".join(raw_parts)), limit=6)
    return NormalizedExperience(role=role, company=company, dates=dates, bullets=bullets, text=text, order_index=index)


def _collect_profile_skills(profile: dict[str, Any]) -> list[str]:
    """
    Collect skills from all available sources in the profile:
    1. profile["skills"] — raw skills from ESCO pipeline (primary source)
    2. career_profile.selected_skills[*].label — controlled profile enrichments
    3. career_profile.experiences[*].tools — tools found in each experience
    4. career_profile.experiences[*].skills — short keyword phrases from structurer / enrichment
    Deduplicated, capped at 30.
    """
    base: list[str] = []
    skills = profile.get("skills") or profile.get("matching_skills") or []
    if isinstance(skills, str):
        base.extend(_split_sentences(skills))
    elif isinstance(skills, list):
        base.extend(str(item) for item in skills if item)

    # Also pull experience-level tools and skills from career profile
    career = profile.get("career_profile") or {}
    for item in (career.get("selected_skills") or []):
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            if label:
                base.append(label)
        elif isinstance(item, str) and item.strip():
            base.append(item.strip())
    for exp in (career.get("experiences") or []):
        if not isinstance(exp, dict):
            continue
        for t in (exp.get("tools") or []):
            if isinstance(t, str) and t.strip():
                base.append(t.strip())
        for s in (exp.get("skills") or []):
            if isinstance(s, str) and s.strip() and len(s.split()) <= 4:
                base.append(s.strip())

    return _dedupe(base, limit=30)


def _education_items(profile: dict[str, Any]) -> list[str]:
    education = profile.get("education") or profile.get("education_history") or []
    items: list[str] = []
    if isinstance(education, str):
        items.extend(_split_sentences(education))
    elif isinstance(education, list):
        for entry in education:
            if isinstance(entry, str):
                items.append(entry)
            elif isinstance(entry, dict):
                degree = str(entry.get("degree") or entry.get("title") or entry.get("label") or "Formation").strip()
                school = str(entry.get("school") or entry.get("institution") or "").strip()
                items.append(f"{degree} — {school}" if school else degree)
    return _dedupe(items, limit=5)


def _overlap_ratio(haystack: str, targets: Iterable[str]) -> tuple[float, list[str]]:
    tokens = set(_tokenize(haystack))
    target_list = [item for item in (_normalize(target) for target in targets) if item]
    matched = []
    for target in target_list:
        target_tokens = set(target.split())
        if target_tokens and target_tokens <= tokens:
            matched.append(target)
        elif target in _normalize(haystack):
            matched.append(target)
    if not target_list:
        return 0.0, []
    ratio = min(1.0, len(set(matched)) / max(1, min(len(target_list), 4)))
    return ratio, _dedupe(matched, limit=6)


def _quantified_evidence(text: str) -> float:
    hits = re.findall(r"\b\d+[\d\s.,%€$kKmM]*\b", text)
    if not hits:
        return 0.0
    return min(1.0, len(hits) / 2)


def _sector_similarity(text: str, sector: str) -> float:
    words = SECTOR_KEYWORDS.get(sector, set())
    if not words:
        return 0.0
    text_norm = _normalize(text)
    hits = sum(1 for word in words if _normalize(word) in text_norm)
    return min(1.0, hits / 3)


def _job_similarity(role: str, offer_title_tokens: list[str]) -> float:
    role_tokens = set(_tokenize(role))
    if not role_tokens or not offer_title_tokens:
        return 0.0
    overlap = role_tokens & set(offer_title_tokens)
    return min(1.0, len(overlap) / max(1, min(len(offer_title_tokens), 3)))


def _parse_years(text: str) -> list[int]:
    years = []
    for match in re.findall(r"\b(20\d{2}|19\d{2})\b", text):
        try:
            years.append(int(match))
        except ValueError:
            continue
    return years


def _recency_score(exp: NormalizedExperience, total: int) -> float:
    years = _parse_years(exp.dates or exp.text)
    if years:
        latest = max(years)
        age = max(0, 2026 - latest)
        return max(0.1, 1 - age * 0.15)
    if total <= 1:
        return 1.0
    return max(0.2, 1 - (exp.order_index / max(total - 1, 1)) * 0.6)


def _autonomy_score(text: str) -> float:
    tokens = set(_tokenize(text))
    if tokens & {_normalize(t) for t in AUTONOMY_HIGH}:
        return 1.0
    if tokens & {_normalize(t) for t in AUTONOMY_MED}:
        return 0.6
    return 0.2


def score_experiences(profile: dict[str, Any], parsed_offer: ParsedOffer) -> list[dict[str, Any]]:
    normalized = [item for idx, exp in enumerate(profile.get("experiences") or []) if (item := _normalize_experience(exp, idx))]
    total = len(normalized)
    if total == 0:
        return []
    target_terms = parsed_offer.core_skills + parsed_offer.tools + parsed_offer.languages + parsed_offer.top_issues
    scored: list[dict[str, Any]] = []
    for exp in normalized:
        skill_match, matched_terms = _overlap_ratio(exp.text, target_terms)
        score = {
            "skill_match": skill_match,
            "job_similarity": _job_similarity(exp.role, parsed_offer.normalized_title_tokens),
            "quantified_evidence": _quantified_evidence(exp.text),
            "sector_similarity": _sector_similarity(exp.text, parsed_offer.sector),
            "recency": _recency_score(exp, total),
            "autonomy": _autonomy_score(exp.text),
        }
        total_score = (
            0.35 * score["skill_match"] +
            0.20 * score["job_similarity"] +
            0.15 * score["quantified_evidence"] +
            0.10 * score["sector_similarity"] +
            0.10 * score["recency"] +
            0.10 * score["autonomy"]
        )
        scored.append({
            "experience": exp,
            "score": round(total_score, 4),
            **score,
            "matched_terms": matched_terms,
        })
    scored.sort(key=lambda item: (-item["score"], item["experience"].order_index, item["experience"].role.lower()))
    for idx, item in enumerate(scored):
        if idx < 3 and item["score"] >= 0.28:
            decision = "keep"
        elif idx < 5 and item["score"] >= 0.4:
            decision = "keep"
        elif item["score"] >= 0.16:
            decision = "compress"
        else:
            decision = "drop"
        item["decision"] = decision
        item["reasons"] = _dedupe(item["matched_terms"] + ([parsed_offer.sector] if item["sector_similarity"] else []), limit=4)
    return scored


_AUTONOMY_EXPLICIT = {"LEAD": 1.0, "COPILOT": 0.6, "CONTRIB": 0.2}


def score_career_experiences(profile: dict[str, Any], parsed_offer: ParsedOffer) -> list[dict[str, Any]]:
    """
    Like score_experiences() but uses explicit autonomy from CareerProfile.
    Reads profile["experiences"] enriched by to_experience_dicts() (has "autonomy" field).
    Falls back to score_experiences() if no career-profile experiences present.
    """
    experiences_raw = profile.get("experiences") or []
    # Detect career-profile format: has string autonomy LEAD/COPILOT/CONTRIB
    has_career_autonomy = any(
        isinstance(exp, dict) and exp.get("autonomy") in _AUTONOMY_EXPLICIT
        for exp in experiences_raw
    )
    if not has_career_autonomy:
        return score_experiences(profile, parsed_offer)

    normalized = [item for idx, exp in enumerate(experiences_raw) if (item := _normalize_experience(exp, idx))]
    total = len(normalized)
    if total == 0:
        return []

    target_terms = parsed_offer.core_skills + parsed_offer.tools + parsed_offer.languages + parsed_offer.top_issues
    scored: list[dict[str, Any]] = []
    for idx, exp in enumerate(normalized):
        raw_exp = experiences_raw[idx] if idx < len(experiences_raw) else {}
        autonomy_str = str(raw_exp.get("autonomy") or "COPILOT").upper() if isinstance(raw_exp, dict) else "COPILOT"
        autonomy_val = _AUTONOMY_EXPLICIT.get(autonomy_str, 0.6)

        skill_match, matched_terms = _overlap_ratio(exp.text, target_terms)
        score = {
            "skill_match": skill_match,
            "job_similarity": _job_similarity(exp.role, parsed_offer.normalized_title_tokens),
            "quantified_evidence": _quantified_evidence(exp.text),
            "sector_similarity": _sector_similarity(exp.text, parsed_offer.sector),
            "recency": _recency_score(exp, total),
            "autonomy": autonomy_val,
        }
        total_score = (
            0.35 * score["skill_match"] +
            0.20 * score["job_similarity"] +
            0.15 * score["quantified_evidence"] +
            0.10 * score["sector_similarity"] +
            0.10 * score["recency"] +
            0.10 * score["autonomy"]
        )
        scored.append({
            "experience": exp,
            "score": round(total_score, 4),
            **score,
            "matched_terms": matched_terms,
        })

    scored.sort(key=lambda item: (-item["score"], item["experience"].order_index, item["experience"].role.lower()))
    for idx, item in enumerate(scored):
        if idx < 3 and item["score"] >= 0.28:
            decision = "keep"
        elif idx < 5 and item["score"] >= 0.4:
            decision = "keep"
        elif item["score"] >= 0.16:
            decision = "compress"
        else:
            decision = "drop"
        item["decision"] = decision
        item["reasons"] = _dedupe(item["matched_terms"] + ([parsed_offer.sector] if item["sector_similarity"] else []), limit=4)
    return scored


def _family_for_offer(parsed_offer: ParsedOffer, snippet: str) -> tuple[str, str]:
    domain = parsed_offer.sector if parsed_offer.sector in VERB_FAMILIES else "operations"
    snippet_norm = _normalize(f"{snippet} {' '.join(parsed_offer.core_skills)} {' '.join(parsed_offer.top_issues)}")
    families = VERB_FAMILIES.get(domain, {})
    best_family = next(iter(families.keys())) if families else "analyse"
    best_score = -1
    for family, words in families.items():
        hits = sum(1 for word in words if _normalize(word) in snippet_norm)
        if hits > best_score:
            best_family = family
            best_score = hits
    return domain, best_family


def _choose_verb(parsed_offer: ParsedOffer, snippet: str, bullet_index: int) -> tuple[str, dict[str, str]]:
    verbs = _load_action_verbs()
    domain, family = _family_for_offer(parsed_offer, snippet)
    family_verbs = verbs.get(domain, {}).get(family) or ["Structurer"]
    verb = family_verbs[bullet_index % len(family_verbs)]
    if _normalize(verb) in GENERIC_VERBS:
        verb = "Structurer"
    return verb, {"domain": domain, "family": family, "verb": verb}


def _best_fragments(exp: NormalizedExperience, parsed_offer: ParsedOffer) -> list[str]:
    fragments = exp.bullets or _split_sentences(exp.text)
    scored: list[tuple[int, int, str]] = []
    for frag in fragments:
        overlap = sum(1 for term in parsed_offer.core_skills + parsed_offer.tools + parsed_offer.top_issues if _normalize(term) in _normalize(frag))
        evidence = 1 if _quantified_evidence(frag) > 0 else 0
        scored.append((overlap, evidence, frag))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2].lower()))
    return [frag for _, _, frag in scored[:3] if frag.strip()]


def _extract_result_phrase(fragment: str) -> str | None:
    lowered = fragment.strip()
    for marker in ("permettant de", "afin de", "pour ", "ayant permis de", "to "):
        idx = lowered.lower().find(marker)
        if idx != -1:
            return lowered[idx:].strip(" ,.;")
    metrics = re.findall(r"\b\d+[\d\s.,%€$kKmM]*\b", fragment)
    if metrics:
        return f"avec un impact mesuré sur {metrics[0]}"
    return None


def _rewrite_fragment(fragment: str, verb: str, parsed_offer: ParsedOffer, exp: NormalizedExperience) -> str:
    cleaned = fragment.strip(" -•\t")
    cleaned = re.sub(r"^(j['e]?|nous|je|j ai|j'ai)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(participation a|participation à|participer a|participer à|suivi de|gestion de|analyse de)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned[0].lower() + cleaned[1:] if cleaned and cleaned[0].isupper() else cleaned
    result = _extract_result_phrase(cleaned)
    if result and result in cleaned:
        core = cleaned[: cleaned.lower().find(result.lower())].strip(" ,.;")
    else:
        core = cleaned.strip(" ,.;")
    if not core:
        target = parsed_offer.core_skills[0] if parsed_offer.core_skills else exp.role.lower()
        core = f"les sujets de {target}"
    bullet = f"{verb} {core}"
    if exp.company and exp.company.lower() not in bullet.lower():
        bullet += f" chez {exp.company}"
    if result and result.lower() not in bullet.lower():
        bullet += f", {result}"
    bullet = re.sub(r"\s+", " ", bullet).strip(" ,.;")
    return bullet + ("." if not bullet.endswith(".") else "")


def _rewrite_experience(item: dict[str, Any], parsed_offer: ParsedOffer) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    exp: NormalizedExperience = item["experience"]
    fragments = _best_fragments(exp, parsed_offer)
    selected_verbs: list[dict[str, str]] = []
    bullets: list[str] = []
    missing: list[str] = []
    for idx, fragment in enumerate(fragments[:2]):
        verb, debug = _choose_verb(parsed_offer, fragment, idx)
        bullet = _rewrite_fragment(fragment, verb, parsed_offer, exp)
        bullets.append(bullet)
        selected_verbs.append({
            "experience_role": exp.role,
            "source_fragment": fragment,
            **debug,
        })
        if _quantified_evidence(fragment) == 0 and "permettant de" not in fragment.lower() and "pour " not in fragment.lower():
            missing.append(f"preuve faible pour {exp.role}")
    if not bullets:
        target = parsed_offer.core_skills[0] if parsed_offer.core_skills else parsed_offer.job_title.lower()
        verb, debug = _choose_verb(parsed_offer, exp.text or exp.role, 0)
        bullets = [f"{verb} les sujets liés à {target} dans un contexte {parsed_offer.sector}." ]
        selected_verbs.append({"experience_role": exp.role, "source_fragment": exp.text or exp.role, **debug})
        missing.append(f"absence de bullet prouvable pour {exp.role}")
    tools = [skill for skill in parsed_offer.tools if _normalize(skill) in _normalize(exp.text)]
    return {
        "title": exp.role,
        "company": exp.company or "Entreprise",
        "dates": exp.dates or None,
        "bullets": _dedupe(bullets, limit=3),
        "tools": _dedupe(tools, limit=4),
        "impact": None,
        "autonomy": "LEAD" if item["autonomy"] >= 0.85 else "COPILOT" if item["autonomy"] >= 0.45 else "CONTRIB",
    }, selected_verbs, missing


def _sort_skills(profile_skills: list[str], parsed_offer: ParsedOffer, experience_scores: list[dict[str, Any]]) -> list[str]:
    target_terms = parsed_offer.core_skills + parsed_offer.tools + parsed_offer.languages
    matched = [skill for skill in profile_skills if any(_normalize(term) == _normalize(skill) or _normalize(term) in _normalize(skill) for term in target_terms)]
    supportive = [
        skill for skill in profile_skills
        if skill not in matched and (
            parsed_offer.sector in _normalize(skill) or
            any(_normalize(term) in _normalize(skill) for term in parsed_offer.top_issues) or
            any(_normalize(skill) in _normalize(reason) for score in experience_scores for reason in score.get("reasons", []))
        )
    ]
    fallback = [skill for skill in profile_skills if skill not in matched and skill not in supportive]
    return _dedupe(matched + supportive + fallback, limit=16)


# ── Career-profile adaptation engine (Block 2) ───────────────────────────────
#
# Works directly from career_profile.experiences (rich dicts with
# responsibilities[], achievements[], tools[]) rather than the normalized
# NormalizedExperience used by the legacy scorer.
#
# Public surface:
#   adapt_career_experiences(profile, offer) → list[AdaptedExperience]
#   score_projects(profile, offer)           → list[dict]
# Both are additive — never touch skills_uri or matching core.
# ─────────────────────────────────────────────────────────────────────────────

# Keyword injection: if an offer keyword appears in a bullet verbatim, keep it.
# If not, we try to append a context clause only when the bullet is thin (<8 words).
_THIN_BULLET_WORDS = 8
# Max bullets per experience in adapted output
_MAX_BULLETS_ADAPTED = 4
# Min score to include an experience as "keep" (vs "compress"/"drop")
_KEEP_THRESHOLD = 0.25
_COMPRESS_THRESHOLD = 0.12


@dataclass
class AdaptedExperience:
    title: str
    company: str
    location: str
    start_date: str
    end_date: str
    bullets: list[str]
    tools: list[str]
    autonomy: str
    score: float
    decision: str          # "keep" | "compress" | "drop"
    matched_keywords: list[str]
    debug_score: dict[str, float]


def _offer_target_terms(parsed_offer: ParsedOffer, offer: dict[str, Any]) -> list[str]:
    """
    Build the full list of target terms from:
    - parsed offer core_skills + tools + languages + top_issues
    - structured_v1 tools_stack + requirements + missions (if present)
    - cv_strategy.focus (if present)
    Deduplicated, lowercased.
    """
    terms: list[str] = list(parsed_offer.core_skills + parsed_offer.tools + parsed_offer.languages + parsed_offer.top_issues)
    structured = offer.get("structured_v1") or {}
    if isinstance(structured, dict):
        terms.extend(structured.get("tools_stack") or [])
        # requirements (was incorrectly "key_requirements" — fixed)
        # Add short requirement phrases (≤5 words) as whole terms; longer ones split
        for req in (structured.get("requirements") or [])[:6]:
            req_s = str(req).strip()
            if len(req_s.split()) <= 5:
                terms.append(req_s)
            else:
                # Only keep content words (>3 chars) from longer requirements
                terms.extend(w for w in req_s.split() if len(w) > 3)
        # missions: short phrases as whole term; context signal only
        for mission in (structured.get("missions") or [])[:4]:
            m_s = str(mission).strip()
            if len(m_s.split()) <= 5:
                terms.append(m_s)
    cv_strategy = offer.get("cv_strategy") or {}
    if isinstance(cv_strategy, dict):
        terms.extend(cv_strategy.get("focus") or [])
    return _dedupe(terms, limit=40)


def _score_single_career_exp(
    exp: dict[str, Any],
    parsed_offer: ParsedOffer,
    target_terms: list[str],
    exp_index: int,
    total_exps: int,
) -> dict[str, float]:
    """
    Score one career_profile experience dict.
    Returns a dict of dimension scores (all 0–1).
    """
    # Build a searchable text from all rich fields
    all_text_parts = [
        str(exp.get("title") or ""),
        str(exp.get("company") or ""),
        " ".join(str(r) for r in (exp.get("responsibilities") or [])),
        " ".join(str(a) for a in (exp.get("achievements") or [])),
        " ".join(str(t) for t in (exp.get("tools") or [])),
    ]
    full_text = " ".join(all_text_parts)

    # Skill match: what fraction of target terms appear in full_text
    skill_match, _ = _overlap_ratio(full_text, target_terms)

    # Tool overlap: career tools vs offer tools
    exp_tools_norm = {_normalize(t) for t in (exp.get("tools") or [])}
    offer_tools_norm = {_normalize(t) for t in parsed_offer.tools}
    tool_overlap = len(exp_tools_norm & offer_tools_norm) / max(1, len(offer_tools_norm)) if offer_tools_norm else 0.0

    # Job similarity: title vs offer title tokens
    job_sim = _job_similarity(str(exp.get("title") or ""), parsed_offer.normalized_title_tokens)

    # Evidence: quantified achievements
    ach_text = " ".join(str(a) for a in (exp.get("achievements") or []))
    evidence = min(1.0, _quantified_evidence(ach_text) + 0.3 * _quantified_evidence(full_text))

    # Sector similarity
    sector_sim = _sector_similarity(full_text, parsed_offer.sector)

    # Recency: use start/end_date from career_profile format
    start = str(exp.get("start_date") or exp.get("dates") or "")
    end = str(exp.get("end_date") or "")
    date_text = f"{start} {end}".strip()
    years = [int(y) for y in re.findall(r"\b(20\d{2}|19\d{2})\b", date_text)]
    if years:
        age = max(0, 2026 - max(years))
        recency = max(0.1, 1 - age * 0.12)
    elif total_exps <= 1:
        recency = 1.0
    else:
        recency = max(0.2, 1 - (exp_index / max(total_exps - 1, 1)) * 0.5)

    # Autonomy (explicit)
    autonomy_str = str(exp.get("autonomy") or "COPILOT").upper()
    autonomy = _AUTONOMY_EXPLICIT.get(autonomy_str, 0.6)

    return {
        "skill_match": round(skill_match, 4),
        "tool_overlap": round(min(1.0, tool_overlap), 4),
        "job_similarity": round(job_sim, 4),
        "evidence": round(min(1.0, evidence), 4),
        "sector_similarity": round(sector_sim, 4),
        "recency": round(recency, 4),
        "autonomy": round(autonomy, 4),
    }


def _total_score(dim: dict[str, float]) -> float:
    return round(
        0.30 * dim["skill_match"] +
        0.15 * dim["tool_overlap"] +
        0.15 * dim["job_similarity"] +
        0.15 * dim["evidence"] +
        0.10 * dim["sector_similarity"] +
        0.10 * dim["recency"] +
        0.05 * dim["autonomy"],
        4,
    )


def _select_and_rewrite_bullets(
    exp: dict[str, Any],
    parsed_offer: ParsedOffer,
    target_terms: list[str],
) -> tuple[list[str], list[str]]:
    """
    Select the best bullets from responsibilities + achievements and rewrite them.

    Strategy:
      1. Score each responsibility by keyword overlap with target_terms + evidence signal
      2. Keep top _MAX_BULLETS_ADAPTED responsibilities
      3. Inject up to 1 achievement (quantified result if available)
      4. For each kept responsibility:
         - if it already contains a target keyword → keep verbatim (just capitalise)
         - if it's thin (< _THIN_BULLET_WORDS words) → prepend action verb
         - otherwise → prepend action verb + trim redundant opener
      5. Return (bullets, matched_keywords_in_bullets)
    """
    target_norm = {_normalize(t) for t in target_terms}
    verbs = _load_action_verbs()
    domain = parsed_offer.sector if parsed_offer.sector in VERB_FAMILIES else "operations"
    families = VERB_FAMILIES.get(domain, {})

    def _verb_for(text: str, idx: int) -> str:
        text_norm = _normalize(text)
        # Pick verb family by keyword overlap
        best_family = next(iter(families.keys())) if families else "analyse"
        best_hits = -1
        for fam, words in families.items():
            hits = sum(1 for w in words if _normalize(w) in text_norm)
            if hits > best_hits:
                best_family = fam
                best_hits = hits
        family_verbs = verbs.get(domain, {}).get(best_family) or ["Structurer"]
        verb = family_verbs[idx % len(family_verbs)]
        return "Structurer" if _normalize(verb) in GENERIC_VERBS else verb

    def _clean(text: str) -> str:
        t = text.strip(" -•\t")
        # Strip first-person openers
        t = re.sub(r"^(j['e]?|nous|je|j'ai|j ai)\s+", "", t, flags=re.IGNORECASE)
        # Strip residual noise not caught by nominalization conversion
        t = re.sub(r"^(mission\s*:?)\s*", "", t, flags=re.IGNORECASE)
        return t.strip()

    def _keyword_overlap(text: str) -> int:
        tn = _normalize(text)
        return sum(1 for kw in target_norm if kw in tn)

    # Score responsibilities — supplement with structurer's short skill phrases when thin
    responsibilities = [str(r).strip() for r in (exp.get("responsibilities") or []) if str(r).strip()]
    achievements = [str(a).strip() for a in (exp.get("achievements") or []) if str(a).strip()]

    # When responsibilities are absent or all very short (<4 words), supplement with
    # the structurer's `skills` field (short keyword phrases extracted from bullets)
    if len(responsibilities) < 2 or all(len(r.split()) < 4 for r in responsibilities):
        structurer_skills = [str(s).strip() for s in (exp.get("skills") or []) if str(s).strip()]
        # Only add skills that aren't already a sub-phrase of an existing responsibility
        resp_norm = {_normalize(r) for r in responsibilities}
        for sk in structurer_skills:
            if not any(_normalize(sk) in rn or rn in _normalize(sk) for rn in resp_norm):
                responsibilities.append(sk)
                resp_norm.add(_normalize(sk))

    scored_resp: list[tuple[int, int, str]] = []
    for resp in responsibilities:
        kw_hits = _keyword_overlap(resp)
        evidence = 1 if _quantified_evidence(resp) > 0 else 0
        scored_resp.append((kw_hits, evidence, resp))
    scored_resp.sort(key=lambda x: (-x[0], -x[1], x[2].lower()))

    # Best responsibilities (max _MAX_BULLETS_ADAPTED - 1 to leave room for achievement)
    top_resp = [r for _, _, r in scored_resp[:_MAX_BULLETS_ADAPTED - 1]]

    # Best achievement: quantified first, then qualitative (≥6 words with an impact signal)
    _IMPACT_SIGNAL_RE = re.compile(
        r"\b(permettant|r[eé]sultant|contribuant|am[eé]liorant|r[eé]duisant|augmentant"
        r"|g[eé]n[eé]rant|optimisant|accélérant|assurant|garantissant|renforc[a-z]+)\b",
        re.IGNORECASE,
    )
    best_ach: str | None = None
    used_resp_norms = {_normalize(r) for r in top_resp}
    for ach in sorted(achievements, key=lambda a: -_quantified_evidence(a)):
        if ach and _normalize(ach) not in used_resp_norms:
            best_ach = ach
            break
    # If no explicit achievement, promote a long qualitative responsibility
    if best_ach is None:
        for r in responsibilities:
            r_norm = _normalize(r)
            if r_norm in used_resp_norms:
                continue
            if len(r.split()) >= 6 and (_quantified_evidence(r) > 0 or _IMPACT_SIGNAL_RE.search(r)):
                best_ach = r
                break

    # Rewrite
    bullets: list[str] = []
    matched_kw: list[str] = []
    for idx, resp in enumerate(top_resp):
        # Step 1: try nominalization conversion BEFORE cleaning
        verbified, was_verbified = _to_infinitive(resp.strip())
        cleaned = _clean(verbified if was_verbified else resp)
        if not cleaned:
            continue

        kw_in_resp = [t for t in target_terms if _normalize(t) in _normalize(cleaned) and len(t) > 2]
        matched_kw.extend(kw_in_resp)
        word_count = len(cleaned.split())

        # Detect if the bullet already starts with a French infinitive verb
        _first_word = cleaned.split()[0].lower() if cleaned else ""
        _already_infinitive = _first_word.endswith(("er", "ir", "re")) and len(_first_word) > 3

        if was_verbified or _already_infinitive:
            # Already a complete infinitive bullet — capitalise and use verbatim
            bullet = cleaned[0].upper() + cleaned[1:]
        elif kw_in_resp and word_count >= _THIN_BULLET_WORDS:
            # Keyword-rich and long enough — keep verbatim capitalised
            bullet = cleaned[0].upper() + cleaned[1:]
        else:
            # Generic: prepend action verb
            verb = _verb_for(cleaned, idx)
            body = cleaned[0].lower() + cleaned[1:] if cleaned else cleaned
            bullet = f"{verb} {body}"

        bullet = re.sub(r"\s+", " ", bullet).strip(" ,.;")
        if not bullet.endswith("."):
            bullet += "."
        bullets.append(bullet)

    # Append achievement as last bullet (→ Impact: ...)
    if best_ach:
        ach_clean = _clean(best_ach)
        if ach_clean:
            bullets.append(f"→ {ach_clean[0].upper() + ach_clean[1:]}.")

    # Deduplicate and cap
    final_bullets = _dedupe(bullets, limit=_MAX_BULLETS_ADAPTED)
    matched_kw = _dedupe(matched_kw, limit=6)
    return final_bullets, matched_kw


def adapt_career_experiences(
    profile: dict[str, Any],
    offer: dict[str, Any],
    *,
    max_keep: int = 4,
) -> list[AdaptedExperience]:
    """
    Score and adapt career_profile.experiences for the given offer.

    Returns a list of AdaptedExperience sorted by relevance score (desc).
    decision: "keep" (shown fully) | "compress" (show title only) | "drop" (excluded).
    Falls back to an empty list if career_profile is absent.

    Never touches skills_uri or any matching core data structure.
    """
    career = profile.get("career_profile") or {}
    career_exps = career.get("experiences") or []
    if not career_exps:
        return []

    parsed_offer = parse_offer(offer)
    target_terms = _offer_target_terms(parsed_offer, offer)
    total = len(career_exps)

    results: list[AdaptedExperience] = []
    for idx, exp in enumerate(career_exps):
        if not isinstance(exp, dict):
            continue
        dim = _score_single_career_exp(exp, parsed_offer, target_terms, idx, total)
        score = _total_score(dim)

        bullets, matched_kw = _select_and_rewrite_bullets(exp, parsed_offer, target_terms)

        # Fallback bullet when experience is empty of content
        if not bullets:
            sector = parsed_offer.sector
            role = str(exp.get("title") or "ce poste")
            verbs = _load_action_verbs()
            domain = sector if sector in verbs else "operations"
            fam = next(iter(verbs.get(domain, {}).keys()), None)
            verb = (verbs.get(domain, {}).get(fam) or ["Structurer"])[0]
            bullets = [f"{verb} les sujets liés à {role} dans un contexte {sector}."]

        results.append(AdaptedExperience(
            title=str(exp.get("title") or "Expérience"),
            company=str(exp.get("company") or ""),
            location=str(exp.get("location") or ""),
            start_date=str(exp.get("start_date") or ""),
            end_date=str(exp.get("end_date") or ""),
            bullets=bullets,
            tools=_dedupe(str(t) for t in (exp.get("tools") or []) if str(t).strip()),
            autonomy=str(exp.get("autonomy") or "COPILOT"),
            score=score,
            decision="keep",   # set below
            matched_keywords=matched_kw,
            debug_score=dim,
        ))

    results.sort(key=lambda e: (-e.score, results.index(e) if e in results else 0))

    # Assign decisions: top max_keep above threshold → keep; rest → compress/drop
    keep_count = 0
    for exp in results:
        if keep_count < max_keep and exp.score >= _KEEP_THRESHOLD:
            exp.decision = "keep"
            keep_count += 1
        elif exp.score >= _COMPRESS_THRESHOLD:
            exp.decision = "compress"
        else:
            exp.decision = "drop"

    return results


def score_projects(
    profile: dict[str, Any],
    offer: dict[str, Any],
    *,
    adapted_exps: "list[AdaptedExperience] | None" = None,
) -> list[dict[str, Any]]:
    """
    Score career_profile.projects against the offer.
    Returns projects sorted by relevance with decision: "show" | "hide".

    Relevance = technology overlap + title keyword match + impact signal.
    A project is "show" if score >= 0.20 AND adds tech not already in matched exp tools.

    adapted_exps: pre-computed adapt_career_experiences() result to avoid re-computation.
    """
    career = profile.get("career_profile") or {}
    projects = career.get("projects") or []
    if not projects:
        return []

    parsed_offer = parse_offer(offer)
    target_terms = _offer_target_terms(parsed_offer, offer)
    target_norm = {_normalize(t) for t in target_terms}

    # Tools already surfaced from adapted experiences (to avoid redundancy)
    if adapted_exps is None:
        adapted_exps = adapt_career_experiences(profile, offer, max_keep=4)
    covered_tools: set[str] = set()
    for exp in adapted_exps:
        if exp.decision == "keep":
            covered_tools.update(_normalize(t) for t in exp.tools)

    scored: list[dict[str, Any]] = []
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        title = str(proj.get("title") or "")
        if not title:
            continue

        techs = [str(t) for t in (proj.get("technologies") or []) if str(t).strip()]
        techs_norm = {_normalize(t) for t in techs}
        description = str(proj.get("description") or "")
        impact = str(proj.get("impact") or "")
        all_text = f"{title} {description} {impact} {' '.join(techs)}"

        # Tech overlap with offer
        tech_overlap = len(techs_norm & target_norm) / max(1, len(target_norm))
        # Title relevance
        title_hits = sum(1 for t in target_norm if t in _normalize(title))
        title_score = min(1.0, title_hits / 2)
        # Impact signal
        impact_score = min(1.0, _quantified_evidence(impact) + 0.3 * _quantified_evidence(description))
        # Novelty: does it show tools not already in experience blocks?
        new_tools = techs_norm - covered_tools
        novelty = min(1.0, len(new_tools) / max(1, len(techs_norm))) if techs_norm else 0.0

        total = round(0.40 * tech_overlap + 0.25 * title_score + 0.20 * impact_score + 0.15 * novelty, 4)

        scored.append({
            "title": title,
            "technologies": techs,
            "url": proj.get("url"),
            "date": proj.get("date"),
            "description": description or None,
            "impact": impact or None,
            "score": total,
            # Require at least one topical signal (tech or title) — pure novelty/impact is not enough
            "decision": "show" if (total >= 0.20 and (tech_overlap > 0 or title_score > 0)) else "hide",
            "debug": {
                "tech_overlap": round(tech_overlap, 3),
                "title_score": round(title_score, 3),
                "impact_score": round(impact_score, 3),
                "novelty": round(novelty, 3),
            },
        })

    scored.sort(key=lambda p: -p["score"])
    return scored


def _exp_date_to_year(date_str: str | None) -> int | None:
    """Return best-effort year from 'MM/YYYY', 'YYYY', or 'présent'."""
    if not date_str:
        return None
    if re.search(r"\bpr[eé]sent\b|aujourd", date_str, re.IGNORECASE):
        return 2026
    m = re.search(r"\b(20\d{2}|19\d{2})\b", date_str)
    return int(m.group(1)) if m else None


def _sum_exp_months(career_experiences: list[dict]) -> int:
    """Sum career experience durations in months, using duration_months when available."""
    total = 0
    for exp in career_experiences:
        dm = exp.get("duration_months")
        if isinstance(dm, int) and dm > 0:
            total += dm
            continue
        start_y = _exp_date_to_year(exp.get("start_date"))
        end_y = _exp_date_to_year(exp.get("end_date")) or 2026
        if start_y and end_y >= start_y:
            total += (end_y - start_y) * 12
    return total


def build_cv_summary(
    profile: dict[str, Any],
    parsed_offer: ParsedOffer,
    matched_skills: list[str],
) -> str:
    """
    Build a 2–3 sentence deterministic CV intro that presents the candidate.

    Sentence 1 — Identity: target title + years of experience + sector.
    Sentence 2 — Core strengths: 2–4 matched skills (non-ESCO, ≤ 5 words each).
    Sentence 3 — Impact signal: first qualifying achievement from recent experiences.

    Never touches skills_uri or the scoring core.
    """
    career = profile.get("career_profile") or {}
    career_exps: list[dict] = career.get("experiences") or []

    # ── Sentence 1: title + experience breadth ──────────────────────────────
    target_title = (parsed_offer.job_title or career.get("base_title") or career.get("target_title") or "").strip()
    total_months = _sum_exp_months(career_exps)
    total_years = round(total_months / 12)

    if total_years >= 10:
        exp_clause = "plus de 10 ans d'expérience"
    elif total_years >= 2:
        exp_clause = f"{total_years} ans d'expérience"
    elif total_months >= 6:
        exp_clause = f"{total_months} mois d'expérience"
    else:
        exp_clause = None

    sector_label = _SECTOR_LABELS.get(parsed_offer.sector or "", "")

    if target_title and exp_clause and sector_label:
        s1 = f"{target_title} avec {exp_clause} en {sector_label}."
    elif target_title and exp_clause:
        s1 = f"{target_title} avec {exp_clause}."
    elif target_title:
        s1 = f"{target_title}."
    else:
        s1 = "Profil expérimenté."

    # ── Sentence 2: core strengths (2–4, short, non-ESCO) ───────────────────
    seen_norms: set[str] = set()
    strengths: list[str] = []
    # Primary source: matched skills for this offer
    for sk in matched_skills:
        if not sk:
            continue
        # Drop ESCO occupation descriptions (verb phrase ≥ 3 words)
        if _ESCO_VERB_RE.match(sk) and len(sk.split()) >= 3:
            continue
        if len(sk.split()) > 5:
            continue
        norm = _normalize(sk)
        if norm and norm not in seen_norms:
            seen_norms.add(norm)
            strengths.append(sk)
        if len(strengths) >= 4:
            break
    # Fallback: career.skills if we still need more
    if len(strengths) < 2:
        for sk in (career.get("skills") or []):
            sk_s = str(sk).strip()
            if not sk_s or len(sk_s.split()) > 4:
                continue
            norm = _normalize(sk_s)
            if norm and norm not in seen_norms:
                seen_norms.add(norm)
                strengths.append(sk_s)
            if len(strengths) >= 4:
                break

    if len(strengths) >= 3:
        s2 = "Spécialisé(e) en " + ", ".join(strengths[:-1]) + f" et {strengths[-1]}."
    elif len(strengths) == 2:
        s2 = f"Compétences avérées en {strengths[0]} et {strengths[1]}."
    elif len(strengths) == 1:
        s2 = f"Compétences avérées en {strengths[0]}."
    else:
        s2 = None

    # ── Sentence 3: impact signal from most recent experience ───────────────
    s3 = None
    for exp in career_exps[:2]:
        for ach in (exp.get("achievements") or []):
            ach_s = str(ach).strip()
            if len(ach_s.split()) >= 6:
                if len(ach_s) > 100:
                    ach_s = ach_s[:97].rsplit(" ", 1)[0] + "…"
                s3 = ach_s if ach_s.endswith(".") else ach_s + "."
                break
        if s3:
            break

    return " ".join(p for p in [s1, s2, s3] if p)


def build_targeted_cv(profile: dict[str, Any], offer: dict[str, Any]) -> dict[str, Any]:
    parsed_offer = parse_offer(offer)
    profile_skills = _collect_profile_skills(profile)
    # Use CareerProfile-aware scorer when career_profile data is available
    experience_scores = score_career_experiences(profile, parsed_offer)
    selected = [item for item in experience_scores if item["decision"] == "keep"][:5]

    # CareerProfile v2 adaptation engine (additive — never touches skills_uri)
    _adapted_experiences: list[AdaptedExperience] = []
    _scored_projects: list[dict[str, Any]] = []
    if profile.get("career_profile"):
        _adapted_experiences = adapt_career_experiences(profile, offer)
        _scored_projects = score_projects(profile, offer, adapted_exps=_adapted_experiences)
    experiences: list[dict[str, Any]] = []
    selected_verbs: list[dict[str, str]] = []
    missing_data: list[str] = []
    for item in selected:
        block, verbs, missing = _rewrite_experience(item, parsed_offer)
        experiences.append(block)
        selected_verbs.extend(verbs)
        missing_data.extend(missing)
    skills_sorted = _sort_skills(profile_skills, parsed_offer, experience_scores)
    matched_keywords = [skill for skill in skills_sorted if any(_normalize(skill) == _normalize(term) or _normalize(term) in _normalize(skill) for term in parsed_offer.core_skills + parsed_offer.tools)]
    missing_keywords = [term for term in parsed_offer.core_skills + parsed_offer.tools + parsed_offer.languages if not any(_normalize(skill) == _normalize(term) or _normalize(term) in _normalize(skill) for skill in profile_skills)]
    ats_score = min(100, round((len(matched_keywords) / max(1, len(parsed_offer.core_skills) + len(parsed_offer.tools) + len(parsed_offer.languages))) * 100))
    education_items = _education_items(profile)
    if not experiences:
        missing_data.append("aucune expérience suffisamment pertinente pour le poste")
    if not education_items:
        missing_data.append("formation absente ou trop faible")
    # cv_strategy from justification layer (additive — never mandatory)
    cv_strategy: dict[str, Any] = {}
    raw_strategy = offer.get("cv_strategy") or {}
    if isinstance(raw_strategy, dict) and raw_strategy:
        cv_strategy = raw_strategy
        # Boost matched_keywords with strategy focus terms (additive, deduped)
        focus_terms = cv_strategy.get("focus") or []
        if isinstance(focus_terms, list):
            for term in focus_terms:
                if isinstance(term, str) and term and term not in matched_keywords:
                    matched_keywords.append(term)

    # Filter ESCO occupation descriptions from matched_keywords for summary
    clean_matched = [k for k in matched_keywords if not (_ESCO_VERB_RE.match(k) and len(k.split()) >= 3)]
    summary = build_cv_summary(profile, parsed_offer, clean_matched)
    return {
        "summary": summary,
        "keywords_injected": skills_sorted,
        "experience_blocks": experiences,
        "adapted_experiences": [
            {
                "title": ae.title,
                "company": ae.company,
                "location": ae.location,
                "start_date": ae.start_date,
                "end_date": ae.end_date,
                "bullets": ae.bullets,
                "tools": ae.tools,
                "autonomy": ae.autonomy,
                "score": ae.score,
                "decision": ae.decision,
                "matched_keywords": ae.matched_keywords,
            }
            for ae in _adapted_experiences
        ],
        "scored_projects": _scored_projects,
        "ats_notes": {
            "matched_keywords": matched_keywords,
            "missing_keywords": _dedupe(missing_keywords, limit=6),
            "ats_score_estimate": ats_score,
            "cv_strategy": cv_strategy if cv_strategy else None,
        },
        "cv": {
            "title": parsed_offer.job_title,
            "experiences": [
                {
                    "role": block["title"],
                    "company": block["company"],
                    "dates": block.get("dates"),
                    "bullets": block["bullets"],
                    "decision": "keep",
                }
                for block in experiences
            ],
            "skills": skills_sorted,
            "education": education_items,
            "layout": "single_column",
        },
        "debug": {
            "parsed_offer": {
                "job_title": parsed_offer.job_title,
                "core_skills": parsed_offer.core_skills,
                "tools": parsed_offer.tools,
                "languages": parsed_offer.languages,
                "sector": parsed_offer.sector,
                "top_issues": parsed_offer.top_issues,
            },
            "experience_scores": [
                {
                    "role": item["experience"].role,
                    "company": item["experience"].company,
                    "score": round(item["score"], 4),
                    "skill_match": round(item["skill_match"], 4),
                    "job_similarity": round(item["job_similarity"], 4),
                    "quantified_evidence": round(item["quantified_evidence"], 4),
                    "sector_similarity": round(item["sector_similarity"], 4),
                    "recency": round(item["recency"], 4),
                    "autonomy": round(item["autonomy"], 4),
                    "decision": item["decision"],
                    "reasons": item["reasons"],
                }
                for item in experience_scores
            ],
            "selected_verbs": selected_verbs,
            "missing_data": _dedupe(missing_data, limit=12),
        },
    }
