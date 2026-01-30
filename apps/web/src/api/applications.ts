const API_BASE =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "";

export type ApplicationStatus = "shortlisted" | "applied" | "dismissed";

export interface ApplicationItem {
  id: string;
  offer_id: string;
  status: ApplicationStatus;
  note: string | null;
  next_follow_up_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationListResponse {
  items: ApplicationItem[];
}

export interface ApplicationCreatePayload {
  offer_id: string;
  status: ApplicationStatus;
  note?: string | null;
  next_follow_up_date?: string | null;
}

export interface ApplicationUpdatePayload {
  status?: ApplicationStatus;
  note?: string | null;
  next_follow_up_date?: string | null;
}

export async function listApplications(): Promise<ApplicationListResponse> {
  const res = await fetch(`${API_BASE}/applications`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getApplication(offerId: string): Promise<ApplicationItem> {
  const res = await fetch(`${API_BASE}/applications/${encodeURIComponent(offerId)}`);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function upsertApplication(payload: ApplicationCreatePayload): Promise<ApplicationItem> {
  const res = await fetch(`${API_BASE}/applications`, {
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
  const res = await fetch(`${API_BASE}/applications/${encodeURIComponent(offerId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export async function deleteApplication(offerId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/applications/${encodeURIComponent(offerId)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
}
