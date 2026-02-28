/**
 * API client for backend calls.
 * Uses VITE_API_BASE_URL or defaults to relative path.
 */

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "";

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

export interface ExplainBlock {
  matched_display: SkillExplainItem[];  // top 6 for card
  missing_display: SkillExplainItem[];  // top 6 for card
  matched_full: SkillExplainItem[];     // all matched, max 30
  missing_full: SkillExplainItem[];     // all missing, max 30
  breakdown: ExplainBreakdown;
}

export interface InboxItem {
  offer_id: string;
  id?: string;
  title: string;
  company: string | null;
  country: string | null;
  city: string | null;
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
  signal_score?: number;
  coherence?: "ok" | "suspicious";
  rome?: { rome_code: string; rome_label: string } | null;
  rome_competences?: Array<{
    competence_code: string;
    competence_label: string;
    esco_uri?: string | null;
  }> | null;
  explain?: ExplainBlock | null;
}

export interface InboxMeta {
  profile_cluster?: string;
  gating_mode?: "IN_DOMAIN" | "OUT_OF_DOMAIN";
  coverage_before?: number;
  coverage_after?: number;
  suggest_out_of_domain?: boolean;
  out_of_domain_count?: number;
  cluster_distribution_top20?: Record<string, number>;
}

export interface InboxResponse {
  profile_id: string;
  items: InboxItem[];
  total_matched: number;
  total_decided: number;
  meta?: InboxMeta;
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

export async function fetchInbox(
  profile: unknown,
  profileId: string,
  minScore = 65,
  limit = 20,
  explain = true,
  domainMode: "in_domain" | "all" = "in_domain",
): Promise<InboxResponse> {
  const url = `${API_BASE}/inbox?domain_mode=${encodeURIComponent(domainMode)}`;
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
  ai_available: boolean;
  ai_added_count: number;
  ai_error?: string | null;
  filename: string;
  content_type: string;
  extracted_text_length: number;
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
 * Upload a CV file and attempt LLM enrichment (best-effort).
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
    const txt = await res.text().catch(() => "");
    throw new Error(`CV génération échouée (${res.status}): ${txt}`);
  }

  return res.json() as Promise<ForOfferResponse>;
}
