"""
profile_key_skills.py — Pydantic schemas for POST /profile/key-skills.

Display-only ranking for AnalyzePage signal-first UI.
No scoring change — read-only reuse of IDF/weights concepts.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel


class ValidatedItemIn(BaseModel):
    uri: str
    label: str


class KeySkillItem(BaseModel):
    label: str
    reason: Literal["weighted", "idf", "standard"]
    idf: Optional[float] = None
    weighted: bool = False


class KeySkillsRequest(BaseModel):
    validated_items: List[ValidatedItemIn]
    rome_code: Optional[str] = None


class KeySkillsResponse(BaseModel):
    key_skills: List[KeySkillItem]       # max 12 — shown first in AnalyzePage
    all_skills_ranked: List[KeySkillItem]  # all ranked, max 40 — for modal
