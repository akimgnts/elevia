import { normalizeExperiences, normalizeSkills, normalizeText } from "./normalizers";

export type SuggestedSummary = {
  text: string;
  confidence: number;
  evidence: string[];
};

export type SuggestedExperience = {
  title: string;
  organization: string;
  start_date: string;
  end_date: string;
  missions: string[];
  tools: string[];
  skills: string[];
  signals: {
    autonomy: string;
    impact: string[];
  };
  confidence: number;
  evidence: string[];
};

export type SuggestedSkill = {
  label: string;
  type: "hard" | "tool" | "domain";
  confidence: number;
  evidence: string[];
};

export type SuggestedProject = {
  name: string;
  description: string;
  tools: string[];
  confidence: number;
  evidence: string[];
};

export type SuggestedCertification = {
  name: string;
  issuer: string;
  confidence: number;
  evidence: string[];
};

export type SuggestedLanguage = {
  language: string;
  level: string;
  confidence: number;
  evidence: string[];
};

export type ProfileReconstructionInput = {
  cv_text?: string;
  career_profile?: Record<string, unknown> | null;
  experiences?: unknown[];
  selected_skills?: unknown[];
  structured_signal_units?: unknown[];
  validated_items?: unknown[];
  canonical_skills?: unknown[];
};

export type ProfileReconstructionOutput = {
  suggested_summary: SuggestedSummary;
  suggested_experiences: SuggestedExperience[];
  suggested_skills: SuggestedSkill[];
  suggested_projects: SuggestedProject[];
  suggested_certifications: SuggestedCertification[];
  suggested_languages: SuggestedLanguage[];
};

type SkillSource = "selected" | "canonical" | "validated" | "experience_skill" | "experience_tool" | "structured";

const TOOL_HINTS = new Set([
  "airtable",
  "excel",
  "figma",
  "google analytics",
  "hubspot",
  "looker",
  "notion",
  "power bi",
  "powerbi",
  "python",
  "salesforce",
  "sap",
  "sql",
  "tableau",
]);

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function cleanLabel(value: unknown): string {
  if (typeof value !== "string") return "";
  return normalizeText(value.replace(/\bpowerbi\b/gi, "power bi"));
}

function stringField(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string") {
      const cleaned = value.trim();
      if (cleaned) return cleaned;
    }
  }
  return "";
}

function arrayField(record: Record<string, unknown>, keys: string[]): unknown[] {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) return value;
  }
  return [];
}

function compactEvidence(values: unknown[], fallback?: string): string[] {
  const evidence = values
    .map((value) => {
      if (typeof value === "string") return value.trim();
      if (value && typeof value === "object") {
        const record = asRecord(value);
        return (
          stringField(record, ["source_text", "evidence", "raw", "label", "name", "title", "description"]) ||
          JSON.stringify(record)
        );
      }
      return "";
    })
    .filter(Boolean)
    .slice(0, 3);

  if (evidence.length > 0) return evidence;
  return fallback ? [fallback] : [];
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const cleaned = cleanLabel(value);
    if (!cleaned) continue;
    if (cleaned.length < 2) continue;
    if (seen.has(cleaned)) continue;
    seen.add(cleaned);
    out.push(cleaned);
  }
  return out;
}

function dedupeEvidence(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const cleaned = value.trim();
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
  }
  return out;
}

function labelsFromUnknown(values: unknown[]): string[] {
  return dedupeStrings(
    values.flatMap((value) => {
      if (typeof value === "string") return [value];
      const record = asRecord(value);
      return [
        stringField(record, ["label", "name", "skill", "skill_label", "raw", "value", "title"]),
      ].filter(Boolean);
    }),
  );
}

function confidenceFromEvidence(explicitCount: number, inferred = false): number {
  if (explicitCount >= 2) return inferred ? 0.7 : 0.9;
  if (explicitCount === 1) return inferred ? 0.5 : 0.7;
  return 0;
}

