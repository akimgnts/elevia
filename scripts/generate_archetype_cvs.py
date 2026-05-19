from __future__ import annotations

from pathlib import Path


OUTPUT_ROOT = Path("exports") / "archetype_cvs"

CENTRAL_SECTORS = {
    "FINANCE_CONTROL": {
        "slug": "finance_control",
    },
    "SALES_BUSINESS_DEVELOPMENT": {
        "slug": "sales_business_development",
    },
    "SUPPLY_CHAIN_PROCUREMENT": {
        "slug": "supply_chain_procurement",
    },
    "OPERATIONS_PROJECT_PMO": {
        "slug": "operations_project_pmo",
    },
    "HR_TALENT_OPERATIONS": {
        "slug": "hr_talent_operations",
    },
}

HYBRID_SECTORS = {
    "FINANCE_BI": {
        "slug": "finance_bi",
        "min_offer_count": 10,
    },
    "SUPPLY_OPERATIONS": {
        "slug": "supply_operations",
        "min_offer_count": 10,
    },
    "HR_BUSINESS": {
        "slug": "hr_business",
        "min_offer_count": 10,
    },
}


def _build_output_path(output_root: Path, sector_type: str, sector_slug: str, suffix: str) -> Path:
    if sector_type not in {"central", "hybrid"}:
        raise ValueError(f"unsupported sector_type: {sector_type}")
    return Path(output_root) / sector_type / f"{sector_slug}{suffix}"


def build_markdown_output_path(
    output_root: Path = OUTPUT_ROOT,
    sector_type: str = "central",
    sector_slug: str = "",
) -> Path:
    return _build_output_path(output_root, sector_type, sector_slug, ".md")


def build_json_output_path(
    output_root: Path = OUTPUT_ROOT,
    sector_type: str = "central",
    sector_slug: str = "",
) -> Path:
    return _build_output_path(output_root, sector_type, sector_slug, ".json")
