from pathlib import Path

from compass.roles.occupation_resolver import DEFAULT_ONET_DB_PATH as OCC_DEFAULT_ONET_DB_PATH
from compass.roles.role_resolver import DEFAULT_ONET_DB_PATH as ROLE_DEFAULT_ONET_DB_PATH


def test_role_default_onet_db_paths_are_repo_absolute():
    expected = Path("apps/api/data/db/onet.db").resolve()
    assert OCC_DEFAULT_ONET_DB_PATH.resolve() == expected
    assert ROLE_DEFAULT_ONET_DB_PATH.resolve() == expected
