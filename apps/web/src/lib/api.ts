/**
 * API client for backend calls.
 * Uses VITE_API_BASE_URL or defaults to relative path.
 */

const API_BASE =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "/api";

export interface OfferNormalized {
  id: string;
  source: "france_travail" | "business_france" | "unknown";
  title: string;
  description: string;
  display_description: string;
  publication_date: string | null;
  company: string | null;
  city: string | null;
  country: string | null;
  contract_duration: number | null;
  start_date: string | null;
}

export interface OffersCatalogResponse {
  offers: OfferNormalized[];
  meta: {
    total_available: number;
    returned: number;
    data_source: "live-db" | "static-fallback";
    fallback_reason: string | null;
  };
}

export interface MatchRequest {
  profile: unknown;
  offers: unknown[];
}

export interface MatchResponse {
  profile_id: string | null;
  threshold: number;
  received_offers: number;
  results: MatchItem[];
  message: string | null;
}

export interface MatchItem {
  offer_id: string;
  score: number;
  reasons?: string[];
  diagnostic?: unknown;
}

export interface SampleOffersResponse {
  total_available: number;
  returned: number;
  offers: unknown[];
}

/**
 * Fetch offers catalog from the API.
 * GET /offers/catalog
 */
export async function fetchCatalogOffers(
  limit: number = 200,
  source: "all" | "france_travail" | "business_france" = "all"
): Promise<OffersCatalogResponse> {
  const url = `${API_BASE}/offers/catalog?limit=${limit}&source=${source}`;

  const res = await fetch(url);

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }

  return res.json();
}

/**
 * Fetch sample VIE offers from the API.
 * GET /offers/sample
 */
export async function fetchSampleOffers(limit: number = 200): Promise<SampleOffersResponse> {
  const url = `${API_BASE}/offers/sample?limit=${limit}`;

  const res = await fetch(url);

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }

  return res.json();
}

/**
 * Run matching against the real API.
 * POST /v1/match/
 */
export async function runMatch(
  profile: unknown,
  offers: unknown[]
): Promise<MatchResponse> {
  const url = `${API_BASE}/v1/match`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ profile, offers }),
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }

  return res.json();
}

/**
 * Normalized correction event format.
 * VERROU #1 Sprint 14 - Format strict, aucune variation autorisée.
 */
export interface CorrectionEvent {
  type: "correction";
  session_id: string;
  profile_hash: string;
  corrections: {
    capabilities: {
      added: string[];
      deleted: string[];
      modified_level: Array<{ name: string; from: string; to: string }>;
    };
  };
  stats: {
    unmapped_count: number;
    detected_capabilities_count: number;
  };
  meta: {
    app_version: string;
    api_version: string;
    timestamp: string;
  };
}

export interface CorrectionInput {
  sessionId: string;
  profileHash: string;
  added: string[];
  deleted: string[];
  modifiedLevel: Array<{ name: string; from: string; to: string }>;
  unmappedCount: number;
  detectedCapabilitiesCount: number;
}

const APP_VERSION = "web@0.1.0";
const API_VERSION = "api@0.1.0";

/**
 * Build a normalized correction event.
 * UNIQUE function for all correction logs - NO VARIATION ALLOWED.
 */
export function buildCorrectionEvent(input: CorrectionInput): CorrectionEvent {
  return {
    type: "correction",
    session_id: input.sessionId,
    profile_hash: input.profileHash,
    corrections: {
      capabilities: {
        added: input.added,
        deleted: input.deleted,
        modified_level: input.modifiedLevel,
      },
    },
    stats: {
      unmapped_count: input.unmappedCount,
      detected_capabilities_count: input.detectedCapabilitiesCount,
    },
    meta: {
      app_version: APP_VERSION,
      api_version: API_VERSION,
      timestamp: new Date().toISOString(),
    },
  };
}

/**
 * Post correction metrics (fire and forget).
 */
export async function postCorrectionMetric(event: CorrectionEvent): Promise<void> {
  const url = `${API_BASE}/metrics/correction`;

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(event),
    });

    if (!res.ok) {
      console.warn(`[metrics] POST failed: ${res.status}`);
    }
  } catch (err) {
    console.warn("[metrics] POST error:", err);
  }
}

// ============================================================================
// Inbox
// ============================================================================

// ── Explain block types ───────────────────────────────────────────────────────

export interface SkillExplainItem {
  label: string;
  weighted: boolean; // true if skill appears in ROME competences for this offer
}

export interface ExplainBreakdown {
  skills_score: number;
  skills_weight: number;   // 70
  language_score: number;
  language_weight: number; // 15
  language_match: boolean;
  education_score: number;
  education_weight: number; // 10
  education_match: boolean;
  country_score: number;
  country_weight: number;  // 5
  country_match: boolean;
  total: number;
}

export interface NearMatchItem {
  profile_skill_id: string;
  profile_label: string;
  offer_skill_id: string;
  offer_label: string;
  relation: string;
  strength: number;
}

export interface NearMatchSummary {
  count: number;
  max_strength: number;
  avg_strength: number;
}

export interface ExplainBlock {
  matched_display: SkillExplainItem[];  // top 6 for card
  missing_display: SkillExplainItem[];  // top 6 for card
  matched_full: SkillExplainItem[];     // all matched, max 30
  missing_full: SkillExplainItem[];     // all missing, max 30
  matched_core?: SkillExplainItem[];
  missing_core?: SkillExplainItem[];
  matched_secondary?: SkillExplainItem[];
  missing_secondary?: SkillExplainItem[];
  matched_context?: SkillExplainItem[];
  missing_context?: SkillExplainItem[];
  breakdown: ExplainBreakdown;
  near_matches?: NearMatchItem[];
  near_match_count?: number;
  near_match_summary?: NearMatchSummary | null;
}

