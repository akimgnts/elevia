from __future__ import annotations

ROLE_FAMILY_DEFINITIONS: list[dict[str, object]] = [
    {"key": "data_analytics", "label": "Data & Analytics", "aliases": ["data analytics", "data analyst", "data science"]},
    {"key": "software_engineering", "label": "Software Engineering", "aliases": ["software engineering", "software developer", "software engineer"]},
    {"key": "cybersecurity", "label": "Cybersecurity", "aliases": ["cybersecurity", "security engineering"]},
    {"key": "product_management", "label": "Product Management", "aliases": ["product management", "product manager", "product owner"]},
    {"key": "project_management", "label": "Project Management", "aliases": ["project management", "project manager"]},
    {"key": "sales", "label": "Sales", "aliases": ["sales", "business development"]},
    {"key": "marketing", "label": "Marketing", "aliases": ["marketing", "growth marketing"]},
    {"key": "finance", "label": "Finance", "aliases": ["finance", "financial analysis"]},
    {"key": "legal", "label": "Legal", "aliases": ["legal", "juridical", "juriste"]},
    {"key": "supply_chain", "label": "Supply Chain", "aliases": ["supply chain", "logistics", "procurement"]},
    {"key": "operations", "label": "Operations", "aliases": ["operations", "business operations"]},
    {"key": "hr", "label": "Human Resources", "aliases": ["hr", "human resources", "people ops"]},
    {"key": "design", "label": "Design", "aliases": ["design", "designer", "ux design"]},
    {"key": "consulting", "label": "Consulting", "aliases": ["consulting", "consultant"]},
    {"key": "customer_success", "label": "Customer Success", "aliases": ["customer success"]},
    {"key": "engineering", "label": "Engineering", "aliases": ["engineering", "industrial engineering", "mechanical engineering"]},
    {"key": "other", "label": "Other", "aliases": ["other", "generalist"]},
]

SECTOR_DEFINITIONS: list[dict[str, object]] = [
    {"key": "DATA_IT", "label": "Data / IT", "aliases": ["data it", "data / it"]},
    {"key": "MARKETING_SALES", "label": "Marketing & Sales", "aliases": ["marketing sales", "marketing & sales"]},
    {"key": "FINANCE_LEGAL", "label": "Finance & Legal", "aliases": ["finance legal", "finance & legal"]},
    {"key": "SUPPLY_OPS", "label": "Supply & Ops", "aliases": ["supply ops", "supply & ops"]},
    {"key": "ENGINEERING_INDUSTRY", "label": "Engineering", "aliases": ["engineering industry", "engineering"]},
    {"key": "ADMIN_HR", "label": "HR & Admin", "aliases": ["admin hr", "hr admin"]},
    {"key": "OTHER", "label": "Other", "aliases": ["other"]},
]
