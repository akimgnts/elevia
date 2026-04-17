from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


class ProfileUnderstandingRouteTests(unittest.TestCase):
    def test_profile_understanding_session_returns_structured_questions(self) -> None:
        payload = {
            "profile": {
                "career_profile": {
                    "base_title": "Data Analyst",
                    "experiences": [
                        {
                            "title": "Data Analyst",
                            "company": "Acme",
                            "responsibilities": [
                                "Produced weekly reporting for leadership",
                            ],
                            "tools": [],
                            "canonical_skills_used": [{"label": "Data Analysis", "uri": "skill:data_analysis"}],
                            "skill_links": [],
                        }
                    ],
                    "projects": [
                        {
                            "title": "BI migration",
                            "description": "Migrated reporting stack for finance team",
                            "technologies": ["dbt", "Metabase"],
                        }
                    ],
                    "education": [],
                    "certifications": [],
                }
            },
            "source_context": {
                "validated_labels": ["SQL", "Python"],
                "rejected_tokens": [{"label": "Power BI"}],
                "tight_candidates": ["Tableau"],
            },
        }

        with TestClient(app) as client:
            resp = client.post("/profile-understanding/session", json=payload)

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["session_id"])
        self.assertIsInstance(data["questions"], list)
        self.assertGreaterEqual(len(data["questions"]), 3)
        self.assertTrue(any(question["category"] == "experience_autonomy" for question in data["questions"]))
        self.assertTrue(any(question["category"] == "experience_tools" for question in data["questions"]))
        self.assertTrue(any(question["category"] == "education" for question in data["questions"]))
        self.assertIn("entity_classification", data)
        self.assertIn("skill_links", data)
        self.assertIn("evidence_map", data)
        self.assertIn("confidence_map", data)
        self.assertIn("document_blocks", data)
        self.assertIn("mission_units", data)
        self.assertIn("open_signal", data)
        self.assertIn("canonical_signal", data)
        self.assertIn("understanding_status", data)
        self.assertIsInstance(data["entity_classification"], dict)
        self.assertIsInstance(data["skill_links"], list)
        self.assertIsInstance(data["evidence_map"], dict)
        self.assertIsInstance(data["confidence_map"], dict)
        self.assertIsInstance(data["document_blocks"], list)
        self.assertIsInstance(data["mission_units"], list)
        self.assertIsInstance(data["open_signal"], dict)
        self.assertIsInstance(data["canonical_signal"], dict)
        self.assertIsInstance(data["understanding_status"], dict)
        self.assertIn("experiences", data["entity_classification"])
        self.assertIn("projects", data["entity_classification"])
        self.assertIn("skills", data["entity_classification"])
        block_types = {block["block_type"] for block in data["document_blocks"]}
        self.assertIn("experience", block_types)
        self.assertIn("project", block_types)
        self.assertTrue(data["mission_units"])
        first_mission = data["mission_units"][0]
        self.assertIn("mission_text", first_mission)
        self.assertIn("skill_candidates_open", first_mission)
        self.assertIn("tool_candidates_open", first_mission)
        self.assertTrue(any(link.get("skill", {}).get("label") == "Data Analysis" for link in data["skill_links"]))
        data_analysis_links = [
            link for link in data["skill_links"]
            if link.get("skill", {}).get("label") == "Data Analysis"
        ]
        self.assertTrue(data_analysis_links)
        self.assertTrue(any(tool.get("label") == "SQL" for tool in data_analysis_links[0].get("tools", [])))
        self.assertEqual(data["entity_classification"]["skills"][0]["entity_type"], "skill")
        self.assertIn("career_profile.skill_links", data["evidence_map"])
        self.assertIn("career_profile.mission_units", data["evidence_map"])
        self.assertIn("entity_classification", data["confidence_map"])
        self.assertIn("skill_links", data["confidence_map"])
        self.assertIn("document_blocks", data["confidence_map"])
        self.assertIn("mission_units", data["confidence_map"])
        self.assertIn("skills", data["open_signal"])
        self.assertIn("tools", data["open_signal"])
        self.assertIn("mapped_skills", data["canonical_signal"])
        self.assertIn("overall_status", data["understanding_status"])
        self.assertIn("block_statuses", data["understanding_status"])
        self.assertIsInstance(data["proposed_profile_patch"], dict)
        self.assertIn("career_profile", data["proposed_profile_patch"])
        self.assertTrue(
            data["proposed_profile_patch"]["career_profile"]["experiences"][0]["skill_links"],
        )


if __name__ == "__main__":
    unittest.main()
