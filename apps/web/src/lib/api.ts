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

export interface InboxItem {
  offer_id: string;
  title: string;
  company: string | null;
  country: string | null;
  city: string | null;
  score: number;
  reasons: string[];
  matched_skills?: string[];
  missing_skills?: string[];
  rome?: { rome_code: string; rome_label: string } | null;
  rome_competences?: Array<{
    competence_code: string;
    competence_label: string;
    esco_uri?: string | null;
  }> | null;
}

export interface InboxResponse {
  profile_id: string;
  items: InboxItem[];
  total_matched: number;
  total_decided: number;
}

export async function fetchInbox(
  profile: unknown,
  profileId: string,
  minScore = 65,
  limit = 20
): Promise<InboxResponse> {
  const url = `${API_BASE}/inbox`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId, profile, min_score: minScore, limit }),
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
  filename: string;
  content_type: string;
  extracted_text_length: number;
  canonical_count: number;
  raw_detected: number;
  validated_skills: number;
  filtered_out: number;
  validated_items: ValidatedItem[];
  skill_groups: SkillGroupItem[];
  skills_raw: string[];
  skills_canonical: string[];
  profile: { id: string; skills: string[]; skills_source: string };
  warnings: string[];
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
