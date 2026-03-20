import { SEED_PROFILE } from "../fixtures/seedProfile";

export type SkillsSource = "user" | "seed" | "none" | "capabilities_only";

export type ProfileMatchingV1 = {
  id: string;
  matching_skills: string[];
  capabilities: string[];
  languages: string[] | Array<{ code?: string; level?: string }>;
  education?: string;
  education_summary?: { level?: string };
  preferred_countries?: string[];
  detected_capabilities?: unknown;
  skills_source: SkillsSource;
  profile_intelligence?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

type Capability = {
  name?: string;
  tools_detected?: string[];
};

type UnmappedSkill = { raw_skill?: string };

type ProfileInput = {
  id?: string;
  profile_id?: string;
  matching_skills?: string[];
  skills?: string[];
  languages?: Array<{ code?: string; level?: string }> | string[];
  education?: string;
  education_summary?: { level?: string };
  preferred_countries?: string[];
  detected_capabilities?: Capability[];
  unmapped_skills_high_confidence?: UnmappedSkill[];
  profile_intelligence?: Record<string, unknown>;
};

export type BuildMatchingProfileResult = {
  profile: ProfileMatchingV1;
  skillsSource: SkillsSource;
  needsSeedHydration: boolean;
};

function uniqueStrings(values: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((value) => {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) return;
    seen.add(trimmed);
    result.push(trimmed);
  });
  return result;
}

/**
 * Build matching profile with stable skills hydration rules:
 * 1. If userProfile.skills or userProfile.matching_skills exists → use (source: "user")
 * 2. If capabilities exist → extract names (source: "user")
 * 3. DEV only: fallback to SEED_PROFILE (source: "seed", needs hydration)
 * 4. PROD: no fallback (source: "none", profile incomplete)
 */
export function buildMatchingProfile(profile: ProfileInput, profileId: string): BuildMatchingProfileResult {
  let skillsSource: SkillsSource = "none";

  // Step 1: Try explicit skills from profile
  const explicitSkills = Array.isArray(profile.matching_skills)
    ? profile.matching_skills
    : Array.isArray(profile.skills)
      ? profile.skills
      : [];

  const unmapped = Array.isArray(profile.unmapped_skills_high_confidence)
    ? profile.unmapped_skills_high_confidence.map((skill) => skill?.raw_skill || "")
    : [];

  const detectedTools = Array.isArray(profile.detected_capabilities)
    ? profile.detected_capabilities.flatMap((cap) => cap?.tools_detected || [])
    : [];

  let matchingSkills = uniqueStrings([
    ...explicitSkills,
    ...unmapped,
    ...detectedTools,
  ])
    .map((skill) => skill.toLowerCase())
    .sort();

  // Step 2: If we have user skills, mark source as "user"
  if (matchingSkills.length > 0) {
    skillsSource = "user";
  }

  // Step 3: Try capabilities if no skills yet
  const capabilities = Array.isArray(profile.detected_capabilities)
    ? profile.detected_capabilities
        .map((cap) => cap?.name || "")
        .filter(Boolean) as string[]
    : [];

  if (matchingSkills.length === 0 && capabilities.length > 0) {
    matchingSkills = uniqueStrings(capabilities).map((skill) => skill.toLowerCase()).sort();
    skillsSource = "capabilities_only";
  }

  // Step 4: DEV fallback to SEED_PROFILE
  let needsSeedHydration = false;
  if ((matchingSkills.length === 0 || skillsSource === "capabilities_only") && import.meta.env.DEV) {
    matchingSkills = SEED_PROFILE.skills.map((s) => s.toLowerCase()).sort();
    skillsSource = "seed";
    needsSeedHydration = true;
  }

  const resultProfile: ProfileMatchingV1 = {
    id: profileId,
    matching_skills: matchingSkills,
    capabilities: uniqueStrings(capabilities).map((cap) => cap.toLowerCase()),
    languages: profile.languages || SEED_PROFILE.languages || [],
    education: profile.education || SEED_PROFILE.education,
    education_summary: profile.education_summary,
    preferred_countries: profile.preferred_countries || [],
    detected_capabilities: profile.detected_capabilities,
    skills_source: skillsSource,
    profile_intelligence: profile.profile_intelligence,
    metadata: {
      source: "profileMatchingV1",
      skills_source: skillsSource,
    },
  };

  return {
    profile: resultProfile,
    skillsSource,
    needsSeedHydration,
  };
}
