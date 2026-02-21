const API_BASE =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "";

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
    throw new Error(text || `API ${res.status}`);
  }

  const data = (await res.json()) as CvDeltaResponse;
  return data;
}
