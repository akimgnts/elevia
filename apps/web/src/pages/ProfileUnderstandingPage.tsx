import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  HelpCircle,
  Link2,
  Layers3,
  ScanSearch,
  SearchCheck,
} from "lucide-react";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import {
  type ProfileUnderstandingDocumentBlock,
  startProfileUnderstandingSession,
  type ProfileUnderstandingEvidence,
  type ProfileUnderstandingMissionUnit,
  type ProfileUnderstandingQuestion,
  type ProfileUnderstandingSessionResponse,
  type ProfileUnderstandingSkillLink,
} from "../lib/api";
import { useProfileStore } from "../store/profileStore";

type WizardLocationState = {
  sourceContext?: Record<string, unknown>;
};

type AutonomyLevel = "execution" | "partial" | "autonomous" | "ownership";

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

type SkillLinkItem = {
  skill: CanonicalSkillRef;
  tools: ToolRef[];
  context?: string;
  autonomy_level?: AutonomyLevel;
};

type CareerExperience = {
  title?: string;
  company?: string;
  autonomy_level?: string;
  canonical_skills_used?: CanonicalSkillRef[];
  tools?: Array<CanonicalSkillRef | ToolRef | string>;
  skill_links?: SkillLinkItem[];
  [key: string]: unknown;
};

type CareerProfile = {
  experiences?: CareerExperience[];
  education?: unknown[];
  certifications?: unknown[];
  [key: string]: unknown;
};

const AUTONOMY_LABELS: Record<AutonomyLevel, string> = {
  execution: "Execution",
  partial: "Partiel",
  autonomous: "Autonome",
  ownership: "Ownership",
};

