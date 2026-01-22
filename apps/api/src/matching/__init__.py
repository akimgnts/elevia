# matching package
from .matching_v1 import MatchingEngine
from .extractors import extract_profile
from .idf import compute_idf
from .diagnostic import compute_diagnostic
from .models import Verdict, CriterionResult, MatchingDiagnostic

__all__ = [
    "MatchingEngine",
    "extract_profile",
    "compute_idf",
    "compute_diagnostic",
    "Verdict",
    "CriterionResult",
    "MatchingDiagnostic",
]
