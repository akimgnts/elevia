export type NormalizedSkillRef = {
  label: string;
  uri?: string | null;
  confidence?: number;
  method?: string;
  source?: string;
};

type NormalizedToolRef = {
  label: string;
};

type NormalizedSkillLink = {
  skill: NormalizedSkillRef;
  tools: NormalizedToolRef[];
  context?: string;
  autonomy_level?: string;
};

type NormalizedExperience = {
  title?: string;
  company?: string;
  start_date?: string;
  end_date?: string;
  responsibilities?: string[];
  description?: string;
  tools?: NormalizedSkillRef[];
  canonical_skills_used?: NormalizedSkillRef[];
  achievements?: string[];
  quantified_signals?: string[];
  impact_signals?: string[];
  context_tags?: string[];
  skills?: string[];
  skill_links?: NormalizedSkillLink[];
  [key: string]: unknown;
};

type NormalizedCareerProfile = {
  summary_master?: string;
  selected_skills?: Array<NormalizedSkillRef | string>;
  experiences?: NormalizedExperience[];
  skills_highlights?: string[];
  [key: string]: unknown;
};

type NormalizedProfile = {
  career_profile?: NormalizedCareerProfile;
  canonical_skills?: Array<NormalizedSkillRef | string>;
  skills?: string[];
  experiences?: NormalizedExperience[];
  skills_uri?: string[];
  domain_uris?: string[];
  [key: string]: unknown;
};

const SHORT_FRAGMENT_ALLOWLIST = new Set(["r", "c", "b2", "c1", "c2"]);

function compactSeparators(value: string): string {
  return value
    .replace(/[|]+/g, ",")
    .replace(/,+/g, ",")
    .replace(/\s+/g, " ")
    .replace(/\s+,/g, ",")
    .replace(/,\s*/g, ", ")
    .trim()
    .replace(/^,|,$/g, "")
    .trim();
}

function normalizeToken(value: string): string {
  return compactSeparators(value)
    .replace(/[;]+/g, ",")
    .replace(/\s+-\s+/g, " ")
    .trim()
    .toLowerCase();
}

function isBrokenFragment(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return true;
  if (SHORT_FRAGMENT_ALLOWLIST.has(normalized)) return false;
  if (normalized.length < 2) return true;
  return !/[a-zà-öø-ÿ0-9]/i.test(normalized);
}

function dedupeValues(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const normalized = normalizeToken(value);
    if (isBrokenFragment(normalized)) continue;
    if (seen.has(normalized)) continue;
    seen.add(normalized);
    out.push(normalized);
  }
  return out;
}

export function normalizeText(value: unknown): string {
  if (typeof value !== "string") return "";
  const parts = compactSeparators(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  return dedupeValues(parts).join(", ");
}

function normalizeStringList(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return dedupeValues(
    values.flatMap((value) => {
      if (typeof value === "string") return compactSeparators(value).split(",");
      if (value && typeof value === "object") {
        const record = value as Record<string, unknown>;
        if (typeof record.label === "string") return compactSeparators(record.label).split(",");
        if (typeof record.name === "string") return compactSeparators(record.name).split(",");
        if (typeof record.raw === "string") return compactSeparators(record.raw).split(",");
      }
      return [];
    }),
  );
}

function normalizeSkillRef(value: unknown): NormalizedSkillRef | null {
  if (typeof value === "string") {
    const label = normalizeText(value);
    return label ? { label } : null;
  }
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const label = normalizeText(record.label);
  if (!label) return null;
  return {
    ...record,
    label,
    uri: typeof record.uri === "string" ? record.uri : record.uri === null ? null : undefined,
    confidence: typeof record.confidence === "number" ? record.confidence : undefined,
    method: typeof record.method === "string" ? record.method : undefined,
    source: typeof record.source === "string" ? record.source : undefined,
  };
}

export function normalizeSkills(values: unknown): NormalizedSkillRef[] {
  if (!Array.isArray(values)) return [];
  const seen = new Set<string>();
  const out: NormalizedSkillRef[] = [];
  for (const value of values) {
    const item = normalizeSkillRef(value);
    if (!item) continue;
    const key = item.uri || item.label;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

function normalizeTools(values: unknown): NormalizedSkillRef[] {
  return normalizeSkills(values);
}

function normalizeSkillLinks(values: unknown): NormalizedSkillLink[] {
  if (!Array.isArray(values)) return [];
  const seen = new Set<string>();
  const out: NormalizedSkillLink[] = [];

  for (const value of values) {
    if (!value || typeof value !== "object") continue;
    const record = value as Record<string, unknown>;
    const skill = normalizeSkillRef(record.skill);
    if (!skill) continue;
    const tools = normalizeTools(record.tools).map((tool) => ({ label: tool.label }));
    const context = normalizeText(record.context);
    const key = [skill.uri || skill.label, tools.map((tool) => tool.label).join("|"), context].join("::");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      skill,
      tools,
      ...(context ? { context } : {}),
      ...(typeof record.autonomy_level === "string" ? { autonomy_level: record.autonomy_level } : {}),
    });
  }

  return out;
}

export function normalizeExperiences(values: unknown): NormalizedExperience[] {
  if (!Array.isArray(values)) return [];
  return values
    .filter((value): value is Record<string, unknown> => Boolean(value && typeof value === "object"))
    .map((experience) => {
      const responsibilities = normalizeStringList(experience.responsibilities);
      const description = normalizeText(experience.description);
      return {
        ...experience,
        title: typeof experience.title === "string" ? compactSeparators(experience.title) : "",
        company: typeof experience.company === "string" ? compactSeparators(experience.company) : "",
        start_date: typeof experience.start_date === "string" ? experience.start_date.trim() : "",
        end_date: typeof experience.end_date === "string" ? experience.end_date.trim() : "",
        ...(description ? { description } : {}),
        responsibilities,
        tools: normalizeTools(experience.tools),
        canonical_skills_used: normalizeSkills(experience.canonical_skills_used),
        achievements: normalizeStringList(experience.achievements),
        quantified_signals: normalizeStringList(experience.quantified_signals),
        impact_signals: normalizeStringList(experience.impact_signals),
        context_tags: normalizeStringList(experience.context_tags),
        skills: normalizeStringList(experience.skills),
        skill_links: normalizeSkillLinks(experience.skill_links),
      };
    });
}

export function normalizeProfile<T extends NormalizedProfile>(profile: T): T {
  const careerProfile =
    profile.career_profile && typeof profile.career_profile === "object"
      ? profile.career_profile
      : {};
  const selectedSkills = normalizeSkills(careerProfile.selected_skills);
  const canonicalSkills = normalizeSkills(profile.canonical_skills);
  const profileSkills = normalizeStringList(profile.skills);
  const careerExperiences = normalizeExperiences(careerProfile.experiences);
  const rootExperiences = normalizeExperiences(profile.experiences);

  return {
    ...profile,
    canonical_skills: canonicalSkills,
    skills: profileSkills,
    experiences: rootExperiences.length > 0 ? rootExperiences : profile.experiences,
    career_profile: {
      ...careerProfile,
      summary_master: normalizeText(careerProfile.summary_master),
      selected_skills: selectedSkills,
      skills_highlights: selectedSkills.slice(0, 14).map((skill) => skill.label),
      experiences: careerExperiences,
    },
  };
}
