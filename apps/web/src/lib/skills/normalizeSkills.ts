export type UriLabelMap = Record<string, string>;

export type NormalizedSkillSet = {
  uris: string[];
  labels: string[];
};

export function labelFromUri(uri: string): string {
  const raw = uri.split("/").pop() ?? uri;
  const token = raw.includes(":") ? raw.split(":").pop() ?? raw : raw;
  return token.replace(/[_-]+/g, " ").trim();
}

export function buildUriLabelMap(
  validatedItems?: Array<{ uri: string; label: string }>,
  resolvedToEsco?: Array<{ esco_uri: string; esco_label?: string }>,
): UriLabelMap {
  const map: UriLabelMap = {};
  for (const item of validatedItems ?? []) {
    if (item?.uri && item?.label) {
      map[item.uri] = item.label;
    }
  }
  for (const item of resolvedToEsco ?? []) {
    if (item?.esco_uri) {
      map[item.esco_uri] = item.esco_label ?? map[item.esco_uri] ?? labelFromUri(item.esco_uri);
    }
  }
  return map;
}

export function normalizeProfileSkills(
  profile: { skills_uri_effective?: string[]; skills_uri?: string[]; skills_uri_promoted?: string[] } | null | undefined,
  labelMap: UriLabelMap,
): NormalizedSkillSet {
  if (!profile) return { uris: [], labels: [] };
  const raw = profile.skills_uri_effective
    ?? [...(profile.skills_uri ?? []), ...(profile.skills_uri_promoted ?? [])];

  const uniq = new Set<string>();
  for (const uri of raw) {
    if (typeof uri === "string" && uri.trim()) uniq.add(uri);
  }

  const uris = [...uniq].sort((a, b) => a.localeCompare(b));
  const labels = uris.map((uri) => labelMap[uri] ?? labelFromUri(uri));
  return { uris, labels };
}

export function mapLabelsToUris(labels: string[], labelMap: UriLabelMap): string[] {
  const byLower = new Map<string, string>();
  for (const [uri, label] of Object.entries(labelMap)) {
    if (!label) continue;
    const key = label.toLowerCase().trim();
    if (key && !byLower.has(key)) byLower.set(key, uri);
  }
  const out: string[] = [];
  for (const label of labels) {
    const uri = byLower.get(label.toLowerCase().trim());
    if (uri && !out.includes(uri)) out.push(uri);
  }
  return out;
}
