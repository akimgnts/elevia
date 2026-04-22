import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2, HelpCircle } from "lucide-react";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { startProfileUnderstandingSession } from "../lib/api";
import type {
  ProfileReconstructionOutput,
  SuggestedExperience,
} from "../lib/profile/reconstruction";
import { useProfileStore } from "../store/profileStore";

type WizardLocationState = {
  sourceContext?: Record<string, unknown>;
};

type CanonicalSkillRef = {
  label: string;
  uri?: string | null;
  confidence?: number;
  method?: string;
  source?: string;
};

type ToolRef = {
  label: string;
};

type CareerExperience = {
  title?: string;
  company?: string;
  organization?: string;
  start_date?: string;
  end_date?: string;
  dates?: string;
  description?: string;
  responsibilities?: unknown[];
  achievements?: unknown[];
  tools?: unknown[];
  canonical_skills_used?: unknown[];
  skills?: unknown[];
  autonomy_level?: string;
  autonomy?: string;
  skill_links?: Array<{
    skill?: CanonicalSkillRef;
    tools?: ToolRef[];
    context?: string;
    autonomy_level?: string;
  }>;
  [key: string]: unknown;
};

type CareerProfile = {
  base_title?: string;
  target_title?: string;
  summary_master?: string;
  selected_skills?: unknown[];
  experiences?: CareerExperience[];
  languages?: unknown[];
  certifications?: unknown[];
  projects?: unknown[];
  pending_skill_candidates?: string[];
  [key: string]: unknown;
};

type ProfileWithReconstruction = Record<string, unknown> & {
  career_profile?: CareerProfile;
  canonical_skills?: unknown[];
  profile_reconstruction?: ProfileReconstructionOutput;
};

type ConfirmationQuestion = {
  id: string;
  type: "autonomy" | "tools" | "language";
  label: string;
  helper: string;
  placeholder: string;
  experienceIndex?: number;
};

type DisplayExperience = {
  title: string;
  company: string;
  period: string;
  missions: string[];
  skillsAndTools: string[];
  source: "profile" | "suggestion";
};

const MAX_ITEMS = 5;

const SHORT_ALLOWLIST = new Set(["c", "r", "b2", "c1", "c2"]);

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function cleanDisplayValue(value: unknown): string {
  if (typeof value !== "string") return "";
  return value
    .split(/[|,]/)
    .map((part) => part.trim())
    .filter(Boolean)[0] ?? "";
}

function cleanDisplayList(values: unknown[], limit = MAX_ITEMS): string[] {
  const seen = new Set<string>();
  const out: string[] = [];

  for (const value of values) {
    const parts = typeof value === "string" ? value.split(/[|,]/) : [value];
    for (const part of parts) {
      const raw = cleanDisplayValue(part).replace(/\s+/g, " ").trim();
      if (!raw) continue;
      const normalized = raw.toLowerCase();
      if (normalized.length < 2 && !SHORT_ALLOWLIST.has(normalized)) continue;
      if (seen.has(normalized)) continue;
      seen.add(normalized);
      out.push(normalized);
      if (out.length >= limit) break;
    }
    if (out.length >= limit) break;
  }

  return out;
}

function labelsFromUnknown(values: unknown[], limit = MAX_ITEMS): string[] {
  return cleanDisplayList(
    values.flatMap((value) => {
      if (typeof value === "string") return [value];
      const record = asRecord(value);
      return [
        record.label,
        record.name,
        record.title,
        record.language,
        record.level,
      ].filter(Boolean);
    }),
    limit,
  );
}

function getCareerProfile(profile: unknown): CareerProfile {
  return asRecord(profile).career_profile && typeof asRecord(profile).career_profile === "object"
    ? (asRecord(profile).career_profile as CareerProfile)
    : {};
}

function getProfileReconstruction(profile: unknown): ProfileReconstructionOutput | null {
  const reconstruction = asRecord(profile).profile_reconstruction;
  if (!reconstruction || typeof reconstruction !== "object") return null;
  const record = reconstruction as Partial<ProfileReconstructionOutput>;
  if (!record.suggested_summary || !Array.isArray(record.suggested_skills)) return null;
  return reconstruction as ProfileReconstructionOutput;
}

