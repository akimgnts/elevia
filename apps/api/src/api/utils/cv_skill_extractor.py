"""cv_skill_extractor — Extract and map CV skills to canonical dictionary.

CV → skills → canonical_aliases → canonical_id mapping.
Same extraction logic as V3 offer_skills, optimized for CV text.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Dict, List, Set, Tuple


def normalize_skill(label: str) -> str:
    """Normalize skill label for matching."""
    s = label.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\s\-_/]+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')


# Keywords for V3-style skill extraction (CORE_METIER priority)
SKILL_KEYWORDS = {
    # Programming
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "golang", "rust",
    "kotlin", "scala", "perl", "r language", "matlab", "vba",

    # Frameworks/Tools (Tech)
    "react", "angular", "vue", "node", "express", "django", "flask", "spring", "hibernate",
    "kafka", "spark", "hadoop", "tensorflow", "pytorch", "scikit-learn",

    # Databases
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "oracle", "cassandra",
    "firebase", "dynamodb",

    # Cloud/DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "gitlab", "github", "terraform",
    "ansible", "puppet", "chef",

    # Data/Analytics
    "data", "analytics", "bi", "tableau", "power_bi", "powerbi", "looker", "analytics",
    "machine_learning", "deep_learning", "nlp", "computer_vision",

    # Tools
    "excel", "jira", "confluence", "salesforce", "sap", "erp", "crm",
    "figma", "sketch", "adobe", "photoshop", "illustrator", "premier",
    "git", "gitlab", "github", "bitbucket",

    # Infrastructure
    "linux", "windows", "macos", "unix", "apache", "nginx", "iis",

    # Business/Sales
    "sales", "prospecting", "negotiation", "client_relationship", "business_development",
    "account_management", "lead_generation", "crm",

    # Project/Operations
    "project_management", "agile", "scrum", "kanban", "waterfall",
    "process_improvement", "lean", "six_sigma",

    # Finance
    "accounting", "finance", "budget", "forecast", "audit", "tax", "treasury",

    # HR
    "recruitment", "talent_acquisition", "hr", "payroll", "compensation", "training",

    # Languages
    "english", "french", "spanish", "german", "italian", "portuguese", "chinese", "japanese",
    "arabic", "russian", "dutch",

    # Domain/Industry
    "manufacturing", "automotive", "aerospace", "pharma", "healthcare", "finance", "retail",
    "energy", "construction", "agriculture", "logistics", "supply_chain",

    # Soft skills
    "communication", "leadership", "teamwork", "problem_solving", "critical_thinking",
    "time_management", "stress_management", "adaptability", "creativity", "innovation",
}

# Normalized keyword set
SKILL_KEYWORDS_NORMALIZED = {normalize_skill(kw) for kw in SKILL_KEYWORDS}


def extract_skills_from_cv(cv_text: str, max_skills: int = 20) -> List[str]:
    """
    Extract skills from CV text using keyword matching.

    Returns list of skill labels (non-normalized, as found in text).
    """
    if not cv_text:
        return []

    # Tokenize: split on whitespace + punctuation (but keep skills together)
    # Remove URLs, emails, etc.
    text = cv_text.lower()
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\S+@\S+', '', text)

    # Split on whitespace
    tokens = re.split(r'[\s\,\;\.\:\(\)\[\]\{\}]+', text)
    tokens = [t.strip() for t in tokens if t.strip()]

    found_skills = []
    seen = set()

    for token in tokens:
        # Skip short tokens, numbers, etc.
        if len(token) < 2 or token.isdigit():
            continue

        norm_token = normalize_skill(token)

        # Skip if already found (dedup)
        if norm_token in seen:
            continue

        # Check if token matches a known skill keyword
        if norm_token in SKILL_KEYWORDS_NORMALIZED:
            found_skills.append(token)
            seen.add(norm_token)

            if len(found_skills) >= max_skills:
                break

    return found_skills


def word_overlap_similarity(s1: str, s2: str) -> float:
    """Simple word-level overlap score [0-1]."""
    words1 = set(normalize_skill(s1).split('_'))
    words2 = set(normalize_skill(s2).split('_'))
    if not words1 or not words2:
        return 0.0
    overlap = len(words1 & words2)
    union = len(words1 | words2)
    return overlap / union if union > 0 else 0.0


def map_cv_skills_to_canonical(
    cv_skills: List[str],
    conn: sqlite3.Connection,
    fuzzy_threshold: float = 0.6,
) -> Dict[str, Tuple[str, str]]:
    """
    Map CV skills to canonical_ids via canonical_aliases.

    First tries exact match, then fuzzy match if enabled.
    Returns: {skill_label: (canonical_id, canonical_label)}
    """
    if not cv_skills:
        return {}

    cursor = conn.cursor()
    mappings = {}

    # Load all canonical skills once for fuzzy matching
    cursor.execute("SELECT canonical_id, label FROM canonical_skills")
    canonical_lookup = {row[1]: row[0] for row in cursor.fetchall()}
    canonical_labels = list(canonical_lookup.keys())

    for skill in cv_skills:
        norm_skill = normalize_skill(skill)

        # Try exact match in canonical_aliases
        cursor.execute("""
            SELECT ca.canonical_id, cs.label
            FROM canonical_aliases ca
            JOIN canonical_skills cs ON ca.canonical_id = cs.canonical_id
            WHERE ca.alias = ? OR
                  REPLACE(LOWER(ca.alias), ' ', '_') = ?
            LIMIT 1
        """, (skill, norm_skill))

        row = cursor.fetchone()
        if row:
            mappings[skill] = (row[0], row[1])
            continue

        # Fuzzy match: find best matching canonical skill by similarity
        best_match = None
        best_score = fuzzy_threshold

        for canonical_label in canonical_labels:
            score = word_overlap_similarity(skill, canonical_label)
            if score > best_score:
                best_score = score
                best_match = (canonical_lookup[canonical_label], canonical_label)

        if best_match:
            mappings[skill] = best_match

    return mappings


def build_cv_canonical_skills(
    cv_skills: List[str],
    mappings: Dict[str, Tuple[str, str]],
    conn: sqlite3.Connection,
) -> Tuple[List[Dict], Dict]:
    """
    Build canonical skills response with breakdown by type.

    Returns: (canonical_skills_list, breakdown_by_type)
    """
    if not mappings:
        return [], {
            "core_metier": [],
            "tool": [],
            "context": [],
            "unmapped": cv_skills,
        }

    cursor = conn.cursor()
    canonical_skills_list = []
    breakdown = {
        "core_metier": [],
        "tool": [],
        "context": [],
        "unmapped": [],
    }

    for skill, (canonical_id, canonical_label) in mappings.items():
        # Fetch full skill details
        cursor.execute("""
            SELECT canonical_id, label, skill_type, domain_tag, occurrences
            FROM canonical_skills
            WHERE canonical_id = ?
        """, (canonical_id,))

        row = cursor.fetchone()
        if row:
            skill_dict = {
                "canonical_id": row[0],
                "label": row[1],
                "skill_type": row[2],
                "domain_tag": row[3],
                "occurrences": row[4],
                "cv_source": skill,  # Original CV text
            }
            canonical_skills_list.append(skill_dict)

            # Breakdown by type
            skill_type = row[2]
            if skill_type == "CORE_METIER":
                breakdown["core_metier"].append(skill_dict)
            elif skill_type == "TOOL":
                breakdown["tool"].append(skill_dict)
            elif skill_type == "CONTEXT":
                breakdown["context"].append(skill_dict)

    # Track unmapped skills
    mapped_skills = set(mappings.keys())
    breakdown["unmapped"] = [s for s in cv_skills if s not in mapped_skills]

    return canonical_skills_list, breakdown


def extract_and_map_cv_skills(
    cv_text: str,
    conn: sqlite3.Connection,
    max_skills: int = 20,
) -> Tuple[List[Dict], Dict]:
    """
    End-to-end CV skill extraction + mapping.

    Returns: (canonical_skills_list, breakdown_dict)
    """
    # Step 1: Extract skills from CV text
    cv_skills = extract_skills_from_cv(cv_text, max_skills=max_skills)

    # Step 2: Map to canonical via aliases
    mappings = map_cv_skills_to_canonical(cv_skills, conn)

    # Step 3: Build response
    canonical_skills, breakdown = build_cv_canonical_skills(cv_skills, mappings, conn)

    return canonical_skills, breakdown
