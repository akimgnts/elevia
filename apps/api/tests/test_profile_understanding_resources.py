from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


class ProfileUnderstandingResourcesTests(unittest.TestCase):
    def test_resources_endpoint_returns_reference_sections(self) -> None:
        with TestClient(app) as client:
            resp = client.get("/profile-understanding/resources")

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertIn("agent_runtime", data)
        self.assertIn("resources", data)
        self.assertIn("conventions", data)
        self.assertIn("sources", data)
        self.assertTrue(data["agent_runtime"]["external_runtime_expected"])
        self.assertEqual(data["agent_runtime"]["resource_contract_version"], "v3")
        self.assertIn("canonical_skills", data["resources"])
        self.assertIn("known_tools", data["resources"])
        self.assertIn("certifications", data["resources"])
        self.assertIsInstance(data["resources"]["canonical_skills"], list)
        self.assertIsInstance(data["resources"]["known_tools"], list)
        self.assertIsInstance(data["resources"]["certifications"], list)
        self.assertTrue(data["resources"]["canonical_skills"])
        self.assertTrue(any(item.get("label") == "SQL" for item in data["resources"]["known_tools"]))
        self.assertIn("entity_types", data["conventions"])
        self.assertIn("block_types", data["conventions"])
        self.assertIn("understanding_statuses", data["conventions"])
        self.assertIn("skill_link_shape", data["conventions"])
        self.assertIn("canonical_store_path", data["sources"])
        self.assertIn("certification_registry_path", data["sources"])


if __name__ == "__main__":
    unittest.main()