const AUTONOMY_BADGES: Record<AutonomyLevel, string> = {
  execution: "border-slate-200 bg-slate-100 text-slate-700",
  partial: "border-amber-200 bg-amber-50 text-amber-700",
  autonomous: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ownership: "border-indigo-200 bg-indigo-50 text-indigo-700",
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function splitCommaValues(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function dedupeByLabel<T extends { label: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = item.label.trim().toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizeAutonomy(value: unknown): AutonomyLevel | undefined {
  return value === "execution" || value === "partial" || value === "autonomous" || value === "ownership"
    ? value
    : undefined;
}

function normalizeSkillLink(link: ProfileUnderstandingSkillLink): SkillLinkItem | null {
  const skillLabel = link.skill?.label?.trim();
  if (!skillLabel) return null;

  return {
    skill: {
      label: skillLabel,
      uri: link.skill.uri ?? undefined,
      confidence: typeof link.skill.confidence === "number" ? link.skill.confidence : undefined,
      method: link.skill.method ?? undefined,
      source: link.skill.source ?? undefined,
    },
    tools: dedupeByLabel(
      (Array.isArray(link.tools) ? link.tools : [])
        .map((tool) => {
          const label = typeof tool?.label === "string" ? tool.label.trim() : "";
          return label ? { label } : null;
        })
        .filter((tool): tool is ToolRef => tool !== null),
    ),
    context: typeof link.context === "string" && link.context.trim() ? link.context.trim() : undefined,
    autonomy_level: normalizeAutonomy(link.autonomy_level),
  };
}

function mergeSkillLinks(existing: SkillLinkItem[], incoming: SkillLinkItem[]): SkillLinkItem[] {
  const merged = new Map<string, SkillLinkItem>();

  for (const link of [...existing, ...incoming]) {
    const key = [
      link.skill.label.trim().toLowerCase(),
      link.tools.map((tool) => tool.label.trim().toLowerCase()).sort().join("|"),
      link.context?.trim().toLowerCase() ?? "",
      link.autonomy_level ?? "",
    ].join("::");

    if (!merged.has(key)) {
      merged.set(key, {
        skill: { ...link.skill },
        tools: [...link.tools],
        context: link.context,
        autonomy_level: link.autonomy_level,
      });
    }
  }

  return Array.from(merged.values());
}

function getExperienceIndex(reference: string | null | undefined): number | null {
  if (!reference) return null;
  const match = reference.match(/exp-(\d+)/i);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isInteger(value) ? value : null;
}

function groupSkillLinksByExperience(skillLinks: ProfileUnderstandingSkillLink[]): Map<number, SkillLinkItem[]> {
  const grouped = new Map<number, SkillLinkItem[]>();

  for (const rawLink of skillLinks) {
    const experienceIndex = getExperienceIndex(rawLink.experience_ref);
    if (experienceIndex === null) continue;
    const normalized = normalizeSkillLink(rawLink);
    if (!normalized) continue;
    grouped.set(experienceIndex, [...(grouped.get(experienceIndex) ?? []), normalized]);
  }

  return grouped;
}

function applyAnswerToCareerProfile(
  careerProfile: Record<string, unknown>,
  question: ProfileUnderstandingQuestion,
  answer: string,
): Record<string, unknown> {
  const fieldPath = question.field_path ?? "";
  if (!fieldPath) return careerProfile;

  const next = structuredClone(careerProfile);
  const experienceMatch = fieldPath.match(/^career_profile\.experiences\[(\d+)\]\.(.+)$/);

  if (experienceMatch) {
    const index = Number(experienceMatch[1]);
    const field = experienceMatch[2];
    const experiences = Array.isArray(next.experiences) ? [...(next.experiences as unknown[])] : [];
    const current = experiences[index];
    const experience =
      current && typeof current === "object"
        ? { ...(current as Record<string, unknown>) }
        : {};

    if (field === "autonomy_level") {
      experience.autonomy_level = answer.trim();
    } else if (field === "tools") {
      experience.tools = splitCommaValues(answer).map((label) => ({ label }));
    }

    experiences[index] = experience;
    next.experiences = experiences;
    return next;
  }

  if (fieldPath === "career_profile.education") {
    const current = Array.isArray(next.education) ? [...(next.education as unknown[])] : [];
    const entry = { degree: answer.trim() };
    next.education = answer.trim() ? [entry, ...current.filter(Boolean)] : current;
    return next;
  }

  if (fieldPath === "career_profile.certifications") {
    next.certifications = splitCommaValues(answer);
    return next;
  }

  if (fieldPath === "career_profile.experiences") {
    next.experiences = answer.trim()
      ? [{ title: answer.trim(), company: "", responsibilities: [], tools: [], skill_links: [] }]
      : next.experiences;
    return next;
  }

  return next;
}

function mergeSessionSkillLinksIntoCareerProfile(
  baseCareerProfile: CareerProfile,
  session: ProfileUnderstandingSessionResponse | null,
): CareerProfile {
  const nextCareer = structuredClone(baseCareerProfile);
  const experiences = Array.isArray(nextCareer.experiences) ? [...nextCareer.experiences] : [];
  const groupedLinks = groupSkillLinksByExperience(session?.skill_links ?? []);

  groupedLinks.forEach((incomingLinks, experienceIndex) => {
    const currentExperience = asRecord(experiences[experienceIndex]) as CareerExperience;
    const currentSkillLinks = Array.isArray(currentExperience.skill_links) ? currentExperience.skill_links : [];
    const mergedLinks = mergeSkillLinks(currentSkillLinks, incomingLinks);
    const mergedSkills = dedupeByLabel(
      [
        ...(Array.isArray(currentExperience.canonical_skills_used) ? currentExperience.canonical_skills_used : []),
        ...mergedLinks.map((link) => link.skill),
      ].map((skill) => ({
        label: skill.label,
        uri: skill.uri ?? undefined,
        confidence: skill.confidence,
        method: skill.method,
        source: skill.source,
      })),
    );
    const mergedTools = dedupeByLabel(
      [
        ...(Array.isArray(currentExperience.tools) ? currentExperience.tools : []).map((tool) => {
          if (typeof tool === "string") return { label: tool };
          const record = asRecord(tool);
          return { label: typeof record.label === "string" ? record.label : "" };
        }),
        ...mergedLinks.flatMap((link) => link.tools),
      ].filter((tool) => tool.label.trim()),
    );
    const autonomyFromLinks = mergedLinks.find((link) => link.autonomy_level)?.autonomy_level;

    experiences[experienceIndex] = {
      ...currentExperience,
      skill_links: mergedLinks,
      canonical_skills_used: mergedSkills,
      tools: mergedTools,
      autonomy_level: currentExperience.autonomy_level ?? autonomyFromLinks,
    };
  });

  nextCareer.experiences = experiences;
  return nextCareer;
}

function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function confidenceTone(value: number | undefined): string {
  if (typeof value !== "number") return "border-slate-200 bg-slate-50 text-slate-500";
  if (value >= 0.75) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (value >= 0.5) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-rose-200 bg-rose-50 text-rose-700";
}

function summarizeEvidence(evidence: ProfileUnderstandingEvidence[]): string[] {
  return evidence
    .map((item) => item.source_value || item.source_type)
    .filter((value): value is string => Boolean(value))
    .slice(0, 3);
}

function extractSignalEntries(signal: Record<string, unknown> | null | undefined): Array<[string, string[]]> {
  if (!signal) return [];
  return Object.entries(signal)
    .map(([key, value]) => {
      if (!Array.isArray(value)) return [key, []] as [string, string[]];
      const entries = value
        .map((item) => {
          if (typeof item === "string") return item.trim();
          if (item && typeof item === "object") {
            const record = item as Record<string, unknown>;
            const label = typeof record.label === "string" ? record.label.trim() : "";
            const raw = typeof record.raw_value === "string" ? record.raw_value.trim() : "";
            return label || raw;
          }
          return "";
        })
        .filter(Boolean);
      return [key, entries] as [string, string[]];
    })
    .filter(([, entries]) => entries.length > 0);
}

function groupMissionUnits(
  missionUnits: ProfileUnderstandingMissionUnit[],
): Array<{ key: string; label: string; units: ProfileUnderstandingMissionUnit[] }> {
  const groups = new Map<string, ProfileUnderstandingMissionUnit[]>();

  for (const unit of missionUnits) {
    const key = unit.experience_ref || unit.block_ref || "general";
    groups.set(key, [...(groups.get(key) ?? []), unit]);
  }

  return Array.from(groups.entries()).map(([key, units]) => ({
    key,
    label: key.replace(/^exp-/i, "Experience ").replace(/^block-/i, "").replace(/-/g, " "),
    units,
  }));
}

function getBlockBadgeTone(blockType: string): string {
  switch (blockType) {
    case "experience":
      return "border-blue-200 bg-blue-50 text-blue-700";
    case "project":
      return "border-violet-200 bg-violet-50 text-violet-700";
    case "education":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "certification":
      return "border-emerald-200 bg-emerald-50 text-emerald-700";
    default:
      return "border-slate-200 bg-slate-50 text-slate-700";
  }
}

export default function ProfileUnderstandingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { userProfile, setIngestResult } = useProfileStore();
  const [session, setSession] = useState<ProfileUnderstandingSessionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const sourceContext = useMemo(
    () => ((location.state as WizardLocationState | null)?.sourceContext ?? {}),
    [location.state],
  );

  useEffect(() => {
    if (!userProfile) return;

    let cancelled = false;

    async function loadSession() {
      setLoading(true);
      setError(null);

      try {
        const response = await startProfileUnderstandingSession({
          profile: userProfile as Record<string, unknown>,
          source_context: sourceContext,
        });

        if (cancelled) return;

        setSession(response);
        setAnswers(
          Object.fromEntries(
            response.questions.map((question) => [question.id, question.suggested_answer ?? ""]),
          ),
        );
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Erreur lors du chargement du wizard.");
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [sourceContext, userProfile]);

  const relationSummary = useMemo(() => {
    const skillLinks = session?.skill_links ?? [];
    const entityClassification = session?.entity_classification ?? {};
    const evidenceMap = session?.evidence_map ?? {};
    const documentBlocks = session?.document_blocks ?? [];
    const missionUnits = session?.mission_units ?? [];
    const openSignalEntries = extractSignalEntries(session?.open_signal);
    const canonicalSignalEntries = extractSignalEntries(session?.canonical_signal);
    const understoodCount =
      typeof session?.understanding_status?.understood_count === "number"
        ? session.understanding_status.understood_count
        : documentBlocks.length + skillLinks.length;
    const pendingCount =
      typeof session?.understanding_status?.needs_confirmation_count === "number"
        ? session.understanding_status.needs_confirmation_count
        : (session?.questions ?? []).length;

    return {
      documentBlocks,
      missionUnits,
      skillLinks,
      openSignalEntries,
      canonicalSignalEntries,
      understoodCount,
      pendingCount,
      entityEntries: Object.entries(entityClassification).filter(([, values]) => Array.isArray(values) && values.length > 0),
      evidenceEntries: Object.entries(evidenceMap).filter(([, values]) => Array.isArray(values) && values.length > 0),
    };
  }, [session]);

  if (!userProfile) {
    return <Navigate to="/analyze" replace />;
  }

  async function handleContinue() {
    const baseProfile = structuredClone(userProfile as Record<string, unknown>);
    const currentCareer =
      session?.proposed_profile_patch?.career_profile && typeof session.proposed_profile_patch.career_profile === "object"
        ? structuredClone(session.proposed_profile_patch.career_profile as Record<string, unknown>)
        : structuredClone(asRecord(baseProfile.career_profile));

    const answeredCareer = (session?.questions ?? []).reduce((careerProfile, question) => {
      const answer = answers[question.id]?.trim();
      if (!answer) return careerProfile;
      return applyAnswerToCareerProfile(careerProfile, question, answer);
    }, currentCareer);

    baseProfile.career_profile = mergeSessionSkillLinksIntoCareerProfile(answeredCareer as CareerProfile, session);
    await setIngestResult(baseProfile);
    navigate("/profile");
  }

  return (
    <PremiumAppShell
      eyebrow="Profil"
      title="Verifier les elements cles avant edition finale"
      description="Nous avons deja structure votre parcours. Verifiez les points compris, corrigez uniquement les zones utiles, puis poursuivez vers le profil complet."
      actions={
        <>
          <Link
            to="/analyze"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Revenir a l'analyse
          </Link>
          <button
            type="button"
            onClick={() => void handleContinue()}
            disabled={loading || Boolean(error)}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            Injecter dans le profil
            <ArrowRight className="h-4 w-4" />
          </button>
        </>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.9fr)]">
        <section className="space-y-4">
          {loading && (
            <div className="rounded-[1.5rem] border border-white/80 bg-white/80 px-5 py-4 text-sm text-slate-600 shadow-sm">
              Preparation de la structure du profil...
            </div>
          )}

          {error && (
            <div className="rounded-[1.5rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 shadow-sm">
              {error}
            </div>
          )}

          {!loading && !error && session && (
            <article className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                    Parcours structure
                  </div>
                  <h2 className="mt-3 text-lg font-semibold text-slate-950">
                    Ce que nous avons deja compris de votre CV
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    Les blocs detectes, les missions comprises et les liens competence {"->"} outils sont precharges. Les
                    questions servent seulement a confirmer les zones encore ambiguës.
                  </p>
                </div>
                <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-400">
                  {session.provider}
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Elements compris
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-slate-950">{relationSummary.understoodCount}</div>
                </div>
                <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Missions extraites
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-slate-950">{relationSummary.missionUnits.length}</div>
                </div>
                <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Confirmations utiles
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-slate-950">{relationSummary.pendingCount}</div>
                </div>
              </div>

              {relationSummary.documentBlocks.length > 0 && (
                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {relationSummary.documentBlocks.map((block: ProfileUnderstandingDocumentBlock) => (
                    <div key={block.id} className="rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-slate-900">
                          {block.label}
                        </div>
                        <span
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${getBlockBadgeTone(
                            block.block_type,
                          )}`}
                        >
                          {block.block_type}
                        </span>
                      </div>
                      {block.source_text && <p className="mt-3 text-sm leading-6 text-slate-600">{block.source_text}</p>}
                      <div className="mt-3 flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-500">
                          {typeof block.metadata?.organization === "string"
                            ? block.metadata.organization
                            : typeof block.metadata?.company === "string"
                              ? block.metadata.company
                              : "Bloc structure"}
                        </span>
                        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${confidenceTone(block.confidence ?? undefined)}`}>
                          {formatPercent(block.confidence)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          )}

          {!loading &&
            !error &&
            relationSummary.missionUnits.length > 0 && (
              <article className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Layers3 className="h-4 w-4 text-slate-700" />
                  Missions deja interpretees
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Chaque mission est lue comme une unite distincte pour rattacher des competences, des outils, du
                  contexte et des signaux chiffres.
                </p>
                <div className="mt-4 space-y-4">
                  {groupMissionUnits(relationSummary.missionUnits).map((group) => (
                    <div key={group.key} className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                      <div className="text-sm font-semibold text-slate-900">{group.label}</div>
                      <div className="mt-3 space-y-3">
                        {group.units.map((unit) => (
                          <div key={unit.id} className="rounded-[1rem] border border-slate-200 bg-white p-3">
                            <p className="text-sm leading-6 text-slate-700">{unit.mission_text}</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {unit.skill_candidates_open.map((item) => (
                                <span key={`${unit.id}-skill-${item}`} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700">
                                  {item}
                                </span>
                              ))}
                              {unit.tool_candidates_open.map((item) => (
                                <span key={`${unit.id}-tool-${item}`} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                                  {item}
                                </span>
                              ))}
                              {unit.quantified_signals.map((item) => (
                                <span key={`${unit.id}-signal-${item}`} className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                                  {item}
                                </span>
                              ))}
                            </div>
                            {(unit.context || unit.autonomy_hypothesis) && (
                              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                                {unit.context && <span>Contexte: {unit.context}</span>}
                                {unit.autonomy_hypothesis && <span>Autonomie: {unit.autonomy_hypothesis}</span>}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            )}

          {!loading &&
            !error &&
            (session?.skill_links ?? []).map((link, index) => {
              const autonomy = normalizeAutonomy(link.autonomy_level);
              const evidencePreview = summarizeEvidence(link.evidence);
              return (
                <article
                  key={`${link.experience_ref ?? "exp"}-${link.skill.label}-${index}`}
                  className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-blue-700">
                        <Link2 className="h-3.5 w-3.5" />
                        {link.experience_ref ?? "experience"}
                      </div>
                      <h2 className="mt-3 text-lg font-semibold text-slate-950">{link.skill.label}</h2>
                      {link.context && (
                        <p className="mt-2 text-sm leading-6 text-slate-600">{link.context}</p>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {autonomy && (
                        <span
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${AUTONOMY_BADGES[autonomy]}`}
                        >
                          {AUTONOMY_LABELS[autonomy]}
                        </span>
                      )}
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${confidenceTone(
                          session?.confidence_map?.[`${link.experience_ref ?? "career_profile"}.skill_links`],
                        )}`}
                      >
                        {formatPercent(session?.confidence_map?.[`${link.experience_ref ?? "career_profile"}.skill_links`])}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)]">
                    <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                        Outils relies a cette competence
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {link.tools.length > 0 ? (
                          link.tools.map((tool) => (
                            <span
                              key={tool.label}
                              className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700"
                            >
                              {tool.label}
                            </span>
                          ))
                        ) : (
                          <span className="text-sm text-slate-500">Aucun outil confirme pour l&apos;instant.</span>
                        )}
                      </div>
                    </div>

                    <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                        Preuves disponibles
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {evidencePreview.length > 0 ? (
                          evidencePreview.map((evidence) => (
                            <span
                              key={evidence}
                              className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
                            >
                              {evidence}
                            </span>
                          ))
                        ) : (
                          <span className="text-sm text-slate-500">Pas encore de preuve exposee.</span>
                        )}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}

          {!loading &&
            !error &&
            (relationSummary.canonicalSignalEntries.length > 0 || relationSummary.openSignalEntries.length > 0) && (
              <article className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <ScanSearch className="h-4 w-4 text-slate-700" />
                  Signaux recuperes
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Signal canonique
                    </div>
                    <div className="mt-3 space-y-3">
                      {relationSummary.canonicalSignalEntries.length > 0 ? (
                        relationSummary.canonicalSignalEntries.map(([key, values]) => (
                          <div key={key}>
                            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                              {key.replace(/_/g, " ")}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {values.slice(0, 8).map((value) => (
                                <span key={`${key}-${value}`} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700">
                                  {value}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-slate-500">Aucun signal canonique expose.</div>
                      )}
                    </div>
                  </div>
                  <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Signal ouvert
                    </div>
                    <div className="mt-3 space-y-3">
                      {relationSummary.openSignalEntries.length > 0 ? (
                        relationSummary.openSignalEntries.map(([key, values]) => (
                          <div key={key}>
                            <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                              {key.replace(/_/g, " ")}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {values.slice(0, 8).map((value) => (
                                <span key={`${key}-${value}`} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700">
                                  {value}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-slate-500">Aucun signal libre expose.</div>
                      )}
                    </div>
                  </div>
                </div>
              </article>
            )}

          {!loading &&
            !error &&
            (session?.questions ?? []).map((question, index) => (
              <article
                key={question.id}
                className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
                      <HelpCircle className="h-3.5 w-3.5" />
                      Question {index + 1}
                    </div>
                    <h2 className="mt-3 text-lg font-semibold text-slate-950">{question.prompt}</h2>
                    {question.rationale && (
                      <p className="mt-2 text-sm leading-6 text-slate-600">{question.rationale}</p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-500">
                      {question.category}
                    </div>
                    <div
                      className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${confidenceTone(
                        typeof question.confidence === "number" ? question.confidence : undefined,
                      )}`}
                    >
                      {formatPercent(question.confidence)}
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <textarea
                    value={answers[question.id] ?? ""}
                    onChange={(event) =>
                      setAnswers((current) => ({ ...current, [question.id]: event.target.value }))
                    }
                    rows={question.category === "experience_tools" ? 2 : 3}
                    className="min-h-[88px] w-full rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                    placeholder="Confirmer, corriger ou completer la reponse proposee"
                  />

                  {question.suggested_answer && (
                    <div className="rounded-[1rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      Proposition prechargee: <span className="font-medium text-slate-900">{question.suggested_answer}</span>
                    </div>
                  )}
                </div>
              </article>
            ))}
        </section>

        <aside className="space-y-4">
          <div className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="flex items-center gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Lecture du profil</div>
                <div className="text-[11px] text-slate-400">
                  {session ? `Provider technique: ${session.provider}` : "Initialisation du provider..."}
                </div>
              </div>
            </div>
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <p>
                Cette etape pre-remplit le profil a partir de ce qui a deja ete compris et vous laisse seulement
                confirmer les points qui meritent une verification.
              </p>
              <p>
                Au submit, les elements compris sont injectes automatiquement dans `career_profile` sans vous bloquer
                sur chaque question.
              </p>
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <SearchCheck className="h-4 w-4 text-emerald-600" />
              Points controles avant injection
            </div>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
              <li>distinction entre entites metier, projet, education et certification</li>
              <li>liens competence → outils → contexte → autonomie</li>
              <li>questions posees uniquement sur les zones incertaines</li>
              <li>preuves conservees dans `evidence_map` pour garder la tracabilite</li>
            </ul>
          </div>

          {relationSummary.evidenceEntries.length > 0 && (
            <div className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Evidence map
              </div>
              <div className="mt-4 space-y-3">
                {relationSummary.evidenceEntries.slice(0, 5).map(([field, items]) => (
                  <div key={field} className="rounded-[1rem] border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">{field}</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {items.slice(0, 4).map((item, index) => (
                        <span
                          key={`${field}-${item.source_type}-${index}`}
                          className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700"
                        >
                          {item.source_value || item.source_type}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </PremiumAppShell>
  );
}