export interface OfferExplanation {
  score?: number | null;
  fit_label: string;
  summary_reason: string;
  strengths: string[];
  gaps: string[];
  blockers: string[];
  next_actions: string[];
}

export interface OfferRoleHypothesis {
  label: string;
  confidence: number;
}

export interface OfferIntelligence {
  dominant_role_block: string;
  secondary_role_blocks: string[];
  dominant_domains: string[];
  top_offer_signals: string[];
  required_skills: string[];
  optional_skills: string[];
  role_hypotheses: OfferRoleHypothesis[];
  offer_summary: string;
  role_block_scores?: Array<{
    role_block: string;
    score: number;
    share: number;
  }>;
  debug?: Record<string, unknown> | null;
}

export interface SemanticRoleAlignment {
  profile_role: string;
  offer_role: string;
  alignment: "high" | "medium" | "low";
}

export interface SemanticDomainAlignment {
  shared_domains: string[];
  profile_only_domains: string[];
  offer_only_domains: string[];
}

export interface SemanticSignalAlignment {
  matched_signals: string[];
  missing_core_signals: string[];
}

export interface SemanticExplainability {
  role_alignment: SemanticRoleAlignment;
  domain_alignment: SemanticDomainAlignment;
  signal_alignment: SemanticSignalAlignment;
  alignment_summary: string;
}

export interface InboxItem {
  offer_id: string;
  id?: string;
  source?: string;
  title: string;
  title_clean?: string | null;
  company: string | null;
  country: string | null;
  city: string | null;
  publication_date?: string | null;
  is_vie?: boolean;
  score: number;
  score_pct?: number;
  score_raw?: number;
  reasons: string[];
  matched_skills?: string[];
  missing_skills?: string[];
  matched_skills_display?: string[];
  missing_skills_display?: string[];
  unmapped_tokens?: string[];
  offer_uri_count?: number;
  profile_uri_count?: number;
  intersection_count?: number;
  scoring_unit?: string;
  description?: string | null;
  display_description?: string | null;
  description_snippet?: string | null;
  skills_display?: string[];
  strategy_summary?: {
    mission_summary?: string;
    distance?: string;
    action_guidance?: string;
  } | null;
  skills_uri_count?: number;
  skills_uri_collapsed_dupes?: number;
  skills_unmapped_count?: number;
  offer_cluster?: string;
  domain_bucket?: "strict" | "neighbor" | "out";
  signal_score?: number;
  coherence?: "ok" | "suspicious";
  near_match_count?: number;
  /** @deprecated Inbox UI no longer uses this. Safe backend cleanup candidate. */
  match_strength?: "STRONG" | "MEDIUM" | "WEAK";
  core_matched_count?: number;
  core_total_count?: number;
  dominant_reason?: string;
  rome?: { rome_code: string; rome_label: string } | null;
  rome_competences?: Array<{
    competence_code: string;
    competence_label: string;
    esco_uri?: string | null;
  }> | null;
  explain?: ExplainBlock | null;
  explanation: OfferExplanation;
  offer_intelligence?: OfferIntelligence | null;
  semantic_explainability?: SemanticExplainability | null;
  /** @deprecated Inbox UI no longer uses this. Safe backend cleanup candidate. */
  explain_v1?: CompassExplainCompact | null;
}

export interface InboxMeta {
  profile_cluster?: string;
  gating_mode?: "IN_DOMAIN" | "STRICT_PLUS_NEIGHBORS" | "OUT_OF_DOMAIN";
  coverage_before?: number;
  coverage_after?: number;
  suggest_out_of_domain?: boolean;
  out_of_domain_count?: number;
  cluster_distribution_top20?: Record<string, number>;
  strict_count?: number;
  neighbor_count?: number;
  out_count?: number;
}

export interface InboxResponse {
  profile_id: string;
  items: InboxItem[];
  total_matched: number;
  total_decided: number;
  total_estimate?: number | null;
  applied_filters?: Record<string, unknown> | null;
  page?: number | null;
  page_size?: number | null;
  meta?: InboxMeta;
}

export interface ProfileSummaryExperience {
  title: string | null;
  company: string | null;
  dates: string | null;
  impact_one_liner: string | null;
}

export interface ProfileSummaryV1 {
  cv_quality_level: "LOW" | "MED" | "HIGH";
  cv_quality_reasons: string[];
  top_skills: SkillRefItem[];
  tools: string[];
  certifications: string[];
  education: string[];
  experiences: ProfileSummaryExperience[];
  cluster_hints: string[];
  last_updated: string;
}

export interface OfferSemanticResponse {
  offer_id: string;
  semantic_score: number | null;
  semantic_model_version: string | null;
  relevant_passages: string[];
  ai_available: boolean;
  ai_error: string | null;
}

// ── Context layer ───────────────────────────────────────────────────────────

export interface EvidenceSpan {
  field: string;
  span: string;
}

export interface OfferContext {
  offer_id: string;
  mission_summary: string | null;
  role_type: "BI_REPORTING" | "DATA_ANALYSIS" | "DATA_ENGINEERING" | "PRODUCT_ANALYTICS" | "OPS_ANALYTICS" | "MIXED" | "UNKNOWN";
  primary_role_type: "BI_REPORTING" | "DATA_ANALYSIS" | "DATA_ENGINEERING" | "PRODUCT_ANALYTICS" | "OPS_ANALYTICS" | "MIXED" | "UNKNOWN";
  role_type_reason?: string | null;
  primary_outcomes: string[];
  responsibilities: string[];
  tools_stack_signals: string[];
  work_style_signals: {
    autonomy_level: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
    stakeholder_exposure: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
    cadence: "ADHOC" | "WEEKLY" | "DAILY" | "UNKNOWN";
  };
  environment_signals: {
    org_type: "LARGE_CORP" | "SME" | "STARTUP" | "PUBLIC" | "UNKNOWN";
    domain: string | null;
    data_maturity: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
  };
  constraints: string[];
  needs_clarification: string[];
  confidence: number;
  evidence_spans: EvidenceSpan[];
}

