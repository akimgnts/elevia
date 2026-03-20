from __future__ import annotations

from compass.canonical.canonical_store import normalize_canonical_key
from .title_normalization import infer_title_role_family

ROLE_FAMILY_TO_SECTOR = {
    "data_analytics": "DATA_IT",
    "software_engineering": "DATA_IT",
    "cybersecurity": "DATA_IT",
    "product_management": "MARKETING_SALES",
    "project_management": "MARKETING_SALES",
    "sales": "MARKETING_SALES",
    "marketing": "MARKETING_SALES",
    "finance": "FINANCE_LEGAL",
    "legal": "FINANCE_LEGAL",
    "supply_chain": "SUPPLY_OPS",
    "operations": "SUPPLY_OPS",
    "hr": "ADMIN_HR",
    "design": "MARKETING_SALES",
    "consulting": "OTHER",
    "customer_success": "MARKETING_SALES",
    "engineering": "ENGINEERING_INDUSTRY",
    "other": "OTHER",
}

_EXACT_OCCUPATION_MAP = {
    "15-1252.00": "software_engineering",
    "15-1254.00": "software_engineering",
    "15-2051.00": "data_analytics",
    "15-2051.01": "data_analytics",
    "15-2041.00": "data_analytics",
    "15-1212.00": "cybersecurity",
    "11-2021.00": "marketing",
    "11-2022.00": "sales",
    "13-1111.00": "finance",
    "13-1075.00": "legal",
    "23-1011.00": "legal",
    "23-2011.00": "legal",
    "13-1081.00": "supply_chain",
    "13-1082.00": "project_management",
    "11-1021.00": "operations",
    "13-1071.00": "hr",
    "17-2112.00": "engineering",
}

_ROLE_PRIORITY = {
    "product_management": 6,
    "project_management": 5,
    "software_engineering": 5,
    "data_analytics": 5,
    "finance": 4,
    "legal": 4,
    "sales": 4,
    "marketing": 4,
    "supply_chain": 4,
    "operations": 4,
    "hr": 4,
    "cybersecurity": 4,
    "engineering": 3,
    "design": 2,
    "consulting": 1,
    "customer_success": 1,
    "other": 0,
}

def map_onet_occupation_to_role_family(onet_code: str | None, occupation_title: str | None = None) -> str:
    if onet_code and onet_code in _EXACT_OCCUPATION_MAP:
        return _EXACT_OCCUPATION_MAP[onet_code]

    return infer_role_family_from_title(occupation_title)


def infer_role_family_from_title(title: str | None) -> str:
    return infer_title_role_family(normalize_canonical_key(title or ""))


def role_family_priority(role_family: str | None) -> int:
    return _ROLE_PRIORITY.get(role_family or "other", 0)


def map_role_family_to_sector(role_family: str | None) -> str:
    return ROLE_FAMILY_TO_SECTOR.get(role_family or "other", "OTHER")
