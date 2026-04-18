from __future__ import annotations

import sys
import unittest
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[3]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from agents_runtime.cv_understanding_agent.repository_adapter import prepare_understanding_input


class RepositoryAdapterTests(unittest.TestCase):
    def test_prepare_understanding_input_uses_repo_builder(self) -> None:
        payload = {
            "profile": {
                "career_profile": {
                    "base_title": "Data Analyst",
                    "experiences": [],
                    "education": [],
                    "certifications": [],
                    "projects": [],
                }
            },
            "source_context": {
                "cv_text": "Data Analyst with SQL and Power BI",
                "validated_labels": ["SQL"],
                "tight_candidates": ["Power BI"],
                "rejected_tokens": [{"label": "communication", "reason": "generic"}],
            },
        }

        result = prepare_understanding_input(payload)

        self.assertIn("signal_buckets", result)
        self.assertEqual(result["signal_buckets"]["accepted_signal"]["validated_labels"], ["SQL"])
        self.assertEqual(result["signal_buckets"]["ambiguous_signal"]["tight_candidates"], ["Power BI"])


if __name__ == "__main__":
    unittest.main()
