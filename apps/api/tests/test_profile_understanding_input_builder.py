from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from profile_understanding.input_builder import build_understanding_input


class UnderstandingInputBuilderTests(unittest.TestCase):
    def test_builder_separates_accepted_ambiguous_rejected_and_unmapped_signal(self) -> None:
        parse_payload = {
            "filename": "cv.pdf",
            "extracted_text_length": 1200,
            "profile_fingerprint": "fp-1",
            "skills_canonical": ["SQL"],
            "profile": {
                "career_profile": {
                    "base_title": "Data Analyst",
                    "experiences": [
                        {
                            "title": "Data Analyst",
                            "company": "Acme",
                            "responsibilities": ["Built weekly SQL reporting"],
                            "tools": ["SQL"],
                            "canonical_skills_used": [{"label": "Data Analysis", "uri": "skill:data_analysis"}],
                        }
                    ],
                }
            },
            "profile_summary_skills": [{"label": "SQL"}],
            "profile_intelligence": {"dominant_domain": "data"},
            "structured_signal_units": [{"label": "weekly reporting", "source_section": "experience"}],
            "top_signal_units": [{"label": "sql reporting"}],
            "secondary_signal_units": [{"label": "dashboarding"}],
            "skill_proximity_links": [{"source": "SQL", "target": "reporting"}],
            "canonical_skills": [{"label": "SQL", "uri": "skill:sql"}],
            "validated_labels": ["SQL"],
            "tight_candidates": ["Power BI", "Revenue Ops"],
            "rejected_tokens": [
                {"label": "communication", "reason": "generic"},
                {"label": "HubSpot", "reason": "unmapped_tool"},
            ],
        }

        result = build_understanding_input(cv_text="raw cv text", parse_payload=parse_payload)

        self.assertEqual(result["signal_buckets"]["accepted_signal"]["validated_labels"], ["SQL"])
        self.assertEqual(result["signal_buckets"]["ambiguous_signal"]["tight_candidates"], ["Power BI", "Revenue Ops"])
        self.assertEqual(result["signal_buckets"]["rejected_signal"][0]["label"], "communication")
        self.assertEqual(result["signal_buckets"]["unmapped_but_promising_signal"][0]["label"], "HubSpot")
        self.assertEqual(
            result["deterministic_profile_seed"]["career_profile_seed"]["experiences"][0]["title"],
            "Data Analyst",
        )
        self.assertTrue(result["agent_constraints"]["require_contextual_evidence_for_rejected_signal"])


if __name__ == "__main__":
    unittest.main()
