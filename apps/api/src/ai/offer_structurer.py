"""
offer_structurer.py — Structured rewrite of an offer description.

Takes a raw job description (any language) and produces 7 clean blocks:
  quick_read · mission_summary · responsibilities · tools_environment ·
  role_context · key_requirements · nice_to_have

Rules:
  - Translate to French if the offer is in English
  - Reformulate — never copy-paste raw text
  - Strip noise: internal codes, region names, HR filler
  - Mission-first: lead with what the person DOES, not what they need

Falls back to deterministic extraction when LLM unavailable.
Never raises.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_TIMEOUT_S = 45
_MAX_TOKENS = 1800
_RETRIES = 1

# ---------------------------------------------------------------------------
# Noise patterns to strip from output values (post-LLM defensive cleanup)
# ---------------------------------------------------------------------------

_NOISE_RE = re.compile(
    r"\b(?:SouthAM|AMEA|APAC|LATAM|MEA|Greater China|Asia[- ]Pacific|Asia Pacific"
    r"|Digital4Now|Learning Lab|Transform\w*|[A-Z][a-z]+4[A-Z][a-z]+"
    r"|[A-Z]{2,6}\d+[A-Z]*)\b",
    re.IGNORECASE,
)


def _strip_noise(text: str) -> str:
    return _NOISE_RE.sub("", text).replace("  ", " ").strip()


def _clean_list(items: list) -> list:
    cleaned = []
    for item in items:
        if not isinstance(item, str):
            continue
        s = _strip_noise(item).strip(" ,.-")
        if s and len(s) > 5:
            cleaned.append(s)
    return cleaned


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    try:
        from api.utils.env import get_llm_api_key
        key = get_llm_api_key()
        if key:
            return key
    except Exception:
        pass
    for name in ("OPENAI_API_KEY", "OPENAI_KEY", "LLM_API_KEY"):
        v = os.environ.get(name, "").strip()
        if v:
            return v
    return None


def _call_llm(system_prompt: str, user_prompt: str) -> Tuple[dict, int]:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LLM_DISABLED")
    try:
        from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError
    except ImportError:
        raise RuntimeError("LLM_DISABLED: openai not installed")

    client = OpenAI(api_key=api_key, timeout=_TIMEOUT_S)
    t0 = time.time()

    for attempt in range(_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=_MAX_TOKENS,
            )
            break
        except (APITimeoutError, APIConnectionError) as exc:
            if attempt < _RETRIES:
                time.sleep(1.5)
                continue
            raise RuntimeError("LLM_ERROR: timeout") from exc
        except APIStatusError as exc:
            raise RuntimeError(f"LLM_ERROR: status {exc.status_code}") from exc
        except Exception as exc:
            raise RuntimeError(f"LLM_ERROR: {type(exc).__name__}") from exc

    duration_ms = int((time.time() - t0) * 1000)
    raw = (resp.choices[0].message.content or "{}").strip()
    logger.info(
        '{"event":"AI_STRUCTURE_LLM_CALL","model":"%s","chars_in":%d,"chars_out":%d,"ms":%d}',
        _MODEL, len(system_prompt) + len(user_prompt), len(raw), duration_ms,
    )
    try:
        return json.loads(raw), duration_ms
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM_JSON_PARSE_ERROR: {exc}") from exc


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
Tu es un expert en analyse de fiches de poste, spécialisé dans les postes VIE et junior/mid-level.

Ton rôle : transformer une offre d'emploi brute en une fiche lisible et structurée en français.

=== PRIORITÉS (dans cet ordre) ===

1. MISSIONS — Ce que la personne va FAIRE concrètement au quotidien
2. RESPONSABILITÉS — Actions clés du poste (verbes d'action)
3. OUTILS / ENVIRONNEMENT — Technologies, logiciels, environnement de travail
4. CONTEXTE — International, VIE, déplacements, coordination pays
5. PRÉREQUIS — Ce qui est vraiment nécessaire (pas le jargon RH)
6. BONUS — Ce qui est optionnel

=== RÈGLES OBLIGATOIRES ===

REFORMULER — ne jamais copier-coller le texte brut
TRADUIRE EN FRANÇAIS — si l'offre est en anglais, tout traduire
SUPPRIMER SANS EXCEPTION :
  - Codes géographiques internes : SouthAM, AMEA, MEA, APAC, LATAM, Asia-Pacific, Greater China
  - Noms de programmes/initiatives : Digital4Now, Learning Lab, Transform Program, tout sigle X4Y
  - Jargon RH vide : "rejoindre nos équipes dynamiques", "dans un contexte stimulant", "nous vous offrons"
  - Informations administratives sans valeur pour le candidat

=== FORMAT DE SORTIE (JSON strict, sans markdown) ===

{
  "quick_read": "1 phrase naturelle — ce que fait vraiment le poste (ex: 'Analyste Data chargé de piloter la performance commerciale via des tableaux de bord').",
  "mission_summary": "2 à 4 phrases — ce que la personne fait concrètement. Commencer par un verbe. Ex: 'Vous pilotez... Vous analysez... Vous collaborez...'",
  "responsibilities": [
    "Action concrète 1 (ex: Construire et maintenir les dashboards de suivi KPI)",
    "Action concrète 2",
    "Action concrète 3",
    "...jusqu'à 6 max"
  ],
  "tools_environment": [
    "Outil ou technologie utilisée (ex: Python, SQL, Power BI, SAP, Excel)",
    "Environnement de travail si précisé (ex: Environnement cloud Azure)"
  ],
  "role_context": [
    "Contexte pertinent (ex: Poste VIE 12 mois, Coordination avec 8 pays, Déplacements occasionnels)"
  ],
  "key_requirements": [
    "Compétence vraiment requise 1",
    "Compétence vraiment requise 2"
  ],
  "nice_to_have": [
    "Bonus ou plus apprécié 1"
  ]
}

Limites : responsibilities 3–6 · tools_environment 2–8 · role_context 1–4 · key_requirements 3–6 · nice_to_have 0–3\
"""