export interface ProfileContext {
  profile_id: string;
  trajectory_summary: string | null;
  dominant_strengths: string[];
  profile_tools_signals: string[];
  experience_signals: {
    analysis_vs_execution: "ANALYSIS" | "EXECUTION" | "MIXED" | "UNKNOWN";
    autonomy_signal: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
    stakeholder_signal: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
  };
  preferred_work_signals: {
    cadence_preference: "ADHOC" | "WEEKLY" | "DAILY" | "UNKNOWN";
    environment_preference: "LARGE_CORP" | "SME" | "STARTUP" | "PUBLIC" | "UNKNOWN";
  };
  nonlinear_notes: string[];
  gaps_or_unknowns: string[];
  confidence: number;
  evidence_spans: EvidenceSpan[];
}

export interface ContextFit {
  profile_id: string;
  offer_id: string;
  fit_summary: string | null;
  why_it_fits: string[];
  likely_frictions: string[];
  clarifying_questions: string[];
  recommended_angle: {
    cv_focus: string[];
    cover_letter_hooks: string[];
  };
  confidence: number;
  evidence_spans: EvidenceSpan[];
}

export interface InboxFilters {
  q_company?: string;
  country?: string;
  city?: string;
  contract_type?: string;
  published_from?: string;
  published_to?: string;
  domain_bucket?: "strict" | "neighbor" | "out";
  min_score?: number;
  confidence?: "LOW" | "MED" | "HIGH";
  rare_level?: "LOW" | "MED" | "HIGH";
  sector_level?: "LOW" | "MED" | "HIGH";
  has_tool_unspecified?: boolean;
  page?: number;
  page_size?: number;
  sort?: "published_desc" | "score_desc" | "confidence_desc";
}

export async function fetchInbox(
  profile: unknown,
  profileId: string,
  minScore = 65,
  limit = 20,
  explain = true,
  domainMode: "in_domain" | "all" = "in_domain",
  filters?: InboxFilters,
): Promise<InboxResponse> {
  const params = new URLSearchParams();
  params.set("domain_mode", domainMode);
  if (filters?.q_company) params.set("q_company", filters.q_company);
  if (filters?.country) params.set("country", filters.country);
  if (filters?.city) params.set("city", filters.city);
  if (filters?.contract_type) params.set("contract_type", filters.contract_type);
  if (filters?.published_from) params.set("published_from", filters.published_from);
  if (filters?.published_to) params.set("published_to", filters.published_to);
  if (filters?.domain_bucket) params.set("domain_bucket", filters.domain_bucket);
  if (typeof filters?.min_score === "number") params.set("min_score", String(filters.min_score));
  if (filters?.confidence) params.set("confidence", filters.confidence);
  if (filters?.rare_level) params.set("rare_level", filters.rare_level);
  if (filters?.sector_level) params.set("sector_level", filters.sector_level);
  if (typeof filters?.has_tool_unspecified === "boolean") {
    params.set("has_tool_unspecified", String(filters.has_tool_unspecified));
  }
  if (typeof filters?.page === "number") params.set("page", String(filters.page));
  if (typeof filters?.page_size === "number") params.set("page_size", String(filters.page_size));
  if (filters?.sort) params.set("sort", filters.sort);

  const url = `${API_BASE}/inbox?${params.toString()}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId, profile, min_score: minScore, limit, explain }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function postDecision(
  offerId: string,
  profileId: string,
  status: "SHORTLISTED" | "DISMISSED"
): Promise<void> {
  const url = `${API_BASE}/offers/${encodeURIComponent(offerId)}/decision`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId, status }),
  });
  if (!res.ok) {
    console.warn(`[inbox] decision failed: ${res.status}`);
  }
}

export async function fetchOfferSemantic(
  offerId: string,
  profileId: string
): Promise<OfferSemanticResponse> {
  const url = `${API_BASE}/offers/${encodeURIComponent(offerId)}/semantic`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function fetchOfferContext(
  offerId: string,
  description: string
): Promise<OfferContext> {
  const url = `${API_BASE}/context/offer`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ offer_id: offerId, description }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function fetchProfileContext(
  profileId: string,
  profile?: unknown
): Promise<ProfileContext> {
  const url = `${API_BASE}/context/profile`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId, profile: profile ?? null }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function fetchProfileSummary(profileId: string): Promise<ProfileSummaryV1> {
  const url = `${API_BASE}/profile/summary?profile_id=${encodeURIComponent(profileId)}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    const err = new Error(`API ${res.status}: ${txt}`);
    (err as Error & { status?: number }).status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchContextFit(
  profileContext: ProfileContext,
  offerContext: OfferContext,
  matchedSkills: string[],
  missingSkills: string[]
): Promise<ContextFit> {
  const url = `${API_BASE}/context/fit`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_context: profileContext,
      offer_context: offerContext,
      matched_skills: matchedSkills,
      missing_skills: missingSkills,
    }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json();
}

/**
 * Ingest CV text and extract structured profile.
 * POST /profile/ingest_cv
 */
export async function ingestCv(cvText: string): Promise<unknown> {
  const url = `${API_BASE}/profile/ingest_cv`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ cv_text: cvText }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = data.detail;
    if (typeof detail === "string") {
      throw new Error(detail);
    } else if (detail?.message) {
      throw new Error(detail.message);
    }
    throw new Error(`API ${res.status}: Erreur lors de l'extraction`);
  }

  return res.json();
}

