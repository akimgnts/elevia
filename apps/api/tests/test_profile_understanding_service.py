from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from profile_understanding.schemas import ProfileUnderstandingSessionRequest
from profile_understanding.service import ProfileUnderstandingService


class ProfileUnderstandingServiceTests(unittest.TestCase):
    def test_stub_patch_does_not_auto_inject_raw_pending_candidates(self) -> None:
        service = ProfileUnderstandingService()
        payload = ProfileUnderstandingSessionRequest(
            profile={
                "career_profile": {
                    "base_title": "Marketing Analyst",
                    "pending_skill_candidates": ["signal propre existant"],
                    "experiences": [
                        {
                            "title": "Marketing Analyst",
                            "company": "Acme",
                            "responsibilities": [
                                "Analyse multi sources des campagnes marketing",
                            ],
                            "tools": [],
                            "canonical_skills_used": [],
                            "skill_links": [],
                        }
                    ],
                    "education": [],
                    "certifications": [],
                    "projects": [],
                }
            },
            source_context={
                "validated_labels": ["analyse", "analyse multi sources"],
                "tight_candidates": ["analyse multi sources anomalies"],
                "rejected_tokens": [{"label": "communication", "reason": "generic"}],
            },
        )

        result = service.create_session(payload)
        pending = result.proposed_profile_patch["career_profile"]["pending_skill_candidates"]

        self.assertEqual(pending, ["signal propre existant"])

    def test_http_provider_falls_back_to_stub_by_default(self) -> None:
        service = ProfileUnderstandingService()
        service.provider = "http"
        service.remote_url = "http://127.0.0.1:9/profile-understanding/session"
        service.allow_stub_fallback = True

        payload = ProfileUnderstandingSessionRequest(
            profile={"career_profile": {"experiences": [], "education": [], "certifications": [], "projects": []}},
            source_context={},
        )

        result = service.create_session(payload)

        self.assertEqual(result.provider, "stub")
        self.assertEqual(result.trace_summary.get("fallback_reason"), "remote_provider_unavailable")

    def test_http_provider_can_fail_closed_when_stub_fallback_disabled(self) -> None:
        service = ProfileUnderstandingService()
        service.provider = "http"
        service.remote_url = "http://127.0.0.1:9/profile-understanding/session"
        service.allow_stub_fallback = False

        payload = ProfileUnderstandingSessionRequest(
            profile={"career_profile": {"experiences": [], "education": [], "certifications": [], "projects": []}},
            source_context={},
        )

        with self.assertRaises(RuntimeError):
            service.create_session(payload)


if __name__ == "__main__":
    unittest.main()
