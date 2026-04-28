"""Result types for fit_score_v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EligibilityStatus:
    ok: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": bool(self.ok), "reasons": list(self.reasons)}


@dataclass
class FitScoreV2Result:
    eligibility_status: EligibilityStatus
    fit_score: Optional[int]
    preference_score: Optional[int]
    explain: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligibility_status": self.eligibility_status.to_dict(),
            "fit_score": self.fit_score,
            "preference_score": self.preference_score,
            "explain": dict(self.explain),
        }
