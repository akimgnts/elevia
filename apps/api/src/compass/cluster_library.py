"""
compass/cluster_library.py — Cluster-aware non-ESCO domain skill library.

Persistence:  SQLite table `cluster_domain_skills` in data/db/context.db (WAL mode, thread-safe)

Activation rules (PENDING → ACTIVE):
  (occurrences_cv ≥ 2  AND  occurrences_offers ≥ 3)
  OR (occurrences_offers ≥ 5  alone)
  AND validated deterministically AND cluster-coherent

Validation rules (pure function, no DB):
  - 2 ≤ len(token) ≤ 50 chars
  - 1 ≤ word_count ≤ 4
  - not in FR/EN stopwords
  - not number-only
  - not soft-skill pattern

Score invariance: NEVER reads or writes score_core.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import unicodedata
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .contracts import (
    ClusterDomainSkill,
    ClusterLibraryMetrics,
    MarketRadarReport,
)

logger = logging.getLogger(__name__)

# ── Storage path (shares context.db with other stores) ───────────────────────

_DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "db" / "context.db"
_REPORTS_DIR = Path(__file__).parent.parent.parent / "data" / "reports"

# ── Activation thresholds ─────────────────────────────────────────────────────

ACTIVATION_CV_MIN = int(os.getenv("ELEVIA_CLUSTER_CV_MIN", "2"))
ACTIVATION_OFFER_MIN = int(os.getenv("ELEVIA_CLUSTER_OFFER_MIN", "3"))
ACTIVATION_OFFER_ONLY_MIN = int(os.getenv("ELEVIA_CLUSTER_OFFER_ONLY_MIN", "5"))

# ── Stopwords (FR + EN + generic business terms, not technical) ───────────────

_STOPWORDS: Set[str] = {
    # FR articles / prepositions / conjunctions
    "le", "la", "les", "un", "une", "des", "du", "de", "en", "au", "aux",
    "et", "ou", "dans", "sur", "par", "pour", "avec", "sans", "mais",
    "donc", "car", "ni", "or", "si", "que", "qui", "dont", "comme",
    "plus", "moins", "tres", "bien", "aussi", "encore", "toujours", "jamais",
    # FR verbs (gerunds / infinitives common in CVs)
    "avoir", "etre", "faire", "aller", "venir", "voir", "savoir", "pouvoir",
    "vouloir", "devoir", "prendre", "donner", "trouver", "mettre",
    "analyser", "gerer", "piloter", "produire", "realiser", "developper",
    "accompagner", "assurer", "suivre", "coordonner", "participer",
    # FR nouns too generic
    "equipe", "projet", "travail", "poste", "entreprise", "societe",
    "experience", "competence", "profil", "candidat", "emploi", "stage",
    "an", "ans", "mois", "annee", "annees", "niveau", "sens",
    "objectif", "resultat", "mission", "activite", "service", "client",
    "secteur", "domaine", "processus",
    # EN articles / prepositions
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "from",
    "by", "is", "are", "was", "were", "be", "been", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "and", "or", "but", "not", "as", "this", "that", "these", "those",
    # EN generic business
    "work", "team", "project", "experience", "skill", "skills", "profile",
    "company", "enterprise", "role", "position", "job", "career",
    # Soft skills (explicitly blocked)
    "communication", "autonomie", "autonome", "rigoureux", "dynamique",
    "motive", "motivation", "serieux", "ponctuel", "adaptable", "curieux", "proactif",
    "creatif", "organise", "polyvalent", "reactif", "leadership",
    "empathie", "ecoute", "creativite",
}

# ── Soft skill patterns (reject if matched) ───────────────────────────────────

_SOFT_SKILL_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bsoft\s*skill", re.IGNORECASE),
    re.compile(r"\bcompetence[s]?\s+(?:humaine|comportementale|relationnelle)", re.IGNORECASE),
    re.compile(r"\b(?:esprit\s+d.equipe|sens\s+du\s+service|qualite\s+relationnelle)\b", re.IGNORECASE),
    re.compile(r"\bteam\s*work\b", re.IGNORECASE),
]

# ── Number-only ───────────────────────────────────────────────────────────────

_NUMBER_ONLY = re.compile(r"^\d+([.,]\d+)?$")

# ── Tool / skill allowlist — forces DOMAIN_PENDING (display-only, not scored) ─

_TOOL_ALLOWLIST: Set[str] = {
    # Spec-mandated list
    "tableau", "dashboards", "dashboard", "forecasting", "forecast",
    "adobe", "photoshop", "premiere", "crm", "kpi", "kpis",
    "api", "apis", "analytics", "opc", "opcvm", "power bi", "powerbi",
    # Finance/asset management
    "ucits", "etf", "etfs", "dcf", "irr", "npv",
    # Common acronyms (safe to record as domain-pending)
    "erp", "bi", "etl", "edi", "sap",
    # Tools that would trip the short-name heuristic (≤4 chars, ≥2 vowels)
    "api", "apis",
}

# ── Generic English words — too vague to be domain skills ─────────────────────

_GENERIC_ENGLISH: Set[str] = {
    # Prepositions / temporal (not in FR stopwords)
    "after", "before", "during", "across", "along", "among", "around",
    "against", "between", "beyond", "through", "within", "without",
    "towards", "until", "since", "prior", "per",
    # Generic CV verbs / adjectives
    "make", "making", "made", "build", "building", "built",
    "ensure", "ensuring", "worked", "working", "focus", "focused",
    "provide", "support", "handle", "own",
    # Generic adjectives
    "advanced", "aligned", "certain", "effective", "effectively",
    "general", "large", "likely", "long", "multiple", "new", "next",
    "other", "right", "same", "several", "specific", "unique", "various",
    # Generic nouns
    "aspect", "aspects", "issue", "issues", "key", "part", "parts",
    "place", "year", "years", "month",
    # Generic adverbs / pronouns
    "also", "often", "just", "rather", "especially", "including",
    "following", "given", "related", "relevant", "current",
    # Generic tech words (too vague alone)
    "system", "systems", "tool", "process", "processes",
    "report", "reports", "using", "used",
}

# ── Email / domain noise ───────────────────────────────────────────────────────

_EMAIL_NOISE: Set[str] = {
    "gmail", "yahoo", "hotmail", "outlook", "orange", "wanadoo", "free",
    "laposte", "sfr",
    # TLDs standing alone as tokens
    "com", "fr", "net", "org", "eu", "io", "co", "uk", "de",
}

# ── URL and handle patterns ────────────────────────────────────────────────────

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_HANDLE_DIGITS_RE = re.compile(r"^[a-z]+\d{2,}[a-z]*$|^[a-z]*\d{2,}[a-z]+$", re.IGNORECASE)

# ── Minimal FR location names (common in CV headers) ─────────────────────────

_LOCATION_NAMES_FR: Set[str] = {
    "paris", "lyon", "marseille", "bordeaux", "lille", "havre", "nantes",
    "toulouse", "rennes", "strasbourg", "nice", "grenoble", "montpellier",
    "rouen", "toulon", "brest", "reims", "limoges", "amiens",
}

# ── Short alpha name heuristic helpers ────────────────────────────────────────

_SHORT_ALPHA_NAME = re.compile(r"^[a-z]{3,4}$")
_VOWELS = frozenset("aeiou")


def _vowel_count(s: str) -> int:
    return sum(1 for c in s if c in _VOWELS)


# ── Reason codes ──────────────────────────────────────────────────────────────

_DOMAIN_PENDING = "DOMAIN_PENDING"
_REJECT = "REJECT"
RC_ALLOWLIST = "ALLOWLIST"
RC_TOO_SHORT = "REJECT_TOO_SHORT"
RC_WORD_COUNT = "REJECT_WORD_COUNT"
RC_NUMBER = "REJECT_NUMBER"
RC_STOPWORD = "REJECT_STOPWORD"
RC_GENERIC = "REJECT_GENERIC"
RC_SOFT_SKILL = "REJECT_SOFT_SKILL"
RC_EMAIL = "REJECT_EMAIL"
RC_URL = "REJECT_URL"
RC_HANDLE = "REJECT_NAME_HANDLE"


# ── classify_token — single entry point for token validation ──────────────────

def classify_token(token: str, cluster: Optional[str] = None) -> Tuple[str, str]:
    """
    Classify a candidate token.  Pure function — no DB access, no side effects.

    Returns (decision, reason_code) where:
      decision   = "DOMAIN_PENDING"  → valid, should go to cluster library
                 = "REJECT"          → noise token
      reason_code = "ALLOWLIST"            (guaranteed DOMAIN_PENDING)
                  | "REJECT_TOO_SHORT"
                  | "REJECT_WORD_COUNT"
                  | "REJECT_NUMBER"
                  | "REJECT_STOPWORD"
                  | "REJECT_GENERIC"
                  | "REJECT_SOFT_SKILL"
                  | "REJECT_EMAIL"
                  | "REJECT_URL"
                  | "REJECT_NAME_HANDLE"

    Rule order:
      1. Normalize (strip surrounding punct, NFKD lower)
      2. Allowlist guard  ← checked BEFORE any rejection
      3. URL / email / handle patterns
      4. Length / word-count / number
      5. Location names
      6. Short alpha name heuristic  (≤4 chars, all-alpha, ≥2 vowels → likely a name)
      7. Stopwords
      8. Generic English words
      9. Soft-skill patterns
    """
    if not token or not token.strip():
        return _REJECT, RC_TOO_SHORT

    # 1. Normalize
    norm = _nfkd_lower(token)
    if not norm:
        return _REJECT, RC_TOO_SHORT

    # 2. Allowlist → force DOMAIN_PENDING regardless of other rules
    if norm in _TOOL_ALLOWLIST:
        return _DOMAIN_PENDING, RC_ALLOWLIST

    # 3a. URL
    if _URL_RE.search(token):
        return _REJECT, RC_URL

    # 3b. Email (@ sign)
    if "@" in token:
        return _REJECT, RC_EMAIL

    # 3c. Email noise words (gmail, com, etc.)
    if norm in _EMAIL_NOISE:
        return _REJECT, RC_EMAIL

    # 3d. Handle with digits (e.g. akinguentas13)
    if _HANDLE_DIGITS_RE.match(norm):
        return _REJECT, RC_HANDLE

    # 4a. Length
    if len(norm) < 2 or len(norm) > 50:
        return _REJECT, RC_TOO_SHORT

    # 4b. Word count
    words = norm.split()
    if not (1 <= len(words) <= 4):
        return _REJECT, RC_WORD_COUNT

    # 4c. Number-only
    if _NUMBER_ONLY.match(norm):
        return _REJECT, RC_NUMBER

    # 5. Known FR locations
    if norm in _LOCATION_NAMES_FR:
        return _REJECT, RC_HANDLE

    # 6. Stopwords
    if norm in _STOPWORDS:
        return _REJECT, RC_STOPWORD
    if len(words) == 1 and words[0] in _STOPWORDS:
        return _REJECT, RC_STOPWORD

    # 7. Generic English words  ← before name heuristic so "make/after/ensure" get right code
    if norm in _GENERIC_ENGLISH:
        return _REJECT, RC_GENERIC

    # 8. Short alpha name heuristic: ≤4 all-alpha chars with ≥2 vowels → likely a name
    if _SHORT_ALPHA_NAME.match(norm) and _vowel_count(norm) >= 2:
        return _REJECT, RC_HANDLE

    # 9. Soft-skill patterns (case-insensitive, checked on original token)
    for pat in _SOFT_SKILL_PATTERNS:
        if pat.search(token):
            return _REJECT, RC_SOFT_SKILL

    return _DOMAIN_PENDING, "VALID"

# ── Schema ────────────────────────────────────────────────────────────────────

_SQL_CREATE_SKILLS = """
CREATE TABLE IF NOT EXISTS cluster_domain_skills (
    id                TEXT PRIMARY KEY,
    cluster           TEXT NOT NULL,
    token_normalized  TEXT NOT NULL,
    occurrences_cv    INTEGER DEFAULT 0,
    occurrences_offers INTEGER DEFAULT 0,
    first_seen_at     TEXT NOT NULL,
    last_seen_at      TEXT NOT NULL,
    status            TEXT DEFAULT 'PENDING',
    source            TEXT DEFAULT 'CV',
    validation_score  REAL DEFAULT 0.0,
    UNIQUE(cluster, token_normalized)
)
"""

_SQL_CREATE_META = """
CREATE TABLE IF NOT EXISTS cluster_library_meta (
    key        TEXT PRIMARY KEY,
    value_int  INTEGER DEFAULT 0
)
"""

_META_KEYS = ("llm_calls_total", "llm_calls_avoided", "new_skills_via_offers")


# ── Normalisation helpers ─────────────────────────────────────────────────────

# Surrounding punctuation to strip (never internal – preserves C#, S&OP, etc.)
_STRIP_SURROUND = re.compile(r"^[\s,.;:()\[\]{}<>/\\|\-_]+|[\s,.;:()\[\]{}<>/\\|\-_]+$")


def _nfkd_lower(s: str) -> str:
    """Strip surrounding punct, NFKD-decompose, remove combining chars, lowercase."""
    s = _STRIP_SURROUND.sub("", s.strip())
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def normalize_token(token: str) -> str:
    """Public normalisation for display / reporting (same as DB key function)."""
    return _nfkd_lower(token)


def _make_id(cluster: str, token_norm: str) -> str:
    return hashlib.md5(f"{cluster}|{token_norm}".encode()).hexdigest()[:16]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ── ClusterLibraryStore ───────────────────────────────────────────────────────

class ClusterLibraryStore:
    """
    Thread-safe SQLite store for cluster domain skills.

    Pass db_path=":memory:" for in-process testing (no file I/O).
    Each thread gets its own connection (threading.local).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_path = os.getenv("ELEVIA_CLUSTER_LIBRARY_DB", str(_DEFAULT_DB))
        self._db_path = db_path
        self._lock = threading.RLock()
        # Per-cluster active-skills cache
        self._active_cache: Dict[str, List[str]] = {}
        self._cache_dirty: Set[str] = set()       # clusters whose cache needs refresh
        self._local = threading.local()

        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Connection management ─────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self._db_path, check_same_thread=False, timeout=5)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=3000")
            c.row_factory = sqlite3.Row
            self._local.conn = c
        return c

    def _init_db(self) -> None:
        with self._lock:
            conn = self._conn()
            conn.execute(_SQL_CREATE_SKILLS)
            conn.execute(_SQL_CREATE_META)
            for key in _META_KEYS:
                conn.execute(
                    "INSERT OR IGNORE INTO cluster_library_meta (key, value_int) VALUES (?, 0)",
                    (key,),
                )
            conn.commit()

    # ── Pure validation (no DB) ───────────────────────────────────────────────

    def validate_token(self, token: str, cluster: Optional[str] = None) -> bool:
        """
        Deterministic token validation. No DB access. No side effects.

        Returns True iff token is a valid non-ESCO skill candidate.
        Delegates to module-level classify_token() — kept for backwards compat.
        """
        decision, _ = classify_token(token, cluster)
        return decision == _DOMAIN_PENDING

    # ── Record operations ─────────────────────────────────────────────────────

    def record_cv_token(self, cluster: str, token: str) -> str:
        """
        Record a token observed in a CV.
        Returns: "REJECTED" | "PENDING" | "ACTIVE"
        """
        if not self.validate_token(token, cluster):
            return "REJECTED"

        norm = _nfkd_lower(token)
        tid = _make_id(cluster, norm)
        now = _utcnow()

        with self._lock:
            conn = self._conn()
            row = conn.execute(
                "SELECT * FROM cluster_domain_skills WHERE id=?", (tid,)
            ).fetchone()

            if row:
                new_cv = row["occurrences_cv"] + 1
                src = "BOTH" if row["occurrences_offers"] > 0 else "CV"
                conn.execute(
                    "UPDATE cluster_domain_skills SET occurrences_cv=?, last_seen_at=?, source=? WHERE id=?",
                    (new_cv, now, src, tid),
                )
            else:
                conn.execute(
                    """INSERT INTO cluster_domain_skills
                       (id, cluster, token_normalized, occurrences_cv, occurrences_offers,
                        first_seen_at, last_seen_at, status, source, validation_score)
                       VALUES (?, ?, ?, 1, 0, ?, ?, 'PENDING', 'CV', 0.5)""",
                    (tid, cluster, norm, now, now),
                )
            conn.commit()

            # Re-fetch and apply activation
            row = conn.execute("SELECT * FROM cluster_domain_skills WHERE id=?", (tid,)).fetchone()
            return self._maybe_activate(conn, row, cluster)

    def record_offer_token(self, cluster: str, token: str) -> str:
        """
        Record a token observed in an offer.
        Returns: "REJECTED" | "PENDING" | "ACTIVE"
        """
        if not self.validate_token(token, cluster):
            return "REJECTED"

        norm = _nfkd_lower(token)
        tid = _make_id(cluster, norm)
        now = _utcnow()
        is_new = False

        with self._lock:
            conn = self._conn()
            row = conn.execute(
                "SELECT * FROM cluster_domain_skills WHERE id=?", (tid,)
            ).fetchone()

            if row:
                new_off = row["occurrences_offers"] + 1
                src = "BOTH" if row["occurrences_cv"] > 0 else "OFFER"
                conn.execute(
                    "UPDATE cluster_domain_skills SET occurrences_offers=?, last_seen_at=?, source=? WHERE id=?",
                    (new_off, now, src, tid),
                )
            else:
                is_new = True
                conn.execute(
                    """INSERT INTO cluster_domain_skills
                       (id, cluster, token_normalized, occurrences_cv, occurrences_offers,
                        first_seen_at, last_seen_at, status, source, validation_score)
                       VALUES (?, ?, ?, 0, 1, ?, ?, 'PENDING', 'OFFER', 0.5)""",
                    (tid, cluster, norm, now, now),
                )
                conn.execute(
                    "UPDATE cluster_library_meta SET value_int = value_int + 1 WHERE key='new_skills_via_offers'"
                )
            conn.commit()

            row = conn.execute("SELECT * FROM cluster_domain_skills WHERE id=?", (tid,)).fetchone()
            return self._maybe_activate(conn, row, cluster)

    def _maybe_activate(self, conn: sqlite3.Connection, row: sqlite3.Row, cluster: str) -> str:
        """Apply activation rules. Mutates DB if conditions met. Returns new status."""
        if row["status"] == "ACTIVE":
            return "ACTIVE"

        occ_cv = row["occurrences_cv"]
        occ_off = row["occurrences_offers"]

        should_activate = (
            (occ_cv >= ACTIVATION_CV_MIN and occ_off >= ACTIVATION_OFFER_MIN)
            or (occ_off >= ACTIVATION_OFFER_ONLY_MIN)
        )

        if should_activate:
            conn.execute(
                "UPDATE cluster_domain_skills SET status='ACTIVE', validation_score=1.0 WHERE id=?",
                (row["id"],),
            )
            conn.commit()
            # Invalidate cache for this cluster
            self._cache_dirty.add(cluster)
            self._active_cache.pop(cluster, None)
            return "ACTIVE"

        return row["status"]

    # ── Read operations ───────────────────────────────────────────────────────

    def get_active_skills(self, cluster: str) -> List[str]:
        """Return sorted list of ACTIVE token_normalized for a cluster (cached)."""
        with self._lock:
            if cluster not in self._cache_dirty and cluster in self._active_cache:
                return list(self._active_cache[cluster])

            conn = self._conn()
            rows = conn.execute(
                "SELECT token_normalized FROM cluster_domain_skills WHERE cluster=? AND status='ACTIVE' ORDER BY token_normalized",
                (cluster,),
            ).fetchall()
            tokens = [r["token_normalized"] for r in rows]
            self._active_cache[cluster] = tokens
            self._cache_dirty.discard(cluster)
            return list(tokens)

    def get_all_skills(
        self,
        status: Optional[str] = None,
        cluster: Optional[str] = None,
    ) -> List[ClusterDomainSkill]:
        with self._lock:
            conn = self._conn()
            q = "SELECT * FROM cluster_domain_skills WHERE 1=1"
            params: List = []
            if status:
                q += " AND status=?"
                params.append(status)
            if cluster:
                q += " AND cluster=?"
                params.append(cluster)
            q += " ORDER BY cluster, token_normalized"
            rows = conn.execute(q, params).fetchall()
            return [_row_to_skill(r) for r in rows]

    # ── Meta counters ─────────────────────────────────────────────────────────

    def increment_meta(self, key: str, delta: int = 1) -> None:
        if key not in _META_KEYS:
            return
        with self._lock:
            conn = self._conn()
            conn.execute(
                "UPDATE cluster_library_meta SET value_int = value_int + ? WHERE key=?",
                (delta, key),
            )
            conn.commit()

    def _get_meta(self) -> Dict[str, int]:
        conn = self._conn()
        return {
            r["key"]: r["value_int"]
            for r in conn.execute("SELECT key, value_int FROM cluster_library_meta").fetchall()
        }

    # ── Metrics ───────────────────────────────────────────────────────────────

    def get_metrics(self) -> ClusterLibraryMetrics:
        with self._lock:
            conn = self._conn()
            clusters = [
                r["cluster"]
                for r in conn.execute(
                    "SELECT DISTINCT cluster FROM cluster_domain_skills ORDER BY cluster"
                ).fetchall()
            ]

            active_per: Dict[str, int] = {}
            pending_per: Dict[str, int] = {}
            drift_per: Dict[str, float] = {}

            for c in clusters:
                active = conn.execute(
                    "SELECT COUNT(*) AS n FROM cluster_domain_skills WHERE cluster=? AND status='ACTIVE'",
                    (c,),
                ).fetchone()["n"]
                pending = conn.execute(
                    "SELECT COUNT(*) AS n FROM cluster_domain_skills WHERE cluster=? AND status='PENDING'",
                    (c,),
                ).fetchone()["n"]
                active_per[c] = active
                pending_per[c] = pending
                drift_per[c] = round(pending / (active + 1), 3)

            meta = self._get_meta()
            return ClusterLibraryMetrics(
                generated_at=_utcnow(),
                total_clusters=len(clusters),
                active_per_cluster=active_per,
                pending_per_cluster=pending_per,
                llm_calls_total=meta.get("llm_calls_total", 0),
                llm_calls_avoided=meta.get("llm_calls_avoided", 0),
                new_skills_via_offers=meta.get("new_skills_via_offers", 0),
                drift_index_per_cluster=drift_per,
            )

    def generate_market_radar(self, top_n: int = 10) -> MarketRadarReport:
        with self._lock:
            conn = self._conn()
            clusters = [
                r["cluster"]
                for r in conn.execute(
                    "SELECT DISTINCT cluster FROM cluster_domain_skills ORDER BY cluster"
                ).fetchall()
            ]

            top_emerging: Dict[str, List[str]] = {}
            new_active: List[str] = []

            for c in clusters:
                # Emerging = PENDING with highest offer occurrences
                rows = conn.execute(
                    """SELECT token_normalized FROM cluster_domain_skills
                       WHERE cluster=? AND status='PENDING'
                       ORDER BY occurrences_offers DESC, occurrences_cv DESC
                       LIMIT ?""",
                    (c, top_n),
                ).fetchall()
                if rows:
                    top_emerging[c] = [r["token_normalized"] for r in rows]

                # Recently activated (last 100)
                rows = conn.execute(
                    """SELECT token_normalized FROM cluster_domain_skills
                       WHERE cluster=? AND status='ACTIVE'
                       ORDER BY last_seen_at DESC LIMIT ?""",
                    (c, top_n),
                ).fetchall()
                new_active.extend(r["token_normalized"] for r in rows)

            # All pending
            pending_rows = conn.execute(
                "SELECT token_normalized FROM cluster_domain_skills WHERE status='PENDING' ORDER BY token_normalized LIMIT 200"
            ).fetchall()

            return MarketRadarReport(
                generated_at=_utcnow(),
                top_emerging_per_cluster=top_emerging,
                new_active_skills=new_active[:50],
                pending_skills=[r["token_normalized"] for r in pending_rows],
                rejected_tokens=[],   # validated at record time — not stored
            )

    def save_reports(self) -> None:
        """Write metrics + radar to JSON files in data/reports/."""
        try:
            _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            metrics = self.get_metrics()
            radar = self.generate_market_radar()
            (_REPORTS_DIR / "cluster_library_metrics.json").write_text(
                json.dumps(metrics.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (_REPORTS_DIR / "market_radar_report.json").write_text(
                json.dumps(radar.model_dump(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("cluster_library.save_reports failed: %s", exc)


def _row_to_skill(r: sqlite3.Row) -> ClusterDomainSkill:
    return ClusterDomainSkill(
        id=r["id"],
        cluster=r["cluster"],
        token_normalized=r["token_normalized"],
        occurrences_cv=r["occurrences_cv"],
        occurrences_offers=r["occurrences_offers"],
        first_seen_at=r["first_seen_at"],
        last_seen_at=r["last_seen_at"],
        status=r["status"],
        source=r["source"],
        validation_score=r["validation_score"],
    )


# ── Module-level singleton ────────────────────────────────────────────────────

_store: Optional[ClusterLibraryStore] = None
_singleton_lock = threading.Lock()


def get_library(db_path: Optional[str] = None) -> ClusterLibraryStore:
    """Return the process-level singleton store (lazy init)."""
    global _store
    if _store is None:
        with _singleton_lock:
            if _store is None:
                _store = ClusterLibraryStore(db_path=db_path)
    return _store


def reset_library(db_path: Optional[str] = None) -> ClusterLibraryStore:
    """Create a fresh store and replace the singleton. Used in tests."""
    global _store
    with _singleton_lock:
        _store = ClusterLibraryStore(db_path=db_path)
    return _store
