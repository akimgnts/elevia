"""
decision_layer.py — AI Decision Layer (INACTIVE STUBS).

This module is not connected to any route or service.
Activate in a future sprint by wiring into applications.py prepare flow
or a dedicated /ai/* endpoint.

Rules (when activated):
  - NEVER modify scoring/matching core (matching/*)
  - NEVER recalculate offer scores
  - NEVER replace existing recommendation logic
  - Only interpret scores and guide user strategy
"""

# Sentinel — importable by any future code that wants to guard on activation.
AI_LAYER_INACTIVE = True


# ---------------------------------------------------------------------------
# Stub functions (not callable until AI_LAYER_INACTIVE = False)
# ---------------------------------------------------------------------------

# def score_application_fit(profile: dict, offer: dict) -> float:
#     """
#     Return a 0–1 contextual fit score for a profile against an offer.
#     Input: profile dict (from auth_profiles), offer dict (from fact_offers payload).
#     Output: float 0.0–1.0.
#     NOTE: Does NOT recalculate ESCO/matching score. Interprets existing signals.
#     """
#     raise NotImplementedError("AI Decision Layer is not yet activated")


# def suggest_next_status(application_id: str) -> str:
#     """
#     Return the recommended next ApplicationStatus for a given application.
#     Reads application_tracker + apply_pack_runs to understand current state.
#     Output: one of the ApplicationStatus enum values.
#     """
#     raise NotImplementedError("AI Decision Layer is not yet activated")


# def rank_applications(user_id: str) -> list[dict]:
#     """
#     Return a ranked list of the user's applications sorted by opportunity score.
#     Output: list of dicts with keys: application_id, offer_id, rank, reason.
#     """
#     raise NotImplementedError("AI Decision Layer is not yet activated")


# def generate_action_hint(application_id: str) -> str:
#     """
#     Generate a short, contextual action prompt for the current stage.
#     Example: "Your CV is ready — consider sending by Thursday for best response rate."
#     Output: plain text string, 1–2 sentences.
#     """
#     raise NotImplementedError("AI Decision Layer is not yet activated")