export class CvDeltaApiError extends Error {
  status: number;
  details: string;

  constructor(status: number, details: string) {
    super(details);
    this.status = status;
    this.details = details;
  }
}

export type CvDeltaMeta = {
  run_mode: "A" | "A+B";
  provider: "openai" | null;
  model: string | null;
  cache_hit: boolean;
  warning: string | null;
};

export type CvDeltaResponse = {
  meta: CvDeltaMeta;
  canonical_count: number;
  added_skills: string[];
  removed_skills: string[];
  unchanged_skills_count: number;
  added_esco: string[];
  removed_esco: string[];
};

export type CvDeltaRequest = {
  file: File;
  withLlm: boolean;
  provider?: "openai";
  model?: string;
};

// ============================================================================
// CV File Upload (baseline, no LLM)
// ============================================================================

export interface SkillGroupItem {
  group: string;
  count: number;
  items: string[];
}

export interface ValidatedItem {
  uri: string;
  label: string;
}

export interface ParseFileResponse {
  source: string;
  mode: "baseline" | "llm";
  pipeline_used?: string;
  pipeline_variant?: string;
  compass_e_enabled?: boolean;
  ai_available: boolean;
  ai_added_count: number;
  ai_error?: string | null;
  llm_fired?: boolean;
  filename: string;
  content_type: string;
  extracted_text_length: number;
  extracted_text_hash?: string | null;
  profile_fingerprint?: string | null;
  recovery_pipeline_version?: string | null;
  canonical_count: number;
  raw_detected: number;
  validated_skills: number;
  filtered_out: number;
  validated_items: ValidatedItem[];
  validated_labels?: string[];
  raw_tokens?: string[];
  filtered_tokens?: string[];
  alias_hits_count?: number;
  alias_hits?: { alias: string; label: string }[];
  skill_groups: SkillGroupItem[];
  skills_uri_count?: number;
  skills_uri_collapsed_dupes?: number;
  skills_unmapped_count?: number;
  skills_dupes?: Array<{ label: string; surfaces: string[] }>;
  skills_raw: string[];
  skills_canonical: string[];
  profile: { id: string; skills: string[]; skills_source: string; skills_uri?: string[] };
  warnings: string[];
  profile_cluster?: ProfileCluster;
  /** DOMAIN→ESCO enrichment fields (Compass E) */
  domain_skills_active?: string[];
  domain_skills_pending_count?: number;
  resolved_to_esco?: Array<{
    token_normalized: string;
    esco_uri: string;
    esco_label?: string;
    provenance?: string;
  }>;
  skill_provenance?: {
    baseline_esco: string[];
    library_token_to_esco: string[];
    llm_token_to_esco: string[];
  };
  baseline_esco_count?: number;
  injected_esco_from_domain?: number;
  total_esco_count?: number;
  rejected_tokens?: Array<{ token: string; token_norm: string; reason_code: string }>;
  /** Sprint 5: phrase-level tight extraction (pre-policy, pre-AI) */
  tight_candidates?: string[];
  tight_metrics?: {
    raw_count: number;
    candidate_count: number;
    noise_ratio: number;
    tech_density: number;
    top_ngrams?: Array<{ phrase: string; score: number }>;
  };
  /** Sprint 0700: canonical mapping layer */
  canonical_skills?: Array<{
    raw: string;
    canonical_id: string;
    label: string;
    strategy: string;
    confidence: number;
    cluster_name?: string;
    genericity_score?: number;
  }>;
  canonical_skills_count?: number;
  canonical_hierarchy_added?: string[];
  /** Skill proximity layer (display-only) */
  skill_proximity_links?: Array<{
    source_id: string;
    target_id: string;
    relation: string;
    strength: number;
  }>;
  skill_proximity_count?: number;
  skill_proximity_summary?: {
    source_covered_by_proximity: number;
    target_covered_by_proximity: number;
    match_count: number;
    max_strength: number;
    avg_strength: number;
  };
  /** Analyze Dev Mode (DEV-only, optional) */
  analyze_dev?: {
    raw_extraction?: {
      raw_extracted_skills?: string[];
      raw_tokens?: string[];
      raw_detected?: number;
      validated_labels?: string[];
    };
    tight_candidates?: {
      items?: string[];
      count?: number;
      top_candidates?: Array<{ phrase?: string; score?: number } | string>;
      top_filtered?: Array<{ phrase?: string; reason?: string }>;
      split_examples?: Array<{ source?: string; added?: string[]; generated?: string[] }>;
      cv_structure_rejected_count?: number;
      cv_structure_rejected_examples?: string[];
    };
    tight_split_trace?: Array<{
      source?: string;
      generated?: string[];
      inserted?: string[];
      survived_after_filter?: string[];
      present_in_final_tight?: string[];
      present_in_mapping_inputs?: string[];
      dropped?: Array<{ chunk?: string; reason?: string }>;
    }>;
    tight_selection_trace?: Array<{
      candidate?: string;
      origin?: string;
      base_score?: number;
      adjustments?: string[];
      final_score?: number;
      selected?: boolean;
    }>;
    top_candidates_source?: string;
    mapping_inputs_source?: string;
    mapping_inputs_preview?: string[];
    noise_removed?: string[];
    split_chunks?: string[];
    split_chunks_count?: number;
    cleaned_chunks?: string[];
    cleaned_chunks_count?: number;
    lemmatized_chunks_count?: number;
    pos_rejected_count?: number;
    stage_flags?: {
      phrase_splitting?: boolean;
      chunk_normalizer?: boolean;
      light_lemmatization?: boolean;
      pos_filter?: boolean;
    };
    canonical_mapping?: {
      mappings?: Array<Record<string, unknown>>;
      matched_count?: number;
      unresolved_count?: number;
      synonym_count?: number;
      tool_count?: number;
    };
    hierarchy_expansion?: {
      input_ids?: string[];
      added_parents?: string[];
      expansion_map?: Record<string, string>;
      expanded_ids?: string[];
    };
    esco_promotion?: {
      canonical_labels?: string[];
      skills_uri_promoted?: string[];
      promoted_uri_count?: number;
    };
    proximity?: {
      links?: Array<Record<string, unknown>>;
      summary?: Record<string, unknown>;
      count?: number;
    };
    explainability?: { status?: string; reason?: string };
    counters?: {
      raw_count?: number;
      tight_count?: number;
      split_chunks_count?: number;
      cleaned_chunks_count?: number;
      lemmatized_chunks_count?: number;
      pos_rejected_count?: number;
      canonical_count?: number;
      unresolved_count?: number;
      expanded_count?: number;
      promoted_uri_count?: number;
      near_match_count?: number;
      noise_removed_count?: number;
      canonical_success_rate?: number;
      compass_skill_candidates?: number;
      compass_skill_rejected?: number;
      tight_single_token_count?: number;
      tight_generic_rejected_count?: number;
      tight_numeric_rejected_count?: number;
      tight_repeated_fragment_count?: number;
      tight_filtered_out_count?: number;
      tight_split_generated_count?: number;
      broken_token_repair_count?: number;
      generated_composite_rejected_count?: number;
      cv_structure_rejected_count?: number;
    };
    broken_token_repair_examples?: Array<{ from?: string; to?: string }>;
  };
}