function skillLabelsFromProfile(profile: ProfileWithReconstruction, careerProfile: CareerProfile): string[] {
  const selected = labelsFromUnknown(Array.isArray(careerProfile.selected_skills) ? careerProfile.selected_skills : []);
  if (selected.length > 0) return selected.slice(0, MAX_ITEMS);
  return labelsFromUnknown(Array.isArray(profile.canonical_skills) ? profile.canonical_skills : []).slice(0, MAX_ITEMS);
}

function toolsFromExperience(experience: CareerExperience): string[] {
  const directTools = labelsFromUnknown(Array.isArray(experience.tools) ? experience.tools : []);
  const linkTools = labelsFromUnknown(
    Array.isArray(experience.skill_links)
      ? experience.skill_links.flatMap((link) => (Array.isArray(link.tools) ? link.tools : []))
      : [],
  );
  return cleanDisplayList([...directTools, ...linkTools], 4);
}

function skillsFromExperience(experience: CareerExperience): string[] {
  const directSkills = labelsFromUnknown(Array.isArray(experience.canonical_skills_used) ? experience.canonical_skills_used : []);
  const legacySkills = labelsFromUnknown(Array.isArray(experience.skills) ? experience.skills : []);
  const linkSkills = labelsFromUnknown(
    Array.isArray(experience.skill_links)
      ? experience.skill_links.map((link) => link.skill).filter(Boolean)
      : [],
  );
  return cleanDisplayList([...directSkills, ...legacySkills, ...linkSkills], 3);
}

function missionsFromExperience(experience: CareerExperience): string[] {
  return cleanDisplayList(
    [
      ...(Array.isArray(experience.responsibilities) ? experience.responsibilities : []),
      experience.description,
      ...(Array.isArray(experience.achievements) ? experience.achievements : []),
    ],
    3,
  );
}

function displayExperienceFromProfile(experience: CareerExperience): DisplayExperience {
  const company = cleanDisplayValue(experience.company || experience.organization);
  const start = cleanDisplayValue(experience.start_date);
  const end = cleanDisplayValue(experience.end_date || experience.dates);
  const period = [start, end].filter(Boolean).join(" - ");
  const tools = toolsFromExperience(experience);
  const skills = skillsFromExperience(experience);
  return {
    title: cleanDisplayValue(experience.title) || "experience reconnue",
    company,
    period,
    missions: missionsFromExperience(experience),
    skillsAndTools: cleanDisplayList([...skills, ...tools], 3),
    source: "profile",
  };
}

function displayExperienceFromSuggestion(experience: SuggestedExperience): DisplayExperience {
  return {
    title: cleanDisplayValue(experience.title) || "experience suggeree",
    company: cleanDisplayValue(experience.organization),
    period: [cleanDisplayValue(experience.start_date), cleanDisplayValue(experience.end_date)].filter(Boolean).join(" - "),
    missions: cleanDisplayList(experience.missions, 3),
    skillsAndTools: cleanDisplayList([...experience.skills, ...experience.tools], 3),
    source: "suggestion",
  };
}

function buildDisplayExperiences(
  careerProfile: CareerProfile,
  reconstruction: ProfileReconstructionOutput | null,
): DisplayExperience[] {
  const profileExperiences = Array.isArray(careerProfile.experiences) ? careerProfile.experiences : [];
  if (profileExperiences.length > 0) {
    return profileExperiences.map(displayExperienceFromProfile).slice(0, MAX_ITEMS);
  }
  return (reconstruction?.suggested_experiences ?? []).map(displayExperienceFromSuggestion).slice(0, MAX_ITEMS);
}

function getSuggestedSummary(careerProfile: CareerProfile, reconstruction: ProfileReconstructionOutput | null): string {
  const profileSummary = cleanDisplayList([careerProfile.summary_master], 3).join(", ");
  if (profileSummary) return profileSummary;
  return cleanDisplayList([reconstruction?.suggested_summary.text], 3).join(", ");
}

function getSuggestedSkills(reconstruction: ProfileReconstructionOutput | null, existingSkills: string[]): string[] {
  const existing = new Set(existingSkills.map((skill) => skill.toLowerCase()));
  return cleanDisplayList(
    (reconstruction?.suggested_skills ?? [])
      .map((skill) => skill.label)
      .filter((label) => !existing.has(label.toLowerCase())),
  );
}

function hasArrayItems(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0;
}

