"""
tight_skill_extractor.py — Phrase-level technical skill extraction.

Case-insensitive extraction of 1–5 gram technical phrases from CV text.
Produces a scored, deduplicated, capped list of skill candidates.

Deterministic: same input → same output (stable sort by score DESC, phrase ASC).
No LLM. No score impact on matching.

Input:
  raw_text: str
  cluster: str | None       (e.g. "DATA_IT")
  language_hint: str | None (e.g. "fr" / "en" — reserved, not used yet)

Output:
  ExtractionResult with:
    raw_tokens     — unique 1-gram word tokens from the text
    skill_candidates — scored, filtered, capped (≤ MAX_SKILL_CANDIDATES = 120)
    dropped_tokens — phrases filtered out (capped at 200 for payload safety)
    metrics        — raw_count, candidate_count, noise_ratio, tech_density, top_ngrams
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_SKILL_CANDIDATES = 120
MAX_NGRAM_SIZE = 5
MIN_PHRASE_CHARS = 2  # phrases shorter than this are skipped (unless allowlisted)
MAX_DROPPED_TRACKED = 200  # cap dropped_tokens list to avoid huge payloads

# ── Regexes ───────────────────────────────────────────────────────────────────

# Preserve tech chars within tokens (scikit-learn, vue.js, ci/cd, C++)
_WORD_TOKEN_RE = re.compile(
    r"[cC]\+\+"                                         # C++ special case
    r"|[a-zA-Z0-9][a-zA-Z0-9+#.\-\/_]*[a-zA-Z0-9]"    # multi-char with tech separators
    r"|[a-zA-Z0-9]",                                    # single-char fallback
)
_NUMBER_ONLY_RE = re.compile(r"^\d+([.,]\d+)?$")
_TECH_SEPARATOR_RE = re.compile(r"[+#.\-\/_]")

# ── Allowlists ────────────────────────────────────────────────────────────────

_CLUSTER_ALLOWLIST: Dict[str, set] = {
    "DATA_IT": {
        "machine learning", "deep learning", "data science", "data engineering",
        "data analysis", "data visualization", "data mining", "time series",
        "forecasting", "business intelligence", "power bi", "powerbi",
        "tableau", "dashboard", "dashboards", "etl", "sql", "python",
        "spark", "airflow", "kafka", "ml", "ai", "bi", "r",
        "scikit-learn", "tensorflow", "pytorch", "keras", "docker",
        "kubernetes", "dbt", "databricks", "snowflake", "redshift",
        "elasticsearch", "pandas", "numpy", "matplotlib", "seaborn",
        "jupyter", "git", "github", "gitlab", "jira", "confluence",
        "aws", "gcp", "azure", "hadoop", "hive", "dask",
        "flask", "fastapi", "django", "postgresql", "mysql", "mongodb",
        "neo4j", "redis", "rest", "graphql", "microservices",
        "ci/cd", "devops", "agile", "scrum", "kanban",
        "c++", "scala", "java", "javascript", "typescript", "golang",
        "looker", "metabase", "grafana", "prometheus", "terraform",
        "nlp", "computer vision", "reinforcement learning",
        "a/b testing", "data warehouse", "data lake", "feature engineering",
    },
    "MARKETING_SALES": {
        "crm", "email marketing", "marketing automation", "seo", "sem",
        "google analytics", "campaign management", "lead generation", "salesforce",
        "hubspot", "mailchimp", "google ads", "facebook ads", "linkedin ads",
        "content marketing", "social media", "brand management", "a/b testing",
        "conversion rate", "customer journey", "roi", "kpi",
    },
    "FINANCE_LEGAL": {
        "financial modeling", "risk management", "audit", "ifrs", "gaap",
        "excel", "vba", "valuation", "m&a", "lbo", "dcf",
        "financial analysis", "corporate finance", "investment banking",
        "private equity", "derivatives", "fixed income",
        "portfolio management", "bloomberg", "reuters",
    },
}

_GLOBAL_ALLOWLIST = {"bi", "ml", "ai", "sql", "r", "aws", "gcp", "sdk", "iot", "api"}

# ── Blocklist ─────────────────────────────────────────────────────────────────

_GENERIC_BLOCKLIST = {
    # Generic skills / soft skills
    "business", "strategy", "management", "project", "projects",
    "team", "experience", "skills", "skill", "knowledge",
    "reporting", "documentation", "communication", "leadership",
    # French soft skills
    "autonomie", "autonome", "rigueur", "polyvalent", "rigoureux",
    "dynamique", "motivé", "proactif", "créatif",
    # Languages (not programming)
    "anglais", "english", "francais", "french", "espagnol", "spanish",
    "allemand", "german", "italien", "italian", "arabe", "arabic",
    "chinois", "chinese", "japonais", "japanese",
    # Cities / geography
    "paris", "london", "berlin", "madrid", "barcelona", "lyon",
    "marseille", "lille", "nice", "toulouse", "bordeaux",
    "new", "york", "san", "francisco", "los", "angeles",
    # French stop words
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou",
    "en", "au", "aux", "avec", "pour", "par", "sur", "dans", "est",
    "sont", "avoir", "être", "faire", "peut", "plus", "mais", "comme",
    # English stop words
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with",
    "from", "by", "as", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "will", "would", "could", "should",
    # Job-level generic terms
    "year", "years", "month", "months", "profil", "professionnel",
    "poste", "emploi", "travail", "formation", "diplome", "bac",
    "master", "licence", "stage", "alternance", "cdi", "cdd",
    "junior", "senior", "expert", "consultant", "manager",
    "directeur", "responsable", "chef", "coordinateur",
    # Verbs / generic actions
    "développer", "développement", "implementation", "analyse",
    "gestion", "coordination", "pilotage",
}

# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class DroppedToken:
    phrase: str
    reason: str


@dataclass
class ExtractionResult:
    raw_tokens: List[str]
    skill_candidates: List[str]
    dropped_tokens: List[DroppedToken]
    metrics: dict = field(default_factory=dict)


# ── Core logic ────────────────────────────────────────────────────────────────


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _tokenize(text: str) -> List[str]:
    """Extract word-level tokens, preserving tech chars (scikit-learn, vue.js, C++)."""
    return _WORD_TOKEN_RE.findall(_nfkc(text))


def _phrase_has_tech_marker(phrase_lower: str, words: List[str], cluster_allowlist: set) -> bool:
    """
    Returns True if the phrase carries at least one technical signal.

    A tech marker is any of:
      - The phrase itself is in the cluster or global allowlist
      - Any token contains a tech separator (scikit-learn, vue.js, ci/cd)
      - Any token contains a digit (python3, java8, gpt4)
      - Any token is in the global allowlist (sql, bi, ml, api …)
    """
    if phrase_lower in cluster_allowlist or phrase_lower in _GLOBAL_ALLOWLIST:
        return True
    for w in words:
        if _TECH_SEPARATOR_RE.search(w):
            return True
        if any(c.isdigit() for c in w):
            return True
        if w in _GLOBAL_ALLOWLIST:
            return True
    return False


def _score_phrase(phrase_lower: str, cluster_allowlist: set) -> Tuple[int, str]:
    """
    Score a lower-cased phrase. Returns (score, reason_if_dropped).
    score > 0 → keep candidate.  score <= 0 → drop.

    Blocklist rule (safe):
      Penalty is only applied when the phrase is a singleton (1-gram) OR has no
      tech marker. Multi-word phrases that carry a positive tech signal (allowlist
      hit, tech separator, digit, global acronym) bypass blocklist penalties —
      this preserves legitimate compound skills like "data management" or
      "project management" when they co-occur with cluster-relevant tokens.
    """
    # Early exits for obviously invalid phrases
    if _NUMBER_ONLY_RE.match(phrase_lower.replace(" ", "")):
        return -10, "number_only"

    if len(phrase_lower) < MIN_PHRASE_CHARS and phrase_lower not in _GLOBAL_ALLOWLIST:
        return -10, "too_short"

    score = 0
    words = phrase_lower.split()

    # Strong positive: explicit cluster or global allowlist hit
    if phrase_lower in cluster_allowlist:
        score += 3
    elif phrase_lower in _GLOBAL_ALLOWLIST:
        score += 2

    # Positive: has tech separator within a token (scikit-learn, vue.js, ci/cd)
    for w in words:
        if _TECH_SEPARATOR_RE.search(w):
            score += 2
            break

    # Positive: multi-word phrase (2+ tokens)
    if len(words) >= 2:
        score += 1

    # Blocklist penalty — guarded by tech-marker check for multi-word phrases.
    # Singletons are always penalized; multi-word phrases only when they carry
    # no technical signal (no allowlist, no separator, no digit, no global acronym).
    apply_blocklist = len(words) == 1 or not _phrase_has_tech_marker(
        phrase_lower, words, cluster_allowlist
    )
    if apply_blocklist:
        for w in words:
            if w in _GENERIC_BLOCKLIST:
                score -= 3

    reason = "score_too_low" if score <= 0 else ""
    return score, reason


def extract_tight_skills(
    raw_text: str,
    cluster: Optional[str] = None,
    language_hint: Optional[str] = None,  # reserved
) -> ExtractionResult:
    """
    Extract technical skill candidates from raw CV text.

    - Case-insensitive detection, original casing preserved in output
    - Favors multi-word technical phrases (2–5 grams)
    - Removes generic / soft-skill terms
    - Caps at MAX_SKILL_CANDIDATES = 120
    - Deterministic: (score DESC, phrase ASC) stable sort

    Args:
        raw_text:      Raw CV text (PDF-extracted or plain text)
        cluster:       Dominant cluster ("DATA_IT", "FINANCE_LEGAL", etc.)
        language_hint: "fr" or "en" (reserved for future locale-aware blocklists)

    Returns:
        ExtractionResult
    """
    if not raw_text or not raw_text.strip():
        return ExtractionResult(
            raw_tokens=[],
            skill_candidates=[],
            dropped_tokens=[],
            metrics={
                "raw_count": 0,
                "candidate_count": 0,
                "noise_ratio": 0.0,
                "tech_density": 0.0,
                "top_ngrams": [],
            },
        )

    # Build cluster-specific allowlist
    cluster_key = (cluster or "").upper()
    cluster_allowlist = _CLUSTER_ALLOWLIST.get(cluster_key, set()) | _GLOBAL_ALLOWLIST

    # Tokenize (1-grams from text, tech-char-preserving)
    tokens = _tokenize(raw_text)
    n = len(tokens)

    # Build all n-gram candidates (1–MAX_NGRAM_SIZE grams) via sliding window
    seen_lower: set = set()
    scored: List[Tuple[str, str, int]] = []  # (original_phrase, phrase_lower, score)
    dropped: List[DroppedToken] = []

    for start in range(n):
        for size in range(1, MAX_NGRAM_SIZE + 1):
            if start + size > n:
                break

            phrase_tokens = tokens[start : start + size]
            phrase_original = " ".join(phrase_tokens)
            phrase_lower = phrase_original.lower()

            if phrase_lower in seen_lower:
                continue
            seen_lower.add(phrase_lower)

            score, reason = _score_phrase(phrase_lower, cluster_allowlist)

            if score > 0:
                scored.append((phrase_original, phrase_lower, score))
            elif len(phrase_lower) >= MIN_PHRASE_CHARS and len(dropped) < MAX_DROPPED_TRACKED:
                dropped.append(DroppedToken(phrase=phrase_original, reason=reason or "score_too_low"))

    # Stable deterministic sort: score DESC, phrase ASC
    scored.sort(key=lambda x: (-x[2], x[1]))

    # Cap at MAX_SKILL_CANDIDATES
    final: List[str] = [phrase_orig for phrase_orig, _, _ in scored[:MAX_SKILL_CANDIDATES]]

    # Metrics
    raw_count = len(seen_lower)
    candidate_count = len(final)
    noise_count = len(dropped)

    tech_count = sum(
        1 for p in final
        if len(p.split()) >= 2 or p.lower() in cluster_allowlist
    )
    tech_density = round(tech_count / candidate_count, 4) if candidate_count > 0 else 0.0
    noise_ratio = round(noise_count / max(raw_count, 1), 4)

    top_ngrams = [
        {"phrase": p, "score": s}
        for p, _, s in scored[:10]
    ]

    metrics = {
        "raw_count": raw_count,
        "candidate_count": candidate_count,
        "noise_ratio": noise_ratio,
        "tech_density": tech_density,
        "top_ngrams": top_ngrams,
    }

    # raw_tokens: unique 1-gram tokens (preserves first-seen casing, insertion order)
    raw_token_list = list(dict.fromkeys(t for t in tokens if len(t) >= MIN_PHRASE_CHARS))

    return ExtractionResult(
        raw_tokens=raw_token_list,
        skill_candidates=final,
        dropped_tokens=dropped,
        metrics=metrics,
    )