function addSkill(
  skills: Map<string, SuggestedSkill>,
  label: string,
  source: SkillSource,
  evidence: string[],
  typeHint?: SuggestedSkill["type"],
) {
  const cleaned = cleanLabel(label);
  if (!cleaned) return;

  const type =
    typeHint ??
    (source === "experience_tool" || TOOL_HINTS.has(cleaned) ? "tool" : source === "structured" ? "domain" : "hard");
  const existing = skills.get(cleaned);
  const confidence = confidenceFromEvidence(evidence.length, source === "structured");

  if (!existing) {
    skills.set(cleaned, {
      label: cleaned,
      type,
      confidence,
      evidence,
    });
    return;
  }

  skills.set(cleaned, {
    label: cleaned,
    type: existing.type === "tool" ? existing.type : type,
    confidence: Math.max(existing.confidence, confidence),
    evidence: dedupeEvidence([...existing.evidence, ...evidence]).slice(0, 3),
  });
}

function buildSuggestedExperiences(input: ProfileReconstructionInput): SuggestedExperience[] {
  const careerProfile = asRecord(input.career_profile);
  const rawExperiences = [
    ...arrayField(careerProfile, ["experiences"]),
    ...(Array.isArray(input.experiences) ? input.experiences : []),
  ];
  const normalized = normalizeExperiences(rawExperiences);
  const seen = new Set<string>();

  return normalized
    .map((experience) => {
      const title = stringField(experience, ["title"]);
      const organization = stringField(experience, ["company", "organization", "employer"]);
      const startDate = stringField(experience, ["start_date"]);
      const endDate = stringField(experience, ["end_date"]);
      const missions = dedupeStrings([
        ...arrayField(experience, ["responsibilities"]).map(String),
        stringField(experience, ["description"]),
      ]);
      const tools = labelsFromUnknown(arrayField(experience, ["tools"]));
      const skills = dedupeStrings([
        ...labelsFromUnknown(arrayField(experience, ["canonical_skills_used"])),
        ...labelsFromUnknown(arrayField(experience, ["skills"])),
        ...arrayField(experience, ["skill_links"]).flatMap((link) => {
          const record = asRecord(link);
          return labelsFromUnknown([record.skill]);
        }),
      ]);
      const impact = dedupeStrings([
        ...arrayField(experience, ["achievements"]).map(String),
        ...arrayField(experience, ["impact_signals"]).map(String),
        ...arrayField(experience, ["quantified_signals"]).map(String),
      ]);
      const autonomy = stringField(experience, ["autonomy_level", "autonomy"]);
      const evidence = compactEvidence(
        [title, organization, ...missions, ...impact].filter(Boolean),
        "career_profile.experiences",
      );
      const key = [title, organization, startDate, endDate].join("::").toLowerCase();

      return {
        key,
        value: {
          title,
          organization,
          start_date: startDate,
          end_date: endDate,
          missions,
          tools,
          skills,
          signals: {
            autonomy,
            impact,
          },
          confidence: confidenceFromEvidence(evidence.length),
          evidence,
        },
      };
    })
    .filter(({ value }) => value.title || value.organization || value.missions.length > 0)
    .filter(({ key }) => {
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .map(({ value }) => value);
}

function buildSuggestedSkills(input: ProfileReconstructionInput, experiences: SuggestedExperience[]): SuggestedSkill[] {
  const skills = new Map<string, SuggestedSkill>();

  for (const item of normalizeSkills(input.selected_skills ?? [])) {
    addSkill(skills, item.label, "selected", compactEvidence([item.source || item.label]));
  }

  for (const item of normalizeSkills(input.canonical_skills ?? [])) {
    addSkill(skills, item.label, "canonical", compactEvidence([item.source || item.label]));
  }

  for (const item of input.validated_items ?? []) {
    const record = asRecord(item);
    const label = stringField(record, ["label", "name", "value", "raw"]);
    addSkill(skills, label, "validated", compactEvidence([record.evidence, record.raw, label]));
  }

  for (const unit of input.structured_signal_units ?? []) {
    const record = asRecord(unit);
    const label = stringField(record, ["label", "name", "skill", "skill_label", "value"]);
    const typeHint =
      stringField(record, ["type", "category"]).toLowerCase() === "tool"
        ? "tool"
        : stringField(record, ["type", "category"]).toLowerCase() === "domain"
          ? "domain"
          : undefined;
    addSkill(skills, label, "structured", compactEvidence([record.evidence, record.source_text, label]), typeHint);
  }

  for (const experience of experiences) {
    for (const tool of experience.tools) {
      addSkill(skills, tool, "experience_tool", compactEvidence([...experience.evidence, tool]), "tool");
    }
    for (const skill of experience.skills) {
      addSkill(skills, skill, "experience_skill", compactEvidence([...experience.evidence, skill]));
    }
  }

  return Array.from(skills.values()).filter((skill) => skill.evidence.length > 0);
}

function buildSuggestedSummary(input: ProfileReconstructionInput, experiences: SuggestedExperience[], skills: SuggestedSkill[]): SuggestedSummary {
  const careerProfile = asRecord(input.career_profile);
  const explicitSummary = stringField(careerProfile, ["summary_master", "summary", "profile_summary"]);

  if (explicitSummary) {
    return {
      text: normalizeText(explicitSummary),
      confidence: 0.9,
      evidence: [explicitSummary],
    };
  }

  const title = stringField(careerProfile, ["base_title", "target_title", "title"]);
  const topSkills = skills.slice(0, 3).map((skill) => skill.label);
  const firstExperience = experiences[0];
  const parts = [
    title,
    firstExperience?.organization ? `experience chez ${firstExperience.organization}` : "",
    topSkills.length > 0 ? `competences: ${topSkills.join(", ")}` : "",
  ].filter(Boolean);

  if (parts.length === 0) {
    return { text: "", confidence: 0, evidence: [] };
  }

  return {
    text: parts.join(" | "),
    confidence: 0.5,
    evidence: compactEvidence([title, firstExperience?.organization, ...topSkills].filter(Boolean)),
  };
}

function buildSuggestedProjects(careerProfile: Record<string, unknown>): SuggestedProject[] {
  return arrayField(careerProfile, ["projects"])
    .map((project) => {
      const record = asRecord(project);
      const name = stringField(record, ["name", "title"]);
      const description = normalizeText(stringField(record, ["description", "impact", "summary"]));
      const tools = labelsFromUnknown(arrayField(record, ["tools", "technologies"]));
      const evidence = compactEvidence([name, description, ...tools].filter(Boolean));
      return {
        name,
        description,
        tools,
        confidence: confidenceFromEvidence(evidence.length),
        evidence,
      };
    })
    .filter((project) => project.name || project.description || project.tools.length > 0);
}

function buildSuggestedCertifications(careerProfile: Record<string, unknown>): SuggestedCertification[] {
  return arrayField(careerProfile, ["certifications"])
    .map((certification) => {
      const record = asRecord(certification);
      const name = typeof certification === "string" ? certification.trim() : stringField(record, ["name", "title"]);
      const issuer = stringField(record, ["issuer", "organization"]);
      const evidence = compactEvidence([name, issuer].filter(Boolean));
      return {
        name,
        issuer,
        confidence: confidenceFromEvidence(evidence.length),
        evidence,
      };
    })
    .filter((certification) => certification.name);
}

function buildSuggestedLanguages(careerProfile: Record<string, unknown>): SuggestedLanguage[] {
  return arrayField(careerProfile, ["languages"])
    .map((language) => {
      const record = asRecord(language);
      const label = typeof language === "string" ? language.trim() : stringField(record, ["language", "name"]);
      const level = stringField(record, ["level", "proficiency"]);
      const evidence = compactEvidence([label, level].filter(Boolean));
      return {
        language: label,
        level,
        confidence: confidenceFromEvidence(evidence.length),
        evidence,
      };
    })
    .filter((language) => language.language);
}

export function buildProfileReconstruction(input: ProfileReconstructionInput): ProfileReconstructionOutput {
  const careerProfile = asRecord(input.career_profile);
  const suggestedExperiences = buildSuggestedExperiences(input);
  const suggestedSkills = buildSuggestedSkills(input, suggestedExperiences);

  return {
    suggested_summary: buildSuggestedSummary(input, suggestedExperiences, suggestedSkills),
    suggested_experiences: suggestedExperiences,
    suggested_skills: suggestedSkills,
    suggested_projects: buildSuggestedProjects(careerProfile),
    suggested_certifications: buildSuggestedCertifications(careerProfile),
    suggested_languages: buildSuggestedLanguages(careerProfile),
  };
}
