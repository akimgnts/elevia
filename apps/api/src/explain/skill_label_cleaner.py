"""skill_label_cleaner — Clean raw skill labels for readable explanations.

Transform raw skill labels (canonical IDs, snake_case, etc.) into
human-readable French text suitable for user-facing explanations.

Deterministic, no AI. 100% rule-based with manual mappings.
"""

from typing import Optional


# Blacklisted skills — never display, return None
SKILL_BLACKLIST = {
    "automate",
    "clients",
    "support",
    "process",
    "operations",
    "management",  # isolated
    "communication",  # isolated
    "autres",
    "divers",
    "misc",
    "general",
}

# Canonical ID → human-readable French label mapping
CANONICAL_MAPPING = {
    "metier:data_analysis": "Analyse de données",
    "metier:data_analyst": "Analyse de données",
    "metier:machine_learning": "Machine learning",
    "metier:project_management": "Gestion de projet",
    "metier:business_development": "Développement commercial",
    "metier:customer_relationship_management": "Gestion de la relation client",
    "metier:crm": "Gestion de la relation client",
    "metier:sales": "Ventes",
    "metier:marketing": "Marketing",
    "metier:finance": "Finance",
    "metier:accounting": "Comptabilité",
    "metier:hr": "Ressources humaines",
    "metier:legal": "Juridique",
    "metier:supply_chain": "Gestion de la chaîne d'approvisionnement",
    "metier:operations": "Opérations",
    "metier:quality": "Assurance qualité",
    # Tech
    "metier:python": "Python",
    "metier:java": "Java",
    "metier:javascript": "JavaScript",
    "metier:csharp": "C#",
    "metier:sql": "SQL",
    "metier:docker": "Docker",
    "metier:kubernetes": "Kubernetes",
    "metier:aws": "AWS",
    "metier:azure": "Azure",
    "metier:gcp": "Google Cloud Platform",
    "metier:react": "React",
    "metier:angular": "Angular",
    "metier:vue": "Vue.js",
    "metier:nodejs": "Node.js",
    "metier:git": "Git",
    "metier:jenkins": "Jenkins",
    "metier:terraform": "Terraform",
    "metier:ansible": "Ansible",
    # Hard skills
    "skill:python": "Python",
    "skill:java": "Java",
    "skill:javascript": "JavaScript",
    "skill:sql": "SQL",
    "skill:docker": "Docker",
    "skill:kubernetes": "Kubernetes",
}

# Common skill label → human label (lowercase variants)
LABEL_MAPPING = {
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "csharp": "C#",
    "c#": "C#",
    "c plus plus": "C++",
    "c++": "C++",
    "php": "PHP",
    "ruby": "Ruby",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "r": "R",
    # Database
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "cassandra": "Cassandra",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    # DevOps/Cloud
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "Google Cloud Platform",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "gitlab ci": "GitLab CI",
    "github actions": "GitHub Actions",
    # Frontend
    "react": "React",
    "angular": "Angular",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "svelte": "Svelte",
    "html": "HTML",
    "css": "CSS",
    "sass": "Sass",
    "less": "Less",
    "bootstrap": "Bootstrap",
    "tailwindcss": "Tailwind CSS",
    # Backend/Frameworks
    "nodejs": "Node.js",
    "express": "Express.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "rails": "Ruby on Rails",
    "laravel": "Laravel",
    ".net": ".NET",
    "asp.net": "ASP.NET",
    # Tools/VCS
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "svn": "SVN",
    # Data Science
    "machine learning": "Machine learning",
    "deep learning": "Deep learning",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "scikit learn": "Scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "matplotlib": "Matplotlib",
    "seaborn": "Seaborn",
    # Data/Analytics
    "data analysis": "Analyse de données",
    "data analytics": "Analyse de données",
    "analytics": "Analytics",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "looker": "Looker",
    "apache spark": "Apache Spark",
    "hadoop": "Hadoop",
    # Business
    "project management": "Gestion de projet",
    "agile": "Agile",
    "scrum": "Scrum",
    "kanban": "Kanban",
    "business analysis": "Analyse métier",
    "business intelligence": "Business Intelligence",
    "crm": "Gestion de la relation client",
    "erp": "ERP",
    "sap": "SAP",
    "salesforce": "Salesforce",
    # Other
    "excel": "Excel",
    "powerpoint": "PowerPoint",
    "word": "Word",
    "confluence": "Confluence",
    "jira": "Jira",
    "slack": "Slack",
    "communication": "Communication",
    "leadership": "Leadership",
    "problem solving": "Résolution de problèmes",
}


def _normalize_base(label: str) -> str:
    """Basic normalization: replace _ with space, lowercase."""
    if not label:
        return ""
    # Replace underscore with space
    normalized = label.replace("_", " ")
    # Strip whitespace
    normalized = normalized.strip()
    return normalized


def _is_blacklisted(label: str) -> bool:
    """Check if label is in blacklist."""
    if not label:
        return False
    normalized = label.lower().strip()
    return normalized in SKILL_BLACKLIST


def _semantic_filter(label: str) -> bool:
    """Reject if label doesn't meet semantic criteria.

    Return True if label passes (should be kept).
    """
    if not label:
        return False

    # Too short
    if len(label) < 3:
        return False

    # Single word that's too generic
    words = label.split()
    if len(words) == 1:
        word = words[0].lower()
        # Very generic single words to skip
        if word in {"it", "am", "pm", "qa", "hr", "cto", "ceo", "cfo"}:
            return False

    return True


def clean_skill_label(
    label: str,
    canonical_id: Optional[str] = None,
) -> Optional[str]:
    """Clean raw skill label to human-readable text.

    Args:
        label: Raw skill label (e.g., "automate", "data_analysis", "python")
        canonical_id: Optional canonical skill ID (e.g., "metier:data_analysis")

    Returns:
        Clean label (e.g., "Analyse de données") or None if should be filtered.
    """
    if not label:
        return None

    # Step 1: Check canonical_id mapping first
    if canonical_id:
        canonical_lower = canonical_id.lower().strip()
        if canonical_lower in CANONICAL_MAPPING:
            return CANONICAL_MAPPING[canonical_lower]

    # Step 2: Normalize base
    normalized = _normalize_base(label)
    normalized_lower = normalized.lower()

    # Step 3: Check blacklist
    if _is_blacklisted(normalized):
        return None

    # Step 4: Check label mapping (common skills)
    if normalized_lower in LABEL_MAPPING:
        return LABEL_MAPPING[normalized_lower]

    # Step 5: Semantic filter
    if not _semantic_filter(normalized):
        return None

    # Step 6: Fallback — capitalize first letter of each word
    # Only if it passed all filters
    words = normalized.split()
    capitalized = " ".join(word.capitalize() for word in words if word)

    # Return if result looks reasonable (not empty, not too generic)
    if capitalized and len(capitalized) >= 3:
        return capitalized

    return None


def clean_skill_labels(
    labels: list,
    canonical_ids: Optional[list] = None,
) -> list:
    """Clean multiple skill labels, filtering out None results.

    Args:
        labels: List of raw skill labels
        canonical_ids: Optional list of canonical IDs (parallel to labels)

    Returns:
        List of cleaned labels (None values removed)
    """
    if not labels:
        return []

    if canonical_ids is None:
        canonical_ids = [None] * len(labels)

    cleaned = []
    for label, canonical_id in zip(labels, canonical_ids):
        clean = clean_skill_label(label, canonical_id)
        if clean is not None:
            cleaned.append(clean)

    return cleaned