function buildConfirmationQuestions(careerProfile: CareerProfile, experiences: DisplayExperience[]): ConfirmationQuestion[] {
  const rawExperiences = Array.isArray(careerProfile.experiences) ? careerProfile.experiences : [];
  const questions: ConfirmationQuestion[] = [];

  const autonomyIndex = rawExperiences.findIndex((experience) => {
    const autonomy = cleanDisplayValue(experience.autonomy_level || experience.autonomy);
    return !autonomy;
  });
  if (autonomyIndex >= 0) {
    const experience = experiences[autonomyIndex];
    questions.push({
      id: "autonomy",
      type: "autonomy",
      label: `Quel niveau d'autonomie pour ${experience?.title || "cette experience"} ?`,
      helper: "Exemples: execution, autonome, pilotage.",
      placeholder: "Autonomie sur cette experience",
      experienceIndex: autonomyIndex,
    });
  }

  const toolsIndex = rawExperiences.findIndex((experience) => toolsFromExperience(experience).length === 0);
  if (toolsIndex >= 0 && questions.length < MAX_ITEMS) {
    const experience = experiences[toolsIndex];
    questions.push({
      id: "tools",
      type: "tools",
      label: `Quels outils associer a ${experience?.title || "cette experience"} ?`,
      helper: "Ajoutez seulement les outils importants pour votre profil.",
      placeholder: "Ex: power bi, excel, salesforce",
      experienceIndex: toolsIndex,
    });
  }

  if (!hasArrayItems(careerProfile.languages) && questions.length < MAX_ITEMS) {
    questions.push({
      id: "language",
      type: "language",
      label: "Quel niveau de langue voulez-vous afficher ?",
      helper: "Utile pour les offres internationales. Exemple: anglais c1.",
      placeholder: "Ex: anglais c1",
    });
  }

  return questions.slice(0, MAX_ITEMS);
}

function mergeStringValues(existing: unknown, incoming: string[]): string[] {
  const values = Array.isArray(existing) ? existing.map(String) : [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of [...values, ...incoming]) {
    const cleaned = cleanDisplayValue(value);
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
  }
  return out;
}

function projectReconstructionIntoCareerProfile(
  careerProfile: Record<string, unknown>,
  reconstruction: ProfileReconstructionOutput | null,
): Record<string, unknown> {
  if (!reconstruction) return careerProfile;
  const next = structuredClone(careerProfile);

  if (typeof next.summary_master !== "string" || !next.summary_master.trim()) {
    const summary = reconstruction.suggested_summary.text.trim();
    if (summary) next.summary_master = summary;
  }

  next.pending_skill_candidates = mergeStringValues(
    next.pending_skill_candidates,
    reconstruction.suggested_skills.map((skill) => skill.label),
  );

  if (!hasArrayItems(next.languages)) {
    const languages = reconstruction.suggested_languages
      .filter((language) => language.language.trim())
      .map((language) => ({
        language: language.language,
        level: language.level,
      }));
    if (languages.length > 0) next.languages = languages;
  }

  if (!hasArrayItems(next.certifications)) {
    const certifications = reconstruction.suggested_certifications
      .map((certification) => [certification.name, certification.issuer].filter(Boolean).join(" - "))
      .filter(Boolean);
    if (certifications.length > 0) next.certifications = certifications;
  }

  if (!hasArrayItems(next.projects)) {
    const projects = reconstruction.suggested_projects
      .filter((project) => project.name.trim() || project.description.trim())
      .map((project) => ({
        title: project.name,
        impact: project.description,
        technologies: project.tools,
      }));
    if (projects.length > 0) next.projects = projects;
  }

  return next;
}

function applyAnswersToCareerProfile(
  careerProfile: Record<string, unknown>,
  questions: ConfirmationQuestion[],
  answers: Record<string, string>,
): Record<string, unknown> {
  const next = structuredClone(careerProfile);
  const experiences = Array.isArray(next.experiences) ? [...(next.experiences as unknown[])] : [];

  for (const question of questions) {
    const answer = answers[question.id]?.trim();
    if (!answer) continue;

    if ((question.type === "autonomy" || question.type === "tools") && typeof question.experienceIndex === "number") {
      const current = asRecord(experiences[question.experienceIndex]);
      if (question.type === "autonomy") current.autonomy_level = answer;
      if (question.type === "tools") current.tools = cleanDisplayList([answer]).map((label) => ({ label }));
      experiences[question.experienceIndex] = current;
    }

    if (question.type === "language" && !hasArrayItems(next.languages)) {
      const [language, ...levelParts] = cleanDisplayList([answer], 2);
      if (language) {
        next.languages = [{ language, level: levelParts.join(" ") }];
      }
    }
  }

  if (experiences.length > 0) next.experiences = experiences;
  return next;
}