export interface ParseBaselineResponse {
  source: string;
  skills_raw: string[];
  skills_canonical: string[];
  canonical_count: number;
  raw_detected: number;
  validated_skills: number;
  filtered_out: number;
  validated_items: ValidatedItem[];
  validated_labels?: string[];
  raw_tokens?: string[];
  filtered_tokens?: string[];
  alias_hits_count?: number;
  alias_hits?: { alias: string; label: string }[];
  skill_groups: SkillGroupItem[];
  skills_uri_count?: number;
  skills_uri_collapsed_dupes?: number;
  skills_unmapped_count?: number;
  skills_dupes?: Array<{ label: string; surfaces: string[] }>;
  profile: { id: string; skills: string[]; skills_source: string; skills_uri?: string[] };
  warnings: string[];
  profile_cluster?: ProfileCluster;
  pipeline_used?: string;
  pipeline_variant?: string;
}

export interface ProfileCluster {
  dominant_cluster:
    | "DATA_IT"
    | "FINANCE_LEGAL"
    | "SUPPLY_OPS"
    | "MARKETING_SALES"
    | "ENGINEERING_INDUSTRY"
    | "ADMIN_HR"
    | "OTHER";
  dominance_percent: number;
  distribution_percent: Record<string, number>;
  skills_count: number;
  confidence: number;
  note: "TRANSVERSAL" | "LOW_SIGNAL" | null;
}

/**
 * Upload a CV file (PDF or TXT) and run deterministic baseline skill extraction.
 * POST /profile/parse-file (multipart/form-data)
 * No LLM required. Same file → same output.
 */
export async function parseFile(file: File): Promise<ParseFileResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/profile/parse-file`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<ParseFileResponse>;
}

/**
 * Upload a CV file and attempt legacy LLM enrichment (DEV-only).
 * POST /profile/parse-file?enrich_llm=1
 */
export async function parseFileEnriched(file: File): Promise<ParseFileResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/profile/parse-file?enrich_llm=1`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<ParseFileResponse>;
}

// ============================================================================
// Apply Pack v0
// ============================================================================

export interface ApplyPackOfferIn {
  id: string;
  title: string;
  company?: string | null;
  country?: string | null;
  city?: string | null;
  description?: string | null;
  skills?: string[];
  url?: string | null;
}

export interface ApplyPackRequest {
  profile: { id?: string; skills: string[]; name?: string };
  offer: ApplyPackOfferIn;
  matched_core?: string[];
  missing_core?: string[];
  enrich_llm?: 0 | 1;
}

export interface ApplyPackMeta {
  offer_id: string;
  offer_title: string;
  company: string;
  matched_core: string[];
  missing_core: string[];
  generated_at: string;
}

export interface ApplyPackResponse {
  mode: "baseline" | "baseline+llm";
  cv_text: string;
  letter_text: string;
  meta: ApplyPackMeta;
  warnings: string[];
}

/**
 * Generate a tailored CV + cover letter for a given offer.
 * POST /apply-pack
 * Baseline mode always works (no LLM key required).
 */