def _build_user_prompt(
    description: str,
    missions: List[str],
    requirements: List[str],
    tools_stack: List[str],
    context_tags: List[str],
) -> str:
    lines = ["=== DESCRIPTION BRUTE ===", description[:2000].strip()]
    if missions:
        lines += ["\n=== MISSIONS PRÉ-EXTRAITES (contexte supplémentaire) ===", *missions[:6]]
    if requirements:
        lines += ["\n=== EXIGENCES PRÉ-EXTRAITES (contexte supplémentaire) ===", *requirements[:6]]
    if tools_stack:
        lines += ["\n=== OUTILS DÉTECTÉS ===", ", ".join(tools_stack[:12])]
    if context_tags:
        lines += ["\n=== TAGS DE CONTEXTE ===", ", ".join(context_tags)]
    lines.append(
        "\nProduis la fiche structurée. "
        "Si la description est en anglais, traduis tout en français. "
        "Commence par les missions, pas par les prérequis."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Common tools / tech to detect in raw text (language-neutral)
_TOOLS_RE = re.compile(
    r"\b(Python|SQL|R\b|Excel|Power\s?BI|Tableau|Looker|SAP|Oracle|Salesforce|"
    r"Workday|Hyperion|PowerPoint|VBA|MATLAB|Databricks|Snowflake|Azure|AWS|GCP|"
    r"dbt|Airflow|Spark|Hadoop|TensorFlow|Scikit[- ]learn|Pandas|NumPy|"
    r"JavaScript|TypeScript|Java|C\+\+|\.NET|Django|FastAPI|React|"
    r"Jira|Confluence|Git|Docker|Kubernetes|Terraform|Linux)\b",
    re.IGNORECASE,
)

# Context keywords (output labels already in French)
_CONTEXT_PATTERNS = [
    (re.compile(r"\bVIE\b"), "Poste VIE"),
    (re.compile(r"\binternat\w+\b", re.IGNORECASE), "Contexte international"),
    (re.compile(r"\b(multi[- ]?pays|plusieurs pays|countries)\b", re.IGNORECASE), "Coordination multi-pays"),
    (re.compile(r"\b(déplacements?|travel|mobilité)\b", re.IGNORECASE), "Déplacements possibles"),
    (re.compile(r"\b(télétr\w+|remote|distanc\w+)\b", re.IGNORECASE), "Télétravail mentionné"),
    (re.compile(r"\b(anglais|english)\b", re.IGNORECASE), "Anglais requis"),
    (re.compile(r"\b(grands? groupes?|CAC\s*40|Fortune\s*500)\b", re.IGNORECASE), "Grand groupe"),
    (re.compile(r"\b(start[- ]?up|scaleup|scale-up)\b", re.IGNORECASE), "Startup / scale-up"),
]

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_FR_STOPWORDS = frozenset([
    "vous", "votre", "notre", "nous", "dans", "avec", "pour", "sur", "est",
    "les", "des", "une", "qui", "que", "cette", "sera", "être", "avoir",
    "vos", "son", "ses", "leur", "leurs", "mais", "par", "au", "aux",
    "du", "en", "de", "la", "le", "et", "un", "à",
])
_EN_STOPWORDS = frozenset([
    "you", "your", "our", "will", "the", "and", "for", "with", "this",
    "that", "are", "have", "be", "is", "to", "of", "in", "we", "as",
    "an", "by", "or", "at", "from", "on", "has", "was", "been",
])


def _detect_language(text: str) -> str:
    """Return 'fr' or 'en' based on stopword frequency in the first 600 chars."""
    sample = text[:600].lower()
    words = re.findall(r"\b[a-z]+\b", sample)
    fr_count = sum(1 for w in words if w in _FR_STOPWORDS)
    en_count = sum(1 for w in words if w in _EN_STOPWORDS)
    return "fr" if fr_count >= en_count else "en"


# ---------------------------------------------------------------------------
# French template system for English offers (fallback only)
#
# Instead of translating English sentences (which produces broken Franglais),
# we detect semantic patterns in the English text and map them to
# pre-written French template sentences. Clean French output, no LLM.
# ---------------------------------------------------------------------------

# (regex_pattern, fr_template_sentence)
# Ordered by specificity — first match wins per pattern group
_EN_VERB_TEMPLATES: List[Tuple[str, str]] = [
    # Data / analytics
    (r"\b(analyz|analys|dashboard|reporting|kpi|indicator|metric)\w*\b",
     "Analyser les données et produire des reportings et tableaux de bord pour le pilotage de la performance"),
    # Data collection / processing
    (r"\b(collect|process|clean|transform|pipeline|etl|ingestion)\w*\b",
     "Collecter, traiter et fiabiliser les données issues de différentes sources"),
    # Development / build
    (r"\b(develop|build|create|implement|code|program)\w*\b",
     "Développer et mettre en œuvre des solutions techniques adaptées aux besoins métier"),
    # Automation / tools
    (r"\b(automat|script|tool|optimize|improve|streamline)\w*\b",
     "Automatiser et optimiser les processus existants pour gagner en efficacité"),
    # Management / coordination
    (r"\b(manag|coordinat|oversee|supervis|govern)\w*\b",
     "Gérer et coordonner les activités opérationnelles et les parties prenantes"),
    # Monitoring / control
    (r"\b(monitor|track|follow|control|ensur|maintain|watch)\w*\b",
     "Suivre les indicateurs de performance et garantir la qualité des livrables"),
    # Reporting / presentation
    (r"\b(report|present|communicat|brief|updat)\w*\b",
     "Préparer et présenter des reportings réguliers à la direction et aux équipes"),
    # Support / collaboration
    (r"\b(support|assist|help|collaborat|work with|partner)\w*\b",
     "Accompagner et collaborer étroitement avec les équipes métier et techniques"),
    # Finance / budget
    (r"\b(budget|forecast|financ|cost|revenue|p&l|pl\b|account)\w*\b",
     "Piloter et analyser les indicateurs financiers, budgets et prévisions"),
    # Projects / initiatives
    (r"\b(project|initiative|program|deliver|roadmap|plan)\w*\b",
     "Piloter des projets de bout en bout et garantir l'atteinte des objectifs"),
    # Procurement / supply chain
    (r"\b(procure|purchas|supply|logistics|vendor|supplier)\w*\b",
     "Gérer les relations fournisseurs et optimiser les flux de la chaîne d'approvisionnement"),
    # Marketing / communication
    (r"\b(market|brand|campaign|customer|content|digital)\w*\b",
     "Concevoir et déployer des actions marketing et de communication ciblées"),
    # Research / analysis
    (r"\b(research|stud|investigat|benchmark|assess|evaluat)\w*\b",
     "Réaliser des études, benchmarks et analyses pour éclairer la prise de décision"),
    # Design / UX
    (r"\b(design|ux|ui|prototype|wireframe|user experience)\w*\b",
     "Concevoir des interfaces et expériences utilisateur centrées sur les besoins"),
    # Define / structure
    (r"\b(defin|structur|frame|specify|document|model)\w*\b",
     "Définir les méthodes de travail, standards et livrables attendus"),
]


def _match_en_templates(text: str) -> List[str]:
    """Return FR responsibility sentences matching detected EN verb patterns (max 5)."""
    text_lower = text.lower()
    matched: List[str] = []
    seen_templates: set = set()
    for pattern_str, fr_sentence in _EN_VERB_TEMPLATES:
        if len(matched) >= 5:
            break
        if fr_sentence in seen_templates:
            continue
        if re.search(pattern_str, text_lower):
            matched.append(fr_sentence)
            seen_templates.add(fr_sentence)
    return matched


# ---------------------------------------------------------------------------
# French action verb pattern (for FR offers)
# ---------------------------------------------------------------------------

_FR_ACTION_VERBS_RE = re.compile(
    r"\b(analyser?|développer?|gérer?|piloter?|coordonner?|assurer?|participer?|"
    r"contribuer?|réaliser?|mettre en place|suivre|élaborer?|produire|rédiger?|"
    r"animer?|préparer?|optimiser?|construire|identifier?|définir?|accompagner?|"
    r"superviser?)\b",
    re.IGNORECASE,
)


def _extract_fr_responsibilities(text: str, missions: List[str]) -> List[str]:
    """Extract action-verb sentences from French text + pre-extracted missions."""
    results: List[str] = []

    for m in missions[:6]:
        s = _strip_noise(m.strip())
        if s and len(s) > 15:
            results.append(s)

    if len(results) >= 4:
        return results[:6]

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    sentences = _SENT_SPLIT_RE.split(clean)
    bullet_re = re.compile(r"^[\-•*▸►\d.)\]]\s*")

    for raw_sent in sentences:
        sent = bullet_re.sub("", raw_sent).strip()
        if len(sent) < 20 or len(sent) > 200:
            continue
        if _FR_ACTION_VERBS_RE.search(sent):
            cleaned = _strip_noise(sent)
            if cleaned and cleaned not in results:
                results.append(cleaned)
        if len(results) >= 6:
            break

    return results[:6]


def _extract_tools(text: str, tools_stack: List[str]) -> List[str]:
    """Detect tool names from pre-extracted list + raw text."""
    found = list(tools_stack[:8])
    seen = {t.lower() for t in found}

    for match in _TOOLS_RE.finditer(text):
        tool = match.group(0)
        if tool.lower() not in seen:
            found.append(tool)
            seen.add(tool.lower())
        if len(found) >= 8:
            break

    return found[:8]


def _extract_context(text: str, context_tags: List[str]) -> List[str]:
    ctx: List[str] = []
    seen: set = set()

    tag_map = {
        "vie": "Poste VIE", "international": "Contexte international",
        "remote": "Télétravail mentionné", "hybride": "Mode hybride",
        "expatriation": "Expatriation",
    }
    for tag in context_tags:
        label = tag_map.get(tag.lower())
        if label and label not in seen:
            ctx.append(label)
            seen.add(label)

    for pattern, label in _CONTEXT_PATTERNS:
        if label not in seen and pattern.search(text):
            ctx.append(label)
            seen.add(label)
        if len(ctx) >= 4:
            break

    return ctx[:4]


def _dedup_requirements_vs_tools(key_req: List[str], tools: List[str]) -> List[str]:
    """Remove from key_requirements items that are already in tools_environment."""
    tools_lower = {t.lower() for t in tools}
    return [r for r in key_req if r.lower() not in tools_lower]


def _deterministic_fallback(
    description: str,
    missions: List[str],
    requirements: List[str],
    tools_stack: List[str],
    context_tags: List[str],
    duration_ms: int,
) -> dict:
    lang = _detect_language(description)
    tools = _extract_tools(description, tools_stack)
    context = _extract_context(description, context_tags)

    if lang == "en":
        # Template-based French generation — never emit English sentences
        responsibilities = _match_en_templates(description)
        if not responsibilities:
            # Absolute last resort: generic templates
            responsibilities = [
                "Analyser les données et produire des reportings pour les équipes",
                "Collaborer avec les parties prenantes locales et internationales",
                "Contribuer à l'amélioration continue des processus et des outils",
            ]

        mission_summary = (
            responsibilities[0]
            + (". " + responsibilities[1] if len(responsibilities) > 1 else "")
            + ". "
            + (responsibilities[2] if len(responsibilities) > 2 else "Coordination étroite avec les équipes métier.")
        )
        quick_read = responsibilities[0].rstrip(".") + "."

        # key_requirements: use pre-extracted (often tool names, language-neutral)
        # + add "Anglais professionnel" since the offer is in English
        key_req = _clean_list(requirements[:6])
        if not any("anglais" in r.lower() for r in key_req + context):
            key_req = ["Anglais professionnel (offre en anglais)"] + key_req
        key_req = _dedup_requirements_vs_tools(key_req, tools)

    else:
        # French offer: extract action-verb sentences verbatim
        responsibilities = _extract_fr_responsibilities(description, missions)
        key_req = _dedup_requirements_vs_tools(_clean_list(requirements[:6]), tools)

        if responsibilities:
            mission_summary = " ".join(responsibilities[:3])
        else:
            clean = re.sub(r"<[^>]+>", " ", description)
            clean = re.sub(r"\s+", " ", clean).strip()
            parts = _SENT_SPLIT_RE.split(clean)
            good = [p.strip() for p in parts if len(p.strip()) > 30]
            mission_summary = _strip_noise(" ".join(good[:3])) if good else _strip_noise(description[:300])

        quick_read = (
            responsibilities[0] if responsibilities
            else _strip_noise(description[:120]).rstrip(".") + "."
        )

    return {
        "quick_read": quick_read,
        "mission_summary": mission_summary,
        "responsibilities": responsibilities,
        "tools_environment": tools,
        "role_context": context,
        "key_requirements": key_req,
        "nice_to_have": [],
        "_fallback": True,
        "_duration_ms": duration_ms,
    }


# ---------------------------------------------------------------------------
# Response normalisation
# ---------------------------------------------------------------------------

def _normalise(raw: dict, offer_id: str, llm_used: bool, fallback_used: bool, duration_ms: int) -> dict:
    def s(val: Any, default: str = "") -> str:
        return _strip_noise(str(val).strip()) if val else default

    return {
        "quick_read": s(raw.get("quick_read"), "Poste à analyser."),
        "mission_summary": s(raw.get("mission_summary"), ""),
        "responsibilities": _clean_list(raw.get("responsibilities") or [])[:6],
        "tools_environment": _clean_list(raw.get("tools_environment") or [])[:8],
        "role_context": _clean_list(raw.get("role_context") or [])[:4],
        "key_requirements": _clean_list(raw.get("key_requirements") or [])[:6],
        "nice_to_have": _clean_list(raw.get("nice_to_have") or [])[:3],
        "meta": {
            "offer_id": offer_id,
            "llm_used": llm_used,
            "fallback_used": fallback_used,
            "duration_ms": duration_ms,
            "model": _MODEL if llm_used else None,
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def structure_offer(
    *,
    offer_id: str,
    description: str,
    missions: List[str],
    requirements: List[str],
    tools_stack: List[str],
    context_tags: List[str],
) -> dict:
    """
    Produce a structured, noise-free rewrite of the offer description.
    Returns a dict that maps to StructuredOfferSummary. Never raises.
    """
    t0 = time.time()

    api_key = _get_api_key()
    if api_key:
        try:
            user = _build_user_prompt(description, missions, requirements, tools_stack, context_tags)
            raw, _ = _call_llm(_SYSTEM, user)
            duration_ms = int((time.time() - t0) * 1000)
            return _normalise(raw, offer_id, llm_used=True, fallback_used=False, duration_ms=duration_ms)
        except Exception as exc:
            logger.warning('{"event":"AI_STRUCTURE_LLM_FALLBACK","reason":"%s"}', str(exc)[:120])

    duration_ms = int((time.time() - t0) * 1000)
    raw = _deterministic_fallback(description, missions, requirements, tools_stack, context_tags, duration_ms)
    return _normalise(raw, offer_id, llm_used=False, fallback_used=True, duration_ms=duration_ms)
