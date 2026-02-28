"""
documents — CV Generator package (Sprint CV Generator v1)

Modules:
  schemas      — Pydantic v2 input/output models
  ats_keywords — deterministic ATS keyword extraction
  cache        — SQLite-backed document cache
  llm_client   — safe OpenAI wrapper (no key exposure)
  cv_generator — orchestration: cache → LLM/fallback → anti-lie → response
"""