export async function applyPack(payload: ApplyPackRequest): Promise<ApplyPackResponse> {
  const res = await fetch(`${API_BASE}/apply-pack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<ApplyPackResponse>;
}

// ============================================================================
// Profile Key Skills (display-only ranking for AnalyzePage)
// ============================================================================

export interface KeySkillItem {
  label: string;
  reason: "weighted" | "idf" | "standard";
  idf: number | null;
  weighted: boolean;
}

export interface KeySkillsResponse {
  key_skills: KeySkillItem[];       // max 12 — shown first
  all_skills_ranked: KeySkillItem[]; // all, max 40 — for modal
}

/**
 * Rank validated ESCO skills by signal importance (IDF / ROME weights).
 * POST /profile/key-skills
 * Deterministic. No scoring change.
 */
export async function fetchKeySkills(
  validated_items: ValidatedItem[],
  rome_code?: string | null,
): Promise<KeySkillsResponse> {
  const res = await fetch(`${API_BASE}/profile/key-skills`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ validated_items, rome_code: rome_code ?? null }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<KeySkillsResponse>;
}

export async function runCvDelta(request: CvDeltaRequest): Promise<CvDeltaResponse> {
  const form = new FormData();
  form.append("file", request.file);
  form.append("with_llm", request.withLlm ? "true" : "false");
  if (request.withLlm) {
    form.append("llm_provider", request.provider ?? "openai");
    form.append("llm_model", request.model ?? "gpt-4o-mini");
  }

  const res = await fetch(`${API_BASE}/dev/cv-delta`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new CvDeltaApiError(res.status, text || `API ${res.status}`);
  }

  const data = (await res.json()) as CvDeltaResponse;
  return data;
}

// ============================================================================
// CV Generator — for-offer endpoint
// ============================================================================

export interface InboxContextPayload {
  matched_skills?: string[];
  missing_skills?: string[];
  offer_cluster?: string;
  profile_cluster?: string;
}

export interface CvAtsNotes {
  matched_keywords: string[];
  missing_keywords: string[];
  ats_score_estimate: number;
}

export interface CvExperienceBlock {
  title: string;
  company: string;
  bullets: string[];
  tools: string[];
  autonomy: "CONTRIB" | "COPILOT" | "LEAD";
  impact: string | null;
}

export interface CvDocument {
  summary: string;
  keywords_injected: string[];
  experience_blocks: CvExperienceBlock[];
  ats_notes: CvAtsNotes;
  meta: {
    offer_id: string;
    profile_fingerprint: string;
    prompt_version: string;
    cache_hit: boolean;
    fallback_used: boolean;
  };
}

export interface ForOfferResponse {
  ok: boolean;
  document: CvDocument;
  preview_text: string;
  context_used: boolean;
  duration_ms: number;
}

export interface CvHtmlMeta {
  offer_id: string;
  prompt_version: string;
  cache_hit: boolean;
  fallback_used: boolean;
  template_version: string;
}

export interface CvHtmlResponse {
  ok: boolean;
  html: string;
  meta: CvHtmlMeta;
  duration_ms: number;
}

export interface CoverLetterBlock {
  label: "hook" | "match" | "value" | "closing";
  text: string;
}

export interface CoverLetterDocument {
  blocks: CoverLetterBlock[];
  meta: {
    offer_id: string;
    template_version: string;
    context_used: boolean;
  };
}

export interface ForOfferLetterResponse {
  ok: boolean;
  document: CoverLetterDocument;
  preview_text: string;
  duration_ms: number;
}

// ============================================================================
// Offer Detail (structured description)
// ============================================================================

export interface DescriptionStructured {
  summary: string;
  missions: string[];
  profile: string[];
  competences: string[];
  context: string;
  has_headings: boolean;
  source: "structured" | "fallback";
}

// ── Compass signal layer types ────────────────────────────────────────────────

export interface ToolNote {
  tool_key: string;
  status: "UNSPECIFIED" | "SPECIFIED" | "UNKNOWN";
  sense: string | null;
  hits: string[];
}

export interface SkillRefItem {
  uri: string | null;
  label: string;
}

export interface CompassExplainCompact {
  score_core: number;
  confidence: "LOW" | "MED" | "HIGH";
  cluster_level: "STRICT" | "NEIGHBOR" | "OUT";
  rare_signal_level: "LOW" | "MED" | "HIGH";
  incoherence_reasons: string[];
  matched_count: number;
  missing_count: number;
  sector_signal: number | null;
  sector_signal_level: "LOW" | "MED" | "HIGH" | null;
  sector_signal_note: string | null;
}

export interface ExplainPayloadV1Full {
  score_core: number;
  confidence: "LOW" | "MED" | "HIGH";
  incoherence_reasons: string[];
  matched_skills: SkillRefItem[];
  missing_offer_skills: SkillRefItem[];
  coverage_ratio: number;
  rare_signal: number;
  rare_signal_level: "LOW" | "MED" | "HIGH";
  generic_ratio: number;
  cluster_level: "STRICT" | "NEIGHBOR" | "OUT";
  tool_notes: ToolNote[];
  sector_signal: number | null;
  sector_signal_level: "LOW" | "MED" | "HIGH" | null;
  sector_signal_note: string | null;
  debug_trace: unknown | null;
}

export interface DescriptionStructuredV1 {
  missions: string[];
  requirements: string[];
  tools_stack: string[];
  context: string[];
  red_flags: string[];
  extracted_sections: Record<string, string> | null;
}

export interface OfferDetailResponse {
  id: string;
  source: string;
  title: string;
  description: string;
  display_description: string;
  publication_date: string | null;
  company: string | null;
  city: string | null;
  country: string | null;
  contract_duration: number | null;
  start_date: string | null;
  description_structured: DescriptionStructured | null;
  description_structured_v1?: DescriptionStructuredV1 | null;
  explain_v1_full?: ExplainPayloadV1Full | null;
  offer_intelligence?: OfferIntelligence | null;
  semantic_explainability?: SemanticExplainability | null;
}

export interface ProfileSemanticContext {
  dominant_role_block?: string | null;
  dominant_domains?: string[];
  top_profile_signals?: string[];
  profile_summary?: string | null;
}

/**
 * Fetch single offer with structured description sections.
 * GET /offers/{offer_id}/detail
 */
export async function fetchOfferDetail(
  offerId: string,
  profileSemanticContext?: ProfileSemanticContext | null
): Promise<OfferDetailResponse> {
  const params = new URLSearchParams();
  if (profileSemanticContext?.dominant_role_block) {
    params.set("profile_role_block", profileSemanticContext.dominant_role_block);
  }
  for (const domain of profileSemanticContext?.dominant_domains ?? []) {
    if (domain) params.append("profile_domains", domain);
  }
  for (const signal of profileSemanticContext?.top_profile_signals ?? []) {
    if (signal) params.append("profile_signals", signal);
  }
  if (profileSemanticContext?.profile_summary) {
    params.set("profile_summary", profileSemanticContext.profile_summary);
  }
  const query = params.toString();
  const url = `${API_BASE}/offers/${encodeURIComponent(offerId)}/detail${query ? `?${query}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${txt}`);
  }
  return res.json() as Promise<OfferDetailResponse>;
}

