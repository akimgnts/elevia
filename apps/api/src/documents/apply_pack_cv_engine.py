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
STOPWORDS = {
    "the", "and", "with", "pour", "avec", "dans", "des", "les", "une", "sur", "from", "that",
    "this", "vos", "notre", "votre", "son", "ses", "leur", "leurs", "mission", "poste", "profil",
}
AUTONOMY_HIGH = {"piloter", "manager", "coordonner", "superviser", "responsable", "owner", "lead"}
AUTONOMY_MED = {"analyser", "structurer", "optimiser", "suivre", "controler", "contrôler", "realiser", "réaliser"}


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
    for key in ("bullets", "highlights", "tasks", "missions", "achievements", "actions", "results"):
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
    skills = profile.get("skills") or profile.get("matching_skills") or []
    if isinstance(skills, str):
        return _dedupe(_split_sentences(skills), limit=20)
    if isinstance(skills, list):
        return _dedupe([str(item) for item in skills], limit=20)
    return []


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
    return _dedupe(matched + supportive + fallback, limit=12)


def build_targeted_cv(profile: dict[str, Any], offer: dict[str, Any]) -> dict[str, Any]:
    parsed_offer = parse_offer(offer)
    profile_skills = _collect_profile_skills(profile)
    experience_scores = score_experiences(profile, parsed_offer)
    selected = [item for item in experience_scores if item["decision"] == "keep"][:5]
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
    summary_bits = []
    if matched_keywords:
        summary_bits.append(f"Ciblage {parsed_offer.sector} avec appuis sur {', '.join(matched_keywords[:3])}")
    if parsed_offer.top_issues:
        summary_bits.append(f"Enjeux du poste : {', '.join(parsed_offer.top_issues[:2])}")
    summary = ". ".join(summary_bits) + ("." if summary_bits else "CV ciblé généré de façon déterministe.")
    return {
        "summary": summary,
        "keywords_injected": skills_sorted,
        "experience_blocks": experiences,
        "ats_notes": {
            "matched_keywords": matched_keywords,
            "missing_keywords": _dedupe(missing_keywords, limit=6),
            "ats_score_estimate": ats_score,
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