function SuggestionChips({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export default function ProfileUnderstandingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { userProfile, setIngestResult } = useProfileStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const sourceContext = useMemo(
    () => ((location.state as WizardLocationState | null)?.sourceContext ?? {}),
    [location.state],
  );
  const profile = (userProfile ?? {}) as ProfileWithReconstruction;
  const careerProfile = useMemo(() => getCareerProfile(userProfile), [userProfile]);
  const profileReconstruction = useMemo(() => getProfileReconstruction(userProfile), [userProfile]);
  const profileSkills = useMemo(() => skillLabelsFromProfile(profile, careerProfile), [careerProfile, profile]);
  const profileExperiences = useMemo(
    () => buildDisplayExperiences(careerProfile, profileReconstruction),
    [careerProfile, profileReconstruction],
  );
  const profileTools = useMemo(
    () => cleanDisplayList(profileExperiences.flatMap((experience) => experience.skillsAndTools), 4),
    [profileExperiences],
  );
  const suggestedSkills = useMemo(
    () => getSuggestedSkills(profileReconstruction, profileSkills),
    [profileReconstruction, profileSkills],
  );
  const questions = useMemo(
    () => buildConfirmationQuestions(careerProfile, profileExperiences),
    [careerProfile, profileExperiences],
  );
  const summary = getSuggestedSummary(careerProfile, profileReconstruction);
  const title = cleanDisplayValue(careerProfile.base_title || careerProfile.target_title) || "profil reconstruit";
  const missingLanguages = !hasArrayItems(careerProfile.languages)
    ? cleanDisplayList((profileReconstruction?.suggested_languages ?? []).map((language) => [language.language, language.level].filter(Boolean).join(" ")))
    : [];
  const missingCertifications = !hasArrayItems(careerProfile.certifications)
    ? cleanDisplayList((profileReconstruction?.suggested_certifications ?? []).map((certification) => certification.name))
    : [];
  const missingProjects = !hasArrayItems(careerProfile.projects)
    ? cleanDisplayList((profileReconstruction?.suggested_projects ?? []).map((project) => project.name || project.description))
    : [];

  useEffect(() => {
    if (!userProfile) return;

    let cancelled = false;

    async function loadSession() {
      setLoading(true);
      setError(null);

      try {
        await startProfileUnderstandingSession({
          profile: userProfile as Record<string, unknown>,
          source_context: sourceContext,
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Erreur lors du chargement du profil.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [sourceContext, userProfile]);

  if (!userProfile) {
    return <Navigate to="/analyze" replace />;
  }

  async function handleContinue() {
    const baseProfile = structuredClone(userProfile as ProfileWithReconstruction);
    const currentCareer = structuredClone(getCareerProfile(baseProfile));
    const answeredCareer = applyAnswersToCareerProfile(currentCareer, questions, answers);
    baseProfile.career_profile = projectReconstructionIntoCareerProfile(answeredCareer, profileReconstruction) as CareerProfile;
    await setIngestResult(baseProfile);
    navigate("/profile");
  }

  return (
    <PremiumAppShell
      eyebrow="Profil"
      title="Valider le profil reconstruit"
      description="Elevia a prepare un brouillon de profil. Verifiez les points essentiels, puis genere le profil editable."
      actions={
        <Link
          to="/analyze"
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Revenir a l'analyse
        </Link>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.8fr)]">
        <section className="space-y-5">
          {loading && (
            <div className="rounded-[1.5rem] border border-white/80 bg-white/80 px-5 py-4 text-sm text-slate-600 shadow-sm">
              Preparation du brouillon de profil...
            </div>
          )}

          {error && (
            <div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 shadow-sm">
              {error}
            </div>
          )}

          <article className="rounded-[1.75rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Résumé du profil
                </div>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">
                  {title}
                </h2>
                {summary && <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{summary}</p>}
              </div>
              <div className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                Brouillon prêt
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Compétences principales
                </div>
                <div className="mt-3">
                  <SuggestionChips items={profileSkills} />
                </div>
              </div>
              <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  Outils détectés
                </div>
                <div className="mt-3">
                  <SuggestionChips items={profileTools} />
                  {profileTools.length === 0 && (
                    <p className="text-sm text-slate-500">Aucun outil principal détecté avec assez de clarté.</p>
                  )}
                </div>
              </div>
            </div>
          </article>

          <article className="rounded-[1.75rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
              Expériences
            </div>
            <h2 className="mt-3 text-lg font-semibold text-slate-950">
              Parcours reconnu
            </h2>
            <div className="mt-5 grid gap-3">
              {profileExperiences.length > 0 ? (
                profileExperiences.map((experience, index) => (
                  <div key={`${experience.title}-${experience.company}-${index}`} className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-slate-950">{experience.title}</div>
                        {(experience.company || experience.period) && (
                          <div className="mt-1 text-sm text-slate-500">
                            {[experience.company, experience.period].filter(Boolean).join(" · ")}
                          </div>
                        )}
                      </div>
                      {experience.source === "suggestion" && (
                        <span className="rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700">
                          suggestion
                        </span>
                      )}
                    </div>
                    {experience.missions.length > 0 && (
                      <ul className="mt-3 space-y-1.5 text-sm leading-6 text-slate-600">
                        {experience.missions.map((mission) => (
                          <li key={mission}>• {mission}</li>
                        ))}
                      </ul>
                    )}
                    {experience.skillsAndTools.length > 0 && (
                      <div className="mt-3">
                        <SuggestionChips items={experience.skillsAndTools} />
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                  Aucune expérience suffisamment structurée n'a été reconnue.
                </p>
              )}
            </div>
          </article>

          <article className="rounded-[1.75rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
              Suggestions
            </div>
            <h2 className="mt-3 text-lg font-semibold text-slate-950">
              Éléments proposés, non imposés
            </h2>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-semibold text-slate-900">Compétences suggérées</div>
                <div className="mt-3">
                  <SuggestionChips items={suggestedSkills} />
                  {suggestedSkills.length === 0 && <p className="text-sm text-slate-500">Aucune compétence candidate claire.</p>}
                </div>
              </div>
              <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                <div className="text-sm font-semibold text-slate-900">Compléments possibles</div>
                <div className="mt-3 space-y-3">
                  <SuggestionChips items={missingLanguages} />
                  <SuggestionChips items={missingCertifications} />
                  <SuggestionChips items={missingProjects} />
                  {missingLanguages.length === 0 && missingCertifications.length === 0 && missingProjects.length === 0 && (
                    <p className="text-sm text-slate-500">Aucun complément prioritaire à proposer.</p>
                  )}
                </div>
              </div>
            </div>
          </article>

          <article className="rounded-[1.75rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
              <HelpCircle className="h-4 w-4" />
              Points à confirmer
            </div>
            <h2 className="mt-3 text-lg font-semibold text-slate-950">
              {questions.length > 0 ? "Quelques précisions utiles" : "Aucune précision critique"}
            </h2>
            <div className="mt-5 grid gap-3">
              {questions.length > 0 ? (
                questions.map((question) => (
                  <div key={question.id} className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                    <label className="text-sm font-semibold text-slate-900" htmlFor={`question-${question.id}`}>
                      {question.label}
                    </label>
                    <p className="mt-1 text-sm text-slate-500">{question.helper}</p>
                    <input
                      id={`question-${question.id}`}
                      value={answers[question.id] ?? ""}
                      onChange={(event) => setAnswers((current) => ({ ...current, [question.id]: event.target.value }))}
                      placeholder={question.placeholder}
                      className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
                    />
                  </div>
                ))
              ) : (
                <div className="rounded-[1.25rem] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                  Le brouillon est suffisamment clair pour générer le profil.
                </div>
              )}
            </div>
          </article>
        </section>

        <aside className="space-y-4">
          <div className="rounded-[1.75rem] border border-white/80 bg-white/90 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              Action principale
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              La validation crée votre profil éditable à partir des éléments déjà compris. Les suggestions restent
              traçables et seules les zones vides sont complétées.
            </p>
            <button
              type="button"
              onClick={() => void handleContinue()}
              disabled={loading || Boolean(error)}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              Valider et générer mon profil
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>

          <div className="rounded-[1.75rem] border border-white/80 bg-white/90 p-5 text-sm leading-6 text-slate-600 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="font-semibold text-slate-900">Ce qui ne change pas</div>
            <ul className="mt-3 space-y-2">
              <li>• aucune modification du scoring</li>
              <li>• aucun changement du signal de matching</li>
              <li>• aucune donnée remplacée silencieusement</li>
            </ul>
          </div>
        </aside>
      </div>
    </PremiumAppShell>
  );
}