/**
 * Generate an inbox-contextualised CV for a given offer.
 * POST /documents/cv/for-offer
 *
 * @param offerId   - Offer identifier (from InboxItem.offer_id)
 * @param profile   - Profile payload (from profileStore.userProfile)
 * @param context   - Optional inbox match context (matched/missing skills)
 */
export async function generateCvForOffer(
  offerId: string,
  profile: Record<string, unknown>,
  context?: InboxContextPayload,
): Promise<ForOfferResponse> {
  const url = `${API_BASE}/documents/cv/for-offer`;
  const body: Record<string, unknown> = { offer_id: offerId, profile, lang: "fr" };
  if (context) body.context = context;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.warn(JSON.stringify({
      event: "DOCUMENTS_REQUEST_FAIL",
      endpoint: "/documents/cv/for-offer",
      status: res.status,
      offer_id: offerId,
    }));
    throw new Error("Génération du CV échouée. Réessayez.");
  }

  return res.json() as Promise<ForOfferResponse>;
}

/**
 * Generate a rendered HTML CV for a given offer.
 * POST /documents/cv/html/for-offer
 */
export async function generateCvHtmlForOffer(
  offerId: string,
  profile: Record<string, unknown>,
  context?: InboxContextPayload,
): Promise<CvHtmlResponse> {
  const url = `${API_BASE}/documents/cv/html/for-offer`;
  const body: Record<string, unknown> = { offer_id: offerId, profile, lang: "fr" };
  if (context) body.context = context;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.warn(JSON.stringify({
      event: "DOCUMENTS_CV_HTML_FAILED",
      endpoint: "/documents/cv/html/for-offer",
      status: res.status,
      offer_id: offerId,
    }));
    throw new Error("Génération du CV HTML échouée. Réessayez.");
  }

  return res.json() as Promise<CvHtmlResponse>;
}

// ============================================================================
// Analyze Page — Cluster-Aware AI Skill Recovery (DEV-only)
// ============================================================================

export interface RecoverSkillsRequest {
  cluster: string;
  ignored_tokens: string[];
  noise_tokens?: string[];
  validated_esco_labels?: string[];
  profile_text_excerpt?: string;
  profile_fingerprint?: string | null;
  extracted_text_hash?: string | null;
  force?: boolean;
}

export interface RecoveredSkillItem {
  label: string;
  kind: string;       // tool | language | method | framework | certification | domain
  confidence: number; // 0.0–1.0
  source: string;     // ignored_token | noise_token | recombined | cv_excerpt
  evidence: string;
  why_cluster_fit: string;
}

export interface RecoverSkillsResponse {
  recovered_skills: RecoveredSkillItem[];
  ai_available: boolean;
  ai_error?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  cluster: string;
  ignored_token_count: number;
  noise_token_count: number;
  cache_hit?: boolean | null;
  ai_fired?: boolean | null;
  profile_fingerprint?: string | null;
  request_hash?: string | null;
  raw_count?: number | null;
  candidate_count?: number | null;
  dropped_count?: number | null;
  noise_ratio?: number | null;
  tech_density?: number | null;
  dropped_reasons?: Record<string, number> | null;
  error: string | null;
  request_id: string;
}

/**
 * Recover skills missed by deterministic parsing (DEV-only AI endpoint).
 * POST /analyze/recover-skills
 * Requires ELEVIA_DEV_TOOLS=1 + OPENAI_API_KEY on the backend.
 * Results are display-only — never injected into matching.
 */
