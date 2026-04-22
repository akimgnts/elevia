from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from compass.ai_raw_cv_reconstruction import RawCvReconstructionV1


@dataclass(frozen=True)
class PipelineHTTPError(Exception):
    status_code: int
    detail: Dict[str, Any]


@dataclass(frozen=True)
class ParseFilePipelineRequest:
    request_id: str
    raw_filename: str
    content_type: str
    file_bytes: bytes
    enrich_llm: int = 0


@dataclass(frozen=True)
class FileIngestionResult:
    request_id: str
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class TextExtractionResult:
    request_id: str
    filename: str
    content_type: str
    cv_text: str
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillCandidateStageResult:
    tight_candidates: List[str] = field(default_factory=list)
    tight_metrics: Dict[str, Any] = field(default_factory=dict)
    noise_removed: List[str] = field(default_factory=list)
    split_chunks: List[str] = field(default_factory=list)
    cleaned_chunks: List[str] = field(default_factory=list)
    mapping_inputs: List[str] = field(default_factory=list)
    reduced_candidates: List[str] = field(default_factory=list)
    cleaned_candidates: List[str] = field(default_factory=list)
    reducer_traces: List[dict] = field(default_factory=list)
    phrase_length_gt3_tokens: int = 0
    duplicate_tokens: int = 0
    broken_tokens: int = 0
    multi_skill_phrases: int = 0
    lemmatized_chunks_count: int = 0
    pos_rejected_count: int = 0
    enable_phrase_split: bool = False
    enable_chunk_normalizer: bool = False
    enable_lemmatization: bool = False
    enable_pos_filter: bool = False


@dataclass(frozen=True)
class StructuredExtractionStageResult:
    enabled: bool = False
    structured_units: List[dict] = field(default_factory=list)
    top_signal_units: List[dict] = field(default_factory=list)
    secondary_signal_units: List[dict] = field(default_factory=list)
    mapping_inputs: List[str] = field(default_factory=list)
    generic_filter_removed: List[dict] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnrichedSignalStageResult:
    enriched_signals: List[dict] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnrichedConceptStageResult:
    concept_signals: List[dict] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalMappingStageResult:
    mapping_inputs: List[str] = field(default_factory=list)
    canonical_skills_list: List[dict] = field(default_factory=list)
    canonical_hierarchy_added: List[str] = field(default_factory=list)
    canonical_enriched_labels: List[str] = field(default_factory=list)
    canonical_stats: Dict[str, int] = field(default_factory=dict)
    resolved_ids: List[str] = field(default_factory=list)
    expansion_map: Dict[str, Any] = field(default_factory=dict)
    expanded_ids: List[str] = field(default_factory=list)
    canonical_dedupe_debug: Dict[str, Any] = field(default_factory=dict)
    skill_proximity_links: List[dict] = field(default_factory=list)
    skill_proximity_summary: Dict[str, Any] = field(default_factory=dict)
    skill_proximity_count: int = 0
    preserved_explicit_skills: List[dict] = field(default_factory=list)
    profile_summary_skills: List[dict] = field(default_factory=list)
    dropped_by_priority: List[dict] = field(default_factory=list)
    priority_trace: List[dict] = field(default_factory=list)
    priority_stats: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnrichmentStageResult:
    profile: Dict[str, Any]
    baseline_esco_count: int
    injected_esco_from_domain: int
    total_esco_count: int
    resolved_to_esco: List[dict] = field(default_factory=list)
    rejected_tokens_list: List[dict] = field(default_factory=list)
    domain_uris: List[str] = field(default_factory=list)
    domain_tokens: List[str] = field(default_factory=list)
    domain_debug: Dict[str, Any] = field(default_factory=dict)
    matching_trace_stages: List[dict] = field(default_factory=list)
    skill_provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchingInputStageResult:
    matching_input_trace: Dict[str, Any]


@dataclass(frozen=True)
class ProfileIntelligenceStageResult:
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileIntelligenceAiAssistStageResult:
    data: Dict[str, Any] = field(default_factory=dict)


class ProfileReconstructionV2(BaseModel):
    version: str = "v2"
    source: str = "ai2_stub"
    status: str = "skipped"
    suggested_summary: Dict[str, Any] = Field(default_factory=dict)
    suggested_experiences: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_skills: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_projects: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_certifications: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_languages: List[Dict[str, Any]] = Field(default_factory=list)
    link_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)


@dataclass(frozen=True)
class CacheHookResult:
    profile_hash: str
    extracted_text_hash: str


@dataclass(frozen=True)
class ParseFilePipelineArtifacts:
    result: Dict[str, Any]
    pipeline_variant: str
    mode: str
    compass_e_enabled: bool
    ai_available: bool
    ai_added_count: int
    ai_error: Optional[str]
    extracted_text_hash: str
    profile_hash: str
    profile_fingerprint: Optional[str]
    profile_cluster: Dict[str, Any]
    skill_candidates: SkillCandidateStageResult
    structured_extraction: StructuredExtractionStageResult
    enriched_signals: EnrichedSignalStageResult
    concept_signals: EnrichedConceptStageResult
    canonical_mapping: CanonicalMappingStageResult
    enrichment: EnrichmentStageResult
    matching_input: MatchingInputStageResult
    profile_intelligence: ProfileIntelligenceStageResult
    profile_intelligence_ai_assist: ProfileIntelligenceAiAssistStageResult
    raw_cv_reconstruction: RawCvReconstructionV1
    profile_reconstruction: ProfileReconstructionV2
    warnings: List[str]
    cv_text: str
    source_cv_text: str
    filename: str
    content_type: str
    domain_skills_active: List[str] = field(default_factory=list)
    domain_skills_pending_count: int = 0
    llm_fired: bool = False
    pipeline_warnings: List[str] = field(default_factory=list)
