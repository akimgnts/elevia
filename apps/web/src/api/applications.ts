import { apiFetch } from "../lib/api";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "";

export type ApplicationStatus =
  | "saved"
  | "cv_ready"
  | "applied"
  | "follow_up"
  | "interview"
  | "rejected"
  | "won"
  | "archived";

export interface ApplicationItem {
  id: string;
  user_id: string | null;
  offer_id: string;
  offer_title: string | null;
  offer_company: string | null;
  offer_city: string | null;
  offer_country: string | null;
  status: ApplicationStatus;
  source: string;
  note: string | null;
  next_follow_up_date: string | null;
  current_cv_cache_key: string | null;
  current_letter_cache_key: string | null;
  created_at: string;
  updated_at: string;
  applied_at: string | null;
  last_status_change_at: string | null;
  strategy_hint: string | null;
}

export interface ApplicationListResponse {
  items: ApplicationItem[];
}

export interface ApplicationHistoryItem {
  id: string;
  application_id: string;
  from_status: string | null;
  to_status: string;
  changed_at: string;
  note: string | null;
}

export interface ApplicationHistoryResponse {
  items: ApplicationHistoryItem[];
}

export interface ApplicationCreatePayload {
  offer_id: string;
  status: ApplicationStatus;
  source?: string;
  note?: string | null;
  next_follow_up_date?: string | null;
}

export interface ApplicationUpdatePayload {
  status?: ApplicationStatus;
  note?: string | null;
  next_follow_up_date?: string | null;
  strategy_hint?: string | null;
}

export interface PreparePayload {
  profile?: Record<string, unknown>;
  enrich_llm?: 0 | 1;
}

export interface PrepareResponse {
  ok: boolean;
  application_id: string;
  offer_id: string;
  run_id: string;
  cv_cache_key: string | null;
  letter_cache_key: string | null;
  status: string;
  warnings: string[];
}

export async function listApplications(): Promise<ApplicationListResponse> {
  const res = await apiFetch(`${API_BASE}/applications`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getApplication(offerId: string): Promise<ApplicationItem> {
  const res = await apiFetch(`${API_BASE}/applications/${encodeURIComponent(offerId)}`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getApplicationHistory(offerId: string): Promise<ApplicationHistoryResponse> {
  const res = await apiFetch(
    `${API_BASE}/applications/${encodeURIComponent(offerId)}/history`
  );
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function upsertApplication(
  payload: ApplicationCreatePayload
): Promise<ApplicationItem> {
  const res = await apiFetch(`${API_BASE}/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function patchApplication(
  offerId: string,
  payload: ApplicationUpdatePayload
): Promise<ApplicationItem> {
  const res = await apiFetch(
    `${API_BASE}/applications/${encodeURIComponent(offerId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function deleteApplication(offerId: string): Promise<void> {
  const res = await apiFetch(
    `${API_BASE}/applications/${encodeURIComponent(offerId)}`,
    { method: "DELETE" }
  );
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
}

export async function prepareApplication(
  offerId: string,
  payload: PreparePayload = {}
): Promise<PrepareResponse> {
  const res = await apiFetch(
    `${API_BASE}/applications/${encodeURIComponent(offerId)}/prepare`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}