export async function fetchRecoverSkills(
  payload: RecoverSkillsRequest,
): Promise<RecoverSkillsResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/analyze/recover-skills`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    return {
      recovered_skills: [],
      ai_available: false,
      ai_error: "NETWORK_ERROR",
      error_code: "NETWORK_ERROR",
      error_message: "Network error",
      cluster: payload.cluster,
      ignored_token_count: payload.ignored_tokens.length,
      noise_token_count: payload.noise_tokens?.length ?? 0,
      cache_hit: false,
      ai_fired: false,
      profile_fingerprint: payload.profile_fingerprint ?? null,
      request_hash: null,
      raw_count: payload.ignored_tokens.length + (payload.noise_tokens?.length ?? 0),
      candidate_count: 0,
      dropped_count: 0,
      noise_ratio: 1,
      tech_density: 0,
      error: "NETWORK_ERROR",
      request_id: "",
    };
  }
  if (!res.ok) {
    const fallbackCode = res.status === 422 ? "INVALID_REQUEST" : "UNKNOWN_ERROR";
    const fallback: RecoverSkillsResponse = {
      recovered_skills: [],
      ai_available: false,
      ai_error: fallbackCode,
      error_code: fallbackCode,
      error_message: `HTTP ${res.status}`,
      cluster: payload.cluster,
      ignored_token_count: payload.ignored_tokens.length,
      noise_token_count: payload.noise_tokens?.length ?? 0,
      cache_hit: false,
      ai_fired: false,
      profile_fingerprint: payload.profile_fingerprint ?? null,
      request_hash: null,
      raw_count: payload.ignored_tokens.length + (payload.noise_tokens?.length ?? 0),
      candidate_count: 0,
      dropped_count: 0,
      noise_ratio: 1,
      tech_density: 0,
      error: fallbackCode,
      request_id: "",
    };
    try {
      const data = await res.json();
      const errorObj = data?.error;
      const code = errorObj?.code || data?.error_code || fallbackCode;
      const message = errorObj?.message || data?.error_message || `HTTP ${res.status}`;
      return {
        ...fallback,
        ai_error: code,
        error_code: code,
        error_message: message,
        error: code,
        request_id: errorObj?.request_id || data?.request_id || "",
      };
    } catch {
      return fallback;
    }
  }
  return res.json() as Promise<RecoverSkillsResponse>;
}

// ============================================================================
// Analyze Page — AI Quality Audit (DEV-only)
// ============================================================================

export interface AuditAIQualityRequest {
  cluster: string;
  validated_esco_labels: string[];
  recovered_skills: string[];
}

export interface AuditAIQualityResponse {
  validated_esco_count: number;
  ai_recovered_count: number;
  ai_overlap_with_offers: number;
  ai_unique_vs_esco: number;
  cluster_coherence_score: number;
  noise_ratio_estimate: number;
  offers_considered: number;
  request_id: string;
  error_code?: string | null;
  error_message?: string | null;
}

export async function fetchAuditAiQuality(
  payload: AuditAIQualityRequest,
): Promise<AuditAIQualityResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/analyze/audit-ai-quality`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    return {
      validated_esco_count: 0,
      ai_recovered_count: 0,
      ai_overlap_with_offers: 0,
      ai_unique_vs_esco: 0,
      cluster_coherence_score: 0,
      noise_ratio_estimate: 0,
      offers_considered: 0,
      request_id: "",
      error_code: "NETWORK_ERROR",
      error_message: "Network error",
    };
  }

  if (!res.ok) {
    const fallbackCode = res.status === 422 ? "INVALID_REQUEST" : "UNKNOWN_ERROR";
    try {
      const data = await res.json();
      return {
        validated_esco_count: 0,
        ai_recovered_count: 0,
        ai_overlap_with_offers: 0,
        ai_unique_vs_esco: 0,
        cluster_coherence_score: 0,
        noise_ratio_estimate: 0,
        offers_considered: 0,
        request_id: data?.request_id || "",
        error_code: data?.error_code || fallbackCode,
        error_message: data?.error_message || `HTTP ${res.status}`,
      };
    } catch {
      return {
        validated_esco_count: 0,
        ai_recovered_count: 0,
        ai_overlap_with_offers: 0,
        ai_unique_vs_esco: 0,
        cluster_coherence_score: 0,
        noise_ratio_estimate: 0,
        offers_considered: 0,
        request_id: "",
        error_code: fallbackCode,
        error_message: `HTTP ${res.status}`,
      };
    }
  }

  return res.json() as Promise<AuditAIQualityResponse>;
}

/**
 * Generate a deterministic cover letter for a given offer.
 * POST /documents/letter/for-offer
 */
export async function generateLetterForOffer(
  offerId: string,
  profile: Record<string, unknown>,
  context?: InboxContextPayload,
): Promise<ForOfferLetterResponse> {
  const url = `${API_BASE}/documents/letter/for-offer`;
  const body: Record<string, unknown> = { offer_id: offerId, profile, lang: "fr" };
  if (context) body.context = context;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.warn(JSON.stringify({
      event: "DOCUMENTS_REQUEST_FAIL",
      endpoint: "/documents/letter/for-offer",
      status: res.status,
      offer_id: offerId,
    }));
    throw new Error("Génération de la lettre échouée. Réessayez.");
  }

  return res.json() as Promise<ForOfferLetterResponse>;
}

// ── Market Insights ───────────────────────────────────────────────────────────

export interface MarketInsightsCountry {
  country: string;
  count: number;
}

export interface MarketInsightsSector {
  sector: string;
  label: string;
  count: number;
}

export interface MarketInsightsSkill {
  skill: string;
  count: number;
  dominant_sector: string;
  display_label?: string;
}

export interface MarketInsightsMatrixEntry {
  sector: string;
  skill: string;
  count: number;
  relative: number;
}

export interface MarketInsightsDistinctiveSkill {
  sector: string;
  skill: string;
  count: number;
  sector_share: number;
  global_share: number;
  distinctiveness: number;
  display_label?: string;
}

export interface MarketInsightsSectorCountry {
  sector: string;
  country: string;
  count: number;
}

export interface MarketInsightsSectorCompany {
  sector: string;
  company: string;
  count: number;
}

export interface MarketInsightsCompany {
  company: string;
  count: number;
}

export interface MarketInsightsRole {
  role: string;
  count: number;
  skills?: string[];
  mode?: string;
}

export interface MarketInsightsSectorRole extends MarketInsightsRole {
  sector: string;
}

export interface MarketInsightsResponse {
  total_offers: number;
  total_countries: number;
  total_sectors: number;
  total_skills: number;
  country_counts?: MarketInsightsCountry[];
  top_countries: MarketInsightsCountry[];
  sectors_distribution: MarketInsightsSector[];
  top_skills: MarketInsightsSkill[];
  sector_skill_matrix: MarketInsightsMatrixEntry[];
  sector_distinctive_skills?: MarketInsightsDistinctiveSkill[];
  sector_country_matrix: MarketInsightsSectorCountry[];
  sector_country_counts?: MarketInsightsSectorCountry[];
  sector_companies: MarketInsightsSectorCompany[];
  sector_company_counts?: MarketInsightsSectorCompany[];
  company_counts?: MarketInsightsCompany[];
  key_insights: string[];
  top_roles?: MarketInsightsRole[];
  sector_top_roles?: MarketInsightsSectorRole[];
}

export async function fetchMarketInsights(): Promise<MarketInsightsResponse> {
  const res = await fetch(`${API_BASE}/insights/vie-market`);
  if (!res.ok) throw new Error(`Market insights fetch failed: ${res.status}`);
  return res.json() as Promise<MarketInsightsResponse>;
}
