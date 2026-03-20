from compass.roles.role_family_map import (
    infer_role_family_from_title,
    map_onet_occupation_to_role_family,
    map_role_family_to_sector,
)


def test_exact_onet_code_maps_to_stable_role_family():
    assert map_onet_occupation_to_role_family("15-1252.00", "Software Developer") == "software_engineering"
    assert map_role_family_to_sector("software_engineering") == "DATA_IT"


def test_consulting_no_longer_projects_to_finance_legal_sector():
    assert infer_role_family_from_title("consultant") == "consulting"
    assert map_role_family_to_sector("consulting") == "OTHER"


def test_title_family_inference_handles_data_engineer_and_business_developer_precedence():
    assert infer_role_family_from_title("data engineer") == "data_analytics"
    assert infer_role_family_from_title("business developer") == "sales"
