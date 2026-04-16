from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from documents.career_profile import CareerExperience


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _split_sentences(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if not value:
            continue
        parts = re.split(r"[.;\n]+", value)
        out.extend(part.strip() for part in parts if part.strip())
    return out


def _word_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", _canon(text)) if len(token) >= 3}


def _sentence_score(sentence: str, skill_label: str, tool_label: str) -> tuple[int, int, int]:
    sentence_norm = _canon(sentence)
    skill_norm = _canon(skill_label)
    tool_norm = _canon(tool_label)
    skill_tokens = _word_tokens(skill_label)
    sentence_tokens = _word_tokens(sentence)
    return (
        1 if skill_norm and skill_norm in sentence_norm else 0,
        1 if tool_norm and tool_norm in sentence_norm else 0,
        len(skill_tokens & sentence_tokens),
    )


def _best_context(sentences: list[str], skill_label: str, tools: list[str]) -> str | None:
    best_sentence = ""
    best_score = (-1, -1, -1)
    for sentence in sentences:
        for tool_label in tools or [""]:
            score = _sentence_score(sentence, skill_label, tool_label)
            if score > best_score:
                best_score = score
                best_sentence = sentence
    return best_sentence or None


def _best_skill_only_context(sentences: list[str], skill_label: str) -> str | None:
    best_sentence = ""
    best_score = (-1, -1, -1)
    for sentence in sentences:
        score = _sentence_score(sentence, skill_label, "")
        if score > best_score:
            best_sentence = sentence
            best_score = score
    if best_score[0] == 1 or best_score[2] > 0:
        return best_sentence or None
    return None


def build_skill_links_for_experience(exp: CareerExperience) -> list["SkillLink"]:
    from documents.career_profile import SkillLink, ToolRef

    if not exp.canonical_skills_used:
        return []

    sentences = _split_sentences(exp.responsibilities)
    tools_left = [tool.strip() for tool in exp.tools if str(tool).strip()]
    links: list[SkillLink] = []
    single_skill = len(exp.canonical_skills_used) == 1
    tool_matches: dict[str, str] = {}

    for tool_label in list(tools_left):
        candidates: list[tuple[tuple[int, int, int], int, str]] = []
        for index, skill in enumerate(exp.canonical_skills_used):
            skill_label = skill.label.strip()
            if not skill_label:
                continue
            sentence_scores = [_sentence_score(sentence, skill_label, tool_label) for sentence in sentences]
            best_score = max(sentence_scores) if sentence_scores else (0, 0, 0)
            if best_score[1] == 1:
                candidates.append((best_score, index, skill_label))

        if candidates:
            candidates.sort(reverse=True)
            best_score, _, best_skill = candidates[0]
            if len(candidates) == 1 or candidates[1][0] < best_score:
                tool_matches[tool_label] = best_skill
                continue
        if single_skill:
            tool_matches[tool_label] = exp.canonical_skills_used[0].label.strip()

    for skill in exp.canonical_skills_used:
        skill_label = skill.label.strip()
        if not skill_label:
            continue

        matched_tools = [tool_label for tool_label, matched_skill in tool_matches.items() if matched_skill == skill_label]
        context = _best_context(sentences, skill_label, matched_tools) if matched_tools else _best_skill_only_context(sentences, skill_label)
        if not matched_tools and not context:
            continue

        links.append(
            SkillLink(
                skill=skill,
                tools=[ToolRef(label=tool) for tool in matched_tools],
                context=context,
                autonomy_level=exp.autonomy_level,
            )
        )

    return links
