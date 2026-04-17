import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  FileUp,
  Loader2,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react";
import {
  fetchProfileSkillSuggestions,
  fetchProfileToolSuggestions,
  parseFile,
  saveSavedProfile,
  type ParseFileResponse,
  type ProfileSkillSuggestion,
  type ProfileToolSuggestion,
} from "../lib/api";
import { useProfileStore } from "../store/profileStore";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";

type CanonicalSkillRef = {
  label: string;
  uri?: string | null;
  confidence?: number;
  method?: string;
  source?: string;
};

type IdentityV2 = {
  full_name?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
};

type AutonomyLevel = "execution" | "partial" | "autonomous" | "ownership";

/** A software tool or platform — not ESCO-mapped. */
type ToolRef = {
  label: string;
};

/**
 * Explicit skill ↔ tool ↔ context ↔ autonomy binding for one experience.
 * Stored in CareerExperience.skill_links on the backend.
 */
type SkillLinkItem = {
  skill: CanonicalSkillRef;
  tools: ToolRef[];
  context?: string;
  autonomy_level?: AutonomyLevel;
};

type ExperienceV2 = {
  title?: string;
  company?: string;
  start_date?: string;
  end_date?: string;
  responsibilities?: string[];
  tools?: CanonicalSkillRef[];
  canonical_skills_used?: CanonicalSkillRef[];
  autonomy_level?: AutonomyLevel;
  quantified_signals?: string[];
  impact_signals?: string[];
  context_tags?: string[];
  achievements?: string[];
  skills?: string[];
  autonomy?: "CONTRIB" | "COPILOT" | "LEAD";
  skill_links?: SkillLinkItem[];
};

type EducationV2 = {
  degree?: string;
  field?: string;
  institution?: string;
  start_date?: string;
  end_date?: string;
};

type LanguageV2 = {
  language?: string;
  level?: string;
};

type ProjectV2 = {
  title?: string;
  technologies?: string[];
  url?: string;
  impact?: string;
};

type CareerProfileV2 = {
  schema_version?: string;
  base_title?: string;
  summary_master?: string;
  target_title?: string;
  identity?: IdentityV2;
  experiences?: ExperienceV2[];
  education?: EducationV2[];
  languages?: LanguageV2[];
  projects?: ProjectV2[];
  certifications?: string[];
  selected_skills?: CanonicalSkillRef[];
  pending_skill_candidates?: string[];
  completeness?: number;
  skills_highlights?: string[];
};

type FullProfile = {
  career_profile?: CareerProfileV2;
  canonical_skills?: CanonicalSkillRef[];
  skills?: string[];
  matching_skills?: string[];
  experiences?: Record<string, unknown>[];
  [key: string]: unknown;
};

const GLASS =
  "rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm";

const AUTONOMY_OPTIONS: Array<{
  value: AutonomyLevel;
  label: string;
  helper: string;
  legacy: "CONTRIB" | "COPILOT" | "LEAD";
}> = [
  { value: "execution", label: "Exécution", helper: "Cadre défini, exécution attendue.", legacy: "CONTRIB" },
  { value: "partial", label: "Contribution partielle", helper: "Contribution claire, pilotage partagé.", legacy: "CONTRIB" },
  { value: "autonomous", label: "Autonome", helper: "Exécution et arbitrages sur son périmètre.", legacy: "COPILOT" },
  { value: "ownership", label: "Pilotage / ownership", helper: "Pilotage du sujet, coordination et responsabilité.", legacy: "LEAD" },
];

const CONTEXT_OPTIONS = [
  "environnement international",
  "équipe transverse",
  "retail",
  "communication",
  "marketing",
  "finance",
  "RH",
  "supply chain",
  "B2B",
  "B2C",
] as const;

const IMPACT_OPTIONS = [
  "amélioration de fiabilité",
  "automatisation",
  "support à la décision",
  "structuration du suivi",
  "amélioration visibilité",
  "meilleure coordination",
] as const;

function buildPersistedProfile(result: ParseFileResponse): Record<string, unknown> {
  const profile = { ...(result.profile || {}) } as Record<string, unknown>;
  if (Array.isArray(result.canonical_skills)) profile.canonical_skills = result.canonical_skills;
  if (typeof result.canonical_skills_count === "number") profile.canonical_skills_count = result.canonical_skills_count;
  if (Array.isArray(result.enriched_signals)) profile.enriched_signals = result.enriched_signals;
  if (Array.isArray(result.concept_signals)) profile.concept_signals = result.concept_signals;
  if (result.profile_intelligence && !profile.profile_intelligence) profile.profile_intelligence = result.profile_intelligence;
  if (result.profile_intelligence_ai_assist && !profile.profile_intelligence_ai_assist) profile.profile_intelligence_ai_assist = result.profile_intelligence_ai_assist;
  return profile;
}

function normalizeSkillRef(value: unknown): CanonicalSkillRef | null {
  if (typeof value === "string") {
    const label = value.trim();
    return label ? { label } : null;
  }
  if (!value || typeof value !== "object") return null;
  const rec = value as Record<string, unknown>;
  const label = typeof rec.label === "string" ? rec.label.trim() : "";
  if (!label) return null;
  return {
    label,
    uri: typeof rec.uri === "string" ? rec.uri : null,
    confidence: typeof rec.confidence === "number" ? rec.confidence : undefined,
    method: typeof rec.method === "string" ? rec.method : undefined,
    source: typeof rec.source === "string" ? rec.source : undefined,
  };
}

function dedupeStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    const normalized = value.trim();
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(normalized);
  }
  return out;
}

function dedupeSkillRefs(values: CanonicalSkillRef[]): CanonicalSkillRef[] {
  const seen = new Set<string>();
  const out: CanonicalSkillRef[] = [];
  for (const item of values) {
    const normalized = normalizeSkillRef(item);
    if (!normalized) continue;
    const key = normalized.uri || normalized.label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(normalized);
  }
  return out;
}

function dedupeTools(values: ToolRef[]): ToolRef[] {
  const seen = new Set<string>();
  const out: ToolRef[] = [];
  for (const item of values) {
    const label = item.label.trim();
    if (!label) continue;
    const key = label.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ label });
  }
  return out;
}

function legacyAutonomy(level: AutonomyLevel | undefined): "CONTRIB" | "COPILOT" | "LEAD" {
  return AUTONOMY_OPTIONS.find((option) => option.value === level)?.legacy || "COPILOT";
}

function normalizeSkillLink(value: unknown): SkillLinkItem | null {
  if (!value || typeof value !== "object") return null;
  const rec = value as Record<string, unknown>;
  const skill = normalizeSkillRef(rec.skill);
  if (!skill) return null;
  const rawTools = Array.isArray(rec.tools) ? rec.tools : [];
  const tools: ToolRef[] = rawTools
    .map((t) => {
      if (typeof t === "string") return t.trim() ? { label: t.trim() } : null;
      if (t && typeof t === "object" && typeof (t as Record<string, unknown>).label === "string") {
        const label = ((t as Record<string, unknown>).label as string).trim();
        return label ? { label } : null;
      }
      return null;
    })
    .filter((t): t is ToolRef => t !== null);
  const autonomy_level =
    rec.autonomy_level === "execution" || rec.autonomy_level === "partial" ||
    rec.autonomy_level === "autonomous" || rec.autonomy_level === "ownership"
      ? rec.autonomy_level
      : undefined;
  return {
    skill,
    tools,
    context: typeof rec.context === "string" ? rec.context.trim() || undefined : undefined,
    autonomy_level,
  };
}

function normalizeExperience(value: ExperienceV2 | Record<string, unknown> | undefined): ExperienceV2 {
  const rec = (value || {}) as Record<string, unknown>;
  const normalizedSkillLinks = Array.isArray(rec.skill_links)
    ? (rec.skill_links.map(normalizeSkillLink).filter(Boolean) as SkillLinkItem[])
    : [];
  const rawTools = Array.isArray(rec.tools) ? rec.tools : [];
  const rawSkills = Array.isArray(rec.canonical_skills_used)
    ? rec.canonical_skills_used
    : Array.isArray(rec.skills)
      ? rec.skills
      : [];
  const fallbackToolsFromLinks = normalizedSkillLinks.flatMap((link) => link.tools.map((tool) => ({ label: tool.label })));
  const fallbackSkillsFromLinks = normalizedSkillLinks.map((link) => link.skill);
  const autonomyLevel =
    rec.autonomy_level === "execution" ||
    rec.autonomy_level === "partial" ||
    rec.autonomy_level === "autonomous" ||
    rec.autonomy_level === "ownership"
      ? rec.autonomy_level
      : rec.autonomy === "LEAD"
        ? "ownership"
        : rec.autonomy === "CONTRIB"
          ? "execution"
          : "autonomous";

  return {
    title: typeof rec.title === "string" ? rec.title : "",
    company: typeof rec.company === "string" ? rec.company : "",
    start_date: typeof rec.start_date === "string" ? rec.start_date : "",
    end_date: typeof rec.end_date === "string" ? rec.end_date : typeof rec.dates === "string" ? rec.dates : "",
    responsibilities: Array.isArray(rec.responsibilities)
      ? rec.responsibilities.map(String).filter(Boolean)
      : Array.isArray(rec.bullets)
        ? rec.bullets.map(String).filter(Boolean)
        : [],
    tools: dedupeSkillRefs(
      (rawTools.length > 0 ? rawTools : fallbackToolsFromLinks)
        .map((item) => normalizeSkillRef(item))
        .filter(Boolean) as CanonicalSkillRef[]
    ),
    canonical_skills_used: dedupeSkillRefs(
      (rawSkills.length > 0 ? rawSkills : fallbackSkillsFromLinks)
        .map((item) => normalizeSkillRef(item))
        .filter(Boolean) as CanonicalSkillRef[]
    ),
    autonomy_level: autonomyLevel,
    quantified_signals: Array.isArray(rec.quantified_signals) ? dedupeStrings(rec.quantified_signals.map(String)) : [],
    impact_signals: Array.isArray(rec.impact_signals)
      ? dedupeStrings(rec.impact_signals.map(String))
      : Array.isArray(rec.achievements)
        ? dedupeStrings(rec.achievements.map(String))
        : [],
    context_tags: Array.isArray(rec.context_tags) ? dedupeStrings(rec.context_tags.map(String)) : [],
    achievements: Array.isArray(rec.achievements) ? dedupeStrings(rec.achievements.map(String)) : [],
    skills: Array.isArray(rec.skills) ? dedupeStrings(rec.skills.map(String)) : [],
    autonomy: legacyAutonomy(autonomyLevel),
    skill_links: normalizedSkillLinks,
  };
}

function normalizeCareerProfile(career: CareerProfileV2 | undefined, fullProfile: FullProfile): CareerProfileV2 {
  const current = career || {};
  return {
    ...current,
    schema_version: "v2",
    base_title: current.base_title || current.target_title || "",
    summary_master: current.summary_master || "",
    identity: current.identity || {},
    experiences: Array.isArray(current.experiences) ? current.experiences.map((exp) => normalizeExperience(exp)) : [],
    education: Array.isArray(current.education) ? current.education : [],
    languages: Array.isArray(current.languages) ? current.languages : [],
    projects: Array.isArray(current.projects) ? current.projects : [],
    certifications: Array.isArray(current.certifications) ? current.certifications.map(String) : [],
    selected_skills: dedupeSkillRefs(
      (Array.isArray(current.selected_skills) ? current.selected_skills : (Array.isArray(fullProfile.canonical_skills) ? fullProfile.canonical_skills : []))
        .map((item) => normalizeSkillRef(item))
        .filter(Boolean) as CanonicalSkillRef[]
    ),
    pending_skill_candidates: Array.isArray(current.pending_skill_candidates)
      ? dedupeStrings(current.pending_skill_candidates.map(String))
      : [],
  };
}

function computeCompleteness(profile: {
  identity: IdentityV2;
  baseTitle: string;
  summaryMaster: string;
  selectedSkills: CanonicalSkillRef[];
  experiences: ExperienceV2[];
  education: EducationV2[];
  languages: LanguageV2[];
}): number {
  let filled = 0;
  const total = 6;
  if (profile.identity.full_name) filled++;
  if (profile.baseTitle.trim()) filled++;
  if (profile.summaryMaster.trim()) filled++;
  if (profile.selectedSkills.length > 0) filled++;
  if (profile.experiences.length > 0) filled++;
  if (profile.education.length > 0 || profile.languages.length > 0) filled++;
  return filled / total;
}

function SectionLabel({ text }: { text: string }) {
  return <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{text}</div>;
}

const AUTONOMY_LABELS: Record<AutonomyLevel, string> = {
  execution: "Execution",
  partial: "Partielle",
  autonomous: "Autonome",
  ownership: "Ownership",
};

const AUTONOMY_BADGE_STYLES: Record<AutonomyLevel, string> = {
  execution: "border-slate-200 bg-slate-100 text-slate-600",
  partial: "border-amber-200 bg-amber-50 text-amber-700",
  autonomous: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ownership: "border-indigo-200 bg-indigo-50 text-indigo-700",
};

function hasPrimarySkillLinks(experience: ExperienceV2): boolean {
  return Boolean(experience.skill_links && experience.skill_links.length > 0);
}

function SkillLinkSummary({
  link,
  compact = false,
}: {
  link: SkillLinkItem;
  compact?: boolean;
}) {
  return (
    <div className={`rounded-[1rem] border border-slate-200 bg-white ${compact ? "px-3 py-2.5" : "px-4 py-3.5"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">{link.skill.label}</div>
          {link.tools.length > 0 && (
            <div className={`mt-1 flex flex-wrap gap-1.5 ${compact ? "" : "pt-0.5"}`}>
              {link.tools.map((tool) => (
                <span
                  key={tool.label}
                  className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700"
                >
                  {tool.label}
                </span>
              ))}
            </div>
          )}
          {link.context && <div className="mt-2 text-xs leading-5 text-slate-500">{link.context}</div>}
        </div>
        {link.autonomy_level && (
          <span
            className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${AUTONOMY_BADGE_STYLES[link.autonomy_level]}`}
          >
            {AUTONOMY_LABELS[link.autonomy_level]}
          </span>
        )}
      </div>
    </div>
  );
}

function ExperiencePrimarySignals({ experience }: { experience: ExperienceV2 }) {
  if (hasPrimarySkillLinks(experience)) {
    return (
      <div className="grid gap-2.5">
        {(experience.skill_links || []).map((link, index) => (
          <SkillLinkSummary key={`${link.skill.label}-${index}`} link={link} />
        ))}
      </div>
    );
  }

  const tools = experience.tools || [];
  const skills = experience.canonical_skills_used || [];
  if (tools.length === 0 && skills.length === 0) {
    return <div className="text-xs text-slate-400">Ajoutez un premier lien compétence → outils pour rendre cette expérience lisible côté produit et CV. Les champs legacy ne servent qu&apos;en secours.</div>;
  }

  return (
    <div className="grid gap-3 rounded-[1rem] border border-dashed border-slate-200 bg-slate-50/60 px-4 py-3">
      {skills.length > 0 && (
        <div className="grid gap-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Competences legacy</div>
          <div className="flex flex-wrap gap-1.5">
            {skills.map((skill) => (
              <span key={skill.label} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700">
                {skill.label}
              </span>
            ))}
          </div>
        </div>
      )}
      {tools.length > 0 && (
        <div className="grid gap-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Outils legacy</div>
          <div className="flex flex-wrap gap-1.5">
            {tools.map((tool) => (
              <span key={tool.label} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700">
                {tool.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="text-xs font-semibold text-slate-500">{children}</label>;
}

function TextInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
    />
  );
}

function TextArea({
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={rows}
      className="w-full resize-y rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
    />
  );
}

function UploadZone({ onFile, compact = false }: { onFile: (f: File) => void; compact?: boolean }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      onClick={() => fileRef.current?.click()}
      className={`cursor-pointer rounded-2xl border-2 border-dashed transition-colors ${
        dragOver
          ? "border-slate-900 bg-slate-50"
          : "border-slate-200 bg-white/60 hover:border-slate-300 hover:bg-slate-50/60"
      } ${compact ? "p-5" : "p-14"} text-center`}
    >
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.txt"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
      <FileUp className={`mx-auto text-slate-400 ${compact ? "h-6 w-6" : "h-10 w-10"}`} />
      <p className={`mt-2 font-semibold text-slate-700 ${compact ? "text-sm" : "text-base"}`}>
        {compact ? "Glisser un fichier ou cliquer" : "Glissez-déposez votre CV ou cliquez pour sélectionner"}
      </p>
      <p className="mt-1 text-xs text-slate-400">PDF ou TXT · max 10 Mo</p>
    </div>
  );
}

function ToggleTags({
  options,
  values,
  onChange,
}: {
  options: readonly string[];
  values: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => {
        const active = values.includes(option);
        return (
          <button
            key={option}
            type="button"
            onClick={() =>
              onChange(active ? values.filter((value) => value !== option) : [...values, option])
            }
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
              active
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
            }`}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}

function StringChipEditor({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");

  function commit() {
    if (!draft.trim()) return;
    onChange(dedupeStrings([...values, draft.trim()]));
    setDraft("");
  }

  return (
    <div className="grid gap-2">
      <FieldLabel>{label}</FieldLabel>
      <div className="flex flex-wrap gap-2">
        {values.map((value) => (
          <span
            key={value}
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-700"
          >
            {value}
            <button type="button" onClick={() => onChange(values.filter((item) => item !== value))} className="text-slate-400 hover:text-rose-500">
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <TextInput value={draft} onChange={setDraft} placeholder={placeholder} />
        <button
          type="button"
          onClick={commit}
          className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Ajouter
        </button>
      </div>
    </div>
  );
}

function ControlledSkillSelector({
  label,
  description,
  placeholder,
  selected,
  onChange,
  onPendingCandidate,
}: {
  label: string;
  description?: string;
  placeholder: string;
  selected: CanonicalSkillRef[];
  onChange: (next: CanonicalSkillRef[]) => void;
  onPendingCandidate?: (value: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProfileSkillSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const value = query.trim();
    if (value.length < 2) {
      setSuggestions([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(async () => {
      try {
        const result = await fetchProfileSkillSuggestions(value, 8);
        if (!cancelled) setSuggestions(result);
      } catch (err) {
        if (!cancelled) {
          setSuggestions([]);
          setError(err instanceof Error ? err.message : "Impossible de charger les suggestions");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  function addSuggestion(item: ProfileSkillSuggestion) {
    onChange(
      dedupeSkillRefs([
        ...selected,
        {
          label: item.label,
          uri: item.uri ?? null,
          confidence: item.confidence,
          method: item.method,
          source: item.source,
        },
      ])
    );
    setQuery("");
    setSuggestions([]);
  }

  function sendToPending() {
    const value = query.trim();
    if (!value || !onPendingCandidate) return;
    onPendingCandidate(value);
    setQuery("");
    setSuggestions([]);
  }

  return (
    <div className="grid gap-2">
      <div>
        <FieldLabel>{label}</FieldLabel>
        {description && <p className="mt-1 text-xs leading-5 text-slate-400">{description}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        {selected.map((item) => (
          <span
            key={item.uri || item.label}
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700"
          >
            {item.label}
            <button
              type="button"
              onClick={() => onChange(selected.filter((candidate) => (candidate.uri || candidate.label) !== (item.uri || item.label)))}
              className="text-slate-400 hover:text-rose-500"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="rounded-[1rem] border border-slate-200 bg-slate-50/70 p-3">
        <div className="flex gap-2">
          <TextInput value={query} onChange={setQuery} placeholder={placeholder} />
          {onPendingCandidate && (
            <button
              type="button"
              onClick={sendToPending}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
            >
              Pending
            </button>
          )}
        </div>
        {loading && <div className="mt-2 text-xs text-slate-400">Recherche en cours…</div>}
        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
        {!loading && !error && suggestions.length > 0 && (
          <div className="mt-3 grid gap-2">
            {suggestions.map((item) => (
              <button
                key={`${item.uri || item.label}-${item.method}`}
                type="button"
                onClick={() => addSuggestion(item)}
                className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-sm text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
              >
                <span className="font-medium text-slate-900">{item.label}</span>
                <span className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{item.method}</span>
              </button>
            ))}
          </div>
        )}
        {!loading && !error && query.trim().length >= 2 && suggestions.length === 0 && (
          <div className="mt-2 text-xs text-slate-500">
            Aucune suggestion propre trouvée. Cette entrée peut partir en pending review au lieu d&apos;entrer directement dans le profil.
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolChipSelector — autocomplete against /profile/tools/suggest (NOT ESCO)
// ---------------------------------------------------------------------------
function ToolChipSelector({
  selected,
  onChange,
}: {
  selected: ToolRef[];
  onChange: (next: ToolRef[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProfileToolSuggestion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const value = query.trim();
    if (value.length < 2) { setSuggestions([]); return; }
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const result = await fetchProfileToolSuggestions(value, 6);
        if (!cancelled) setSuggestions(result);
      } catch { if (!cancelled) setSuggestions([]); }
      finally { if (!cancelled) setLoading(false); }
    }, 150);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [query]);

  function addTool(label: string) {
    const trimmed = label.trim();
    if (!trimmed) return;
    const exists = selected.some((t) => t.label.toLowerCase() === trimmed.toLowerCase());
    if (!exists) onChange([...selected, { label: trimmed }]);
    setQuery(""); setSuggestions([]);
  }

  function commitDraft() {
    if (query.trim()) addTool(query.trim());
  }

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap gap-1.5">
        {selected.map((t) => (
          <span key={t.label} className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-800">
            {t.label}
            <button type="button" onClick={() => onChange(selected.filter((x) => x.label !== t.label))} className="text-blue-400 hover:text-rose-500">
              <X className="h-2.5 w-2.5" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <TextInput value={query} onChange={setQuery} placeholder="Excel, Power BI, SAP…" />
        <button type="button" onClick={commitDraft} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50">
          Ajouter
        </button>
      </div>
      {loading && <div className="text-xs text-slate-400">Recherche…</div>}
      {!loading && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button key={s.label} type="button" onClick={() => addTool(s.label)}
              className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-800 transition">
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SkillLinkEditor — per-experience skill ↔ tool ↔ context ↔ autonomy links
// ---------------------------------------------------------------------------
function SkillLinkEditor({
  links,
  onChange,
  onQueuePendingSkill,
}: {
  links: SkillLinkItem[];
  onChange: (next: SkillLinkItem[]) => void;
  onQueuePendingSkill: (value: string) => void;
}) {
  const blank: SkillLinkItem = { skill: { label: "" }, tools: [], context: "", autonomy_level: undefined };
  const [draft, setDraft] = useState<SkillLinkItem | null>(null);

  function commitDraft() {
    if (!draft || !draft.skill.label.trim()) return;
    onChange([...links, { ...draft, skill: { ...draft.skill, label: draft.skill.label.trim() }, context: draft.context?.trim() || undefined }]);
    setDraft(null);
  }

  function removLink(idx: number) {
    onChange(links.filter((_, i) => i !== idx));
  }

  return (
    <div className="grid gap-3">
      {links.length > 0 && (
        <div className="grid gap-2">
          {links.map((link, idx) => (
            <div key={idx} className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <SkillLinkSummary link={link} compact />
              </div>
              <button type="button" onClick={() => removLink(idx)} className="mt-0.5 text-slate-300 hover:text-rose-500 shrink-0">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {draft ? (
        <div className="rounded-[1rem] border border-slate-200 bg-white p-4 grid gap-4">
          <div className="grid gap-1">
            <FieldLabel>Compétence</FieldLabel>
            <ControlledSkillSelector
              label=""
              placeholder="Data analysis, reporting, prospection…"
              selected={draft.skill.label ? [draft.skill] : []}
              onChange={(items) => setDraft((d) => d ? { ...d, skill: items[items.length - 1] || { label: "" } } : d)}
              onPendingCandidate={onQueuePendingSkill}
            />
          </div>
          <div className="grid gap-1">
            <FieldLabel>Outils associés</FieldLabel>
            <ToolChipSelector selected={draft.tools} onChange={(tools) => setDraft((d) => d ? { ...d, tools } : d)} />
          </div>
          <div className="grid gap-1">
            <FieldLabel>Contexte (optionnel)</FieldLabel>
            <TextInput
              value={draft.context || ""}
              onChange={(v) => setDraft((d) => d ? { ...d, context: v.slice(0, 80) } : d)}
              placeholder="analyse de performance, gestion des commandes…"
            />
          </div>
          <div className="grid gap-1">
            <FieldLabel>Autonomie sur cette compétence</FieldLabel>
            <div className="flex flex-wrap gap-2">
              {(["execution", "partial", "autonomous", "ownership"] as AutonomyLevel[]).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setDraft((d) => d ? { ...d, autonomy_level: lvl } : d)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                    draft.autonomy_level === lvl
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                  }`}
                >
                  {AUTONOMY_LABELS[lvl]}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={commitDraft}
              disabled={!draft.skill.label.trim()}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
            >
              Ajouter ce lien
            </button>
            <button
              type="button"
              onClick={() => setDraft(null)}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
            >
              Annuler
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setDraft(blank)}
          className="inline-flex items-center gap-1.5 self-start rounded-full border border-dashed border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-500 transition hover:border-slate-400 hover:text-slate-700"
        >
          <Plus className="h-3 w-3" />
          Ajouter un lien compétence → outils
        </button>
      )}
    </div>
  );
}

function ExperienceEditor({
  experience,
  onChange,
  onRemove,
  onQueuePendingSkill,
}: {
  experience: ExperienceV2;
  onChange: (next: ExperienceV2) => void;
  onRemove: () => void;
  onQueuePendingSkill: (value: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const autonomy = experience.autonomy_level || "autonomous";
  const primaryLinks = experience.skill_links || [];
  const usesPrimaryLinks = hasPrimarySkillLinks(experience);

  return (
    <div className="overflow-hidden rounded-[1.25rem] border border-slate-200 bg-white">
      <div className="flex cursor-pointer items-center justify-between gap-3 px-4 py-3" onClick={() => setOpen((value) => !value)}>
        <div>
          <div className="text-sm font-semibold text-slate-900">{experience.title || "Nouvelle expérience"}</div>
          <div className="mt-1 text-xs text-slate-400">
            {[experience.company, experience.start_date && experience.end_date ? `${experience.start_date} — ${experience.end_date}` : experience.start_date || experience.end_date]
              .filter(Boolean)
              .join(" · ") || "À compléter"}
          </div>
          {usesPrimaryLinks && (
            <div className="mt-3 grid gap-2">
              {primaryLinks.slice(0, 2).map((link, index) => (
                <SkillLinkSummary key={`${link.skill.label}-${index}`} link={link} compact />
              ))}
              {primaryLinks.length > 2 && (
                <div className="text-xs font-medium text-slate-500">+{primaryLinks.length - 2} autre(s) lien(s) compétence → outils</div>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRemove();
            }}
            className="text-slate-300 hover:text-rose-500"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <span className="text-xs text-slate-400">{open ? "▲" : "▼"}</span>
        </div>
      </div>

      {open && (
        <div className="grid gap-4 border-t border-slate-100 px-4 py-4">
          <div className="grid gap-2">
            <FieldLabel>Compétences & outils utilisés</FieldLabel>
            <p className="text-xs leading-5 text-slate-500">
              Source principale affichée dans le produit et utilisée pour enrichir le CV. Chaque bloc relie une compétence, ses outils, son contexte et le niveau d&apos;autonomie.
            </p>
            <ExperiencePrimarySignals experience={experience} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1">
              <FieldLabel>Intitulé</FieldLabel>
              <TextInput value={experience.title || ""} onChange={(value) => onChange({ ...experience, title: value })} placeholder="Chargé d'affaires, Data Analyst…" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>Entreprise</FieldLabel>
              <TextInput value={experience.company || ""} onChange={(value) => onChange({ ...experience, company: value })} placeholder="Société Générale" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>Début</FieldLabel>
              <TextInput value={experience.start_date || ""} onChange={(value) => onChange({ ...experience, start_date: value })} placeholder="2023" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>Fin</FieldLabel>
              <TextInput value={experience.end_date || ""} onChange={(value) => onChange({ ...experience, end_date: value })} placeholder="2025 ou présent" />
            </div>
          </div>

          <div className="grid gap-1">
            <FieldLabel>Responsabilités principales</FieldLabel>
            <TextArea
              value={(experience.responsibilities || []).join("\n")}
              onChange={(value) =>
                onChange({
                  ...experience,
                  responsibilities: value
                    .split("\n")
                    .map((item) => item.trim())
                    .filter(Boolean),
                })
              }
              placeholder="Une ligne par responsabilité utile."
              rows={4}
            />
          </div>

          <StringChipEditor
            label="Données chiffrées"
            values={experience.quantified_signals || []}
            onChange={(quantifiedSignals) => onChange({ ...experience, quantified_signals: quantifiedSignals })}
            placeholder="Ex. 12 KPI suivis, 30% de temps gagné, 150 clients"
          />

          <div className="grid gap-2">
            <FieldLabel>Type d&apos;impact</FieldLabel>
            <ToggleTags options={IMPACT_OPTIONS} values={experience.impact_signals || []} onChange={(impactSignals) => onChange({ ...experience, impact_signals: impactSignals })} />
          </div>

          <div className="grid gap-2">
            <FieldLabel>Contexte</FieldLabel>
            <ToggleTags options={CONTEXT_OPTIONS} values={experience.context_tags || []} onChange={(contextTags) => onChange({ ...experience, context_tags: contextTags })} />
          </div>

          <div className="grid gap-2">
            <FieldLabel>Liens compétence → outils</FieldLabel>
            <p className="text-xs leading-5 text-slate-400">
              Associez chaque compétence clé aux outils avec lesquels vous l&apos;exercez dans cette expérience.
              Ce lien structure le signal pour le matching et la génération de CV.
            </p>
            <SkillLinkEditor
              links={experience.skill_links || []}
              onChange={(skill_links) => onChange({ ...experience, skill_links })}
              onQueuePendingSkill={onQueuePendingSkill}
            />
          </div>

          {usesPrimaryLinks ? (
            <div className="rounded-[1rem] border border-slate-200 bg-slate-50/70 px-4 py-3">
              <div className="text-sm font-semibold text-slate-900">Champs legacy conservés en compatibilite</div>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Les anciennes listes `tools` et `skills` restent stockees pour compatibilite, mais elles sont secondaires par rapport aux `skill_links` et derivees de ceux-ci a la sauvegarde.
              </p>
            </div>
          ) : (
            <>
              <ControlledSkillSelector
                label="Outils reellement utilises"
                description="Fallback legacy uniquement si vous n&apos;avez pas encore structure l&apos;experience avec des skill_links."
                placeholder="Power BI, Excel, SAP…"
                selected={experience.tools || []}
                onChange={(tools) => onChange({ ...experience, tools })}
                onPendingCandidate={onQueuePendingSkill}
              />

              <ControlledSkillSelector
                label="Competences reellement mobilisees"
                description="Fallback legacy secondaire, relie aux referentiels existants."
                placeholder="Reporting, paie, customer relationship management…"
                selected={experience.canonical_skills_used || []}
                onChange={(canonicalSkillsUsed) => onChange({ ...experience, canonical_skills_used: canonicalSkillsUsed })}
                onPendingCandidate={onQueuePendingSkill}
              />

              <div className="grid gap-2">
                <FieldLabel>Niveau d&apos;autonomie</FieldLabel>
                <div className="grid gap-2 sm:grid-cols-2">
                  {AUTONOMY_OPTIONS.map((option) => {
                    const active = autonomy === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => onChange({ ...experience, autonomy_level: option.value, autonomy: option.legacy })}
                        className={`rounded-[1rem] border px-4 py-3 text-left transition ${
                          active
                            ? "border-slate-900 bg-slate-900 text-white"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                        }`}
                      >
                        <div className="text-sm font-semibold">{option.label}</div>
                        <div className={`mt-1 text-xs leading-5 ${active ? "text-slate-200" : "text-slate-500"}`}>{option.helper}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function ProfilePage() {
  const { userProfile, setIngestResult, setUserProfile } = useProfileStore();

  const fullProfile = (userProfile || {}) as FullProfile;
  const currentCareer = normalizeCareerProfile(fullProfile.career_profile, fullProfile);

  const [identity, setIdentity] = useState<IdentityV2>(currentCareer.identity || {});
  const [baseTitle, setBaseTitle] = useState(currentCareer.base_title || "");
  const [summaryMaster, setSummaryMaster] = useState(currentCareer.summary_master || "");
  const [experiences, setExperiences] = useState<ExperienceV2[]>(currentCareer.experiences || []);
  const [education, setEducation] = useState<EducationV2[]>(currentCareer.education || []);
  const [languages, setLanguages] = useState<LanguageV2[]>(currentCareer.languages || []);
  const [projects, setProjects] = useState<ProjectV2[]>(currentCareer.projects || []);
  const [certifications, setCertifications] = useState<string[]>(currentCareer.certifications || []);
  const [selectedSkills, setSelectedSkills] = useState<CanonicalSkillRef[]>(currentCareer.selected_skills || []);
  const [pendingSkillCandidates, setPendingSkillCandidates] = useState<string[]>(currentCareer.pending_skill_candidates || []);

  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [showReimport, setShowReimport] = useState(false);

  const hasProfile = Boolean(
    identity.full_name ||
      baseTitle ||
      experiences.length > 0 ||
      selectedSkills.length > 0 ||
      (fullProfile.career_profile && typeof fullProfile.career_profile === "object")
  );

  const completeness = computeCompleteness({
    identity,
    baseTitle,
    summaryMaster,
    selectedSkills,
    experiences,
    education,
    languages,
  });
  const completePct = Math.round(completeness * 100);
  const completenessColor =
    completePct >= 80
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : completePct >= 40
        ? "text-amber-700 bg-amber-50 border-amber-200"
        : "text-rose-700 bg-rose-50 border-rose-200";

  function queuePendingSkill(value: string) {
    setPendingSkillCandidates((current) => dedupeStrings([...current, value]));
  }

  async function handleFile(file: File) {
    setParsing(true);
    setParseError(null);
    try {
      const result = await parseFile(file);
      const persisted = buildPersistedProfile(result);
      await setIngestResult(persisted);

      const nextFullProfile = persisted as FullProfile;
      const nextCareer = normalizeCareerProfile(nextFullProfile.career_profile, nextFullProfile);
      setIdentity(nextCareer.identity || {});
      setBaseTitle(nextCareer.base_title || "");
      setSummaryMaster(nextCareer.summary_master || "");
      setExperiences(nextCareer.experiences || []);
      setEducation(nextCareer.education || []);
      setLanguages(nextCareer.languages || []);
      setProjects(nextCareer.projects || []);
      setCertifications(nextCareer.certifications || []);
      setSelectedSkills(nextCareer.selected_skills || []);
      setPendingSkillCandidates(nextCareer.pending_skill_candidates || []);
      setShowReimport(false);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Erreur lors de l'analyse");
    } finally {
      setParsing(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setSaveNotice(null);

    const normalizedExperiences = experiences.map((experience) => {
      const rawSkillLinks = experience.skill_links || [];
      const seenSkillLabels = new Set<string>();
      const skillLinks = rawSkillLinks
        .map((link) => ({
          skill: { ...link.skill, label: link.skill.label.trim() },
          tools: dedupeTools(link.tools || []),
          context: link.context?.trim() || undefined,
          autonomy_level: link.autonomy_level,
        }))
        .filter((link) => {
          const key = link.skill.label.toLowerCase();
          if (!key || seenSkillLabels.has(key)) return false;
          seenSkillLabels.add(key);
          return true;
        });
      const tools = dedupeSkillRefs(
        (skillLinks.length > 0 ? skillLinks.flatMap((link) => link.tools.map((tool) => ({ label: tool.label }))) : (experience.tools || []))
          .map((item) => normalizeSkillRef(item))
          .filter(Boolean) as CanonicalSkillRef[]
      );
      const canonicalSkillsUsed = dedupeSkillRefs(
        (skillLinks.length > 0 ? skillLinks.map((link) => link.skill) : (experience.canonical_skills_used || []))
          .map((item) => normalizeSkillRef(item))
          .filter(Boolean) as CanonicalSkillRef[]
      );
      const quantifiedSignals = dedupeStrings(experience.quantified_signals || []);
      const impactSignals = dedupeStrings(experience.impact_signals || []);
      const achievements = dedupeStrings([...quantifiedSignals, ...impactSignals]);
      const contextTags = dedupeStrings(experience.context_tags || []);
      const autonomyLevel = experience.autonomy_level || "autonomous";
      return {
        ...experience,
        tools,
        canonical_skills_used: canonicalSkillsUsed,
        skills: canonicalSkillsUsed.map((item) => item.label),
        skill_links: skillLinks,
        quantified_signals: quantifiedSignals,
        impact_signals: impactSignals,
        achievements,
        context_tags: contextTags,
        autonomy_level: autonomyLevel,
        autonomy: legacyAutonomy(autonomyLevel),
      };
    });

    const selectedSkillItems = dedupeSkillRefs(selectedSkills);
    const selectedSkillLabels = selectedSkillItems.map((item) => item.label);
    const careerProfile: CareerProfileV2 = {
      ...currentCareer,
      schema_version: "v2",
      base_title: baseTitle.trim(),
      summary_master: summaryMaster.trim(),
      target_title: currentCareer.target_title || undefined,
      identity,
      experiences: normalizedExperiences,
      education,
      languages,
      projects,
      certifications: dedupeStrings(certifications),
      selected_skills: selectedSkillItems,
      pending_skill_candidates: dedupeStrings(pendingSkillCandidates),
      completeness,
      skills_highlights: selectedSkillLabels.slice(0, 14),
    };

    const updatedProfile: FullProfile = {
      ...fullProfile,
      canonical_skills: selectedSkillItems,
      skills: dedupeStrings([...(Array.isArray(fullProfile.skills) ? fullProfile.skills.map(String) : []), ...selectedSkillLabels]),
      matching_skills: dedupeStrings([...(Array.isArray(fullProfile.matching_skills) ? fullProfile.matching_skills.map(String) : []), ...selectedSkillLabels]),
      experiences: normalizedExperiences.map((experience) => ({
        title: experience.title,
        company: experience.company,
        start_date: experience.start_date,
        end_date: experience.end_date,
        dates: [experience.start_date, experience.end_date].filter(Boolean).join(" — "),
        bullets: experience.responsibilities || [],
        achievements: experience.achievements || [],
        tools: (experience.tools || []).map((item) => item.label),
        skills: experience.skills || [],
        autonomy: experience.autonomy,
        autonomy_level: experience.autonomy_level,
        quantified_signals: experience.quantified_signals || [],
        impact_signals: experience.impact_signals || [],
        context_tags: experience.context_tags || [],
        canonical_skills_used: experience.canonical_skills_used || [],
        skill_links: experience.skill_links || [],
      })),
      career_profile: careerProfile,
    };

    await setUserProfile(updatedProfile);
    try {
      await saveSavedProfile(updatedProfile as Record<string, unknown>);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 3000);
    } catch {
      setSaveNotice("Profil enregistré localement. Connectez-vous pour synchroniser avec le backend.");
    }

    setSaving(false);
  }

  if (!hasProfile && !parsing) {
    return (
      <PremiumAppShell
        eyebrow="Profil"
        title="Construire la base de vérité du produit"
        description="Importez votre CV pour démarrer. Le parsing est le point d'entrée, mais le profil enrichi sert ensuite au matching, aux documents et au suivi."
      >
        <div className="mx-auto max-w-2xl space-y-6">
          <div className={GLASS}>
            <SectionLabel text="Importer mon CV" />
            <div className="mt-4">
              <UploadZone onFile={handleFile} />
            </div>
            {parseError && (
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {parseError}
              </div>
            )}
          </div>
        </div>
      </PremiumAppShell>
    );
  }

  if (parsing) {
    return (
      <PremiumAppShell eyebrow="Profil" title="Analyse en cours…" description="Nous structurons le profil de base avant enrichissement manuel.">
        <div className="flex flex-col items-center gap-4 py-20 text-slate-500">
          <Loader2 className="h-10 w-10 animate-spin text-slate-900" />
          <span className="text-sm font-medium">Extraction de vos informations…</span>
        </div>
      </PremiumAppShell>
    );
  }

  return (
    <PremiumAppShell
      eyebrow="Profil"
      title={identity.full_name || "Profil source de vérité"}
      description="Ce profil alimente le matching, le cockpit, l'inbox, les candidatures et la génération de CV. Les informations enrichies ici servent ensuite à améliorer vos documents."
      actions={
        <>
          <button
            type="button"
            onClick={() => setShowReimport((value) => !value)}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <FileUp className="h-4 w-4" />
            Mettre à jour mon CV
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : saved ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            {saving ? "Enregistrement…" : saved ? "Enregistré" : "Enregistrer le profil"}
          </button>
        </>
      }
      contentClassName="max-w-7xl"
    >
      <div className="space-y-6 pb-12">
        <section className={`${GLASS} p-5`}>
          <SectionLabel text="Flux produit" />
          <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="text-lg font-semibold text-slate-950">Ce profil alimente votre matching et vos documents.</div>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
                Le parsing CV est seulement un point de départ. Cette page sert à contrôler les compétences, enrichir les expériences et préparer la génération de CV / lettre sans injecter de bruit.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to="/cockpit" className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800">Voir mon cockpit</Link>
              <Link to="/inbox" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Voir mes offres</Link>
              <Link to="/applications" className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Ouvrir candidatures</Link>
            </div>
          </div>
        </section>

        <div className={`flex items-center justify-between rounded-2xl border px-5 py-3 text-sm font-semibold ${completenessColor}`}>
          <span>Profil complété à {completePct}%</span>
          {completePct < 80 && <span className="text-xs font-normal">Ajoutez des expériences, des compétences contrôlées et du signal chiffré.</span>}
        </div>

        {saveNotice && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-800">
            {saveNotice}
          </div>
        )}

        {showReimport && (
          <div className={GLASS}>
            <div className="mb-3 flex items-center justify-between">
              <SectionLabel text="Importer un nouveau CV" />
              <button type="button" onClick={() => setShowReimport(false)} className="text-slate-400 hover:text-slate-700">
                <X className="h-4 w-4" />
              </button>
            </div>
            <UploadZone onFile={handleFile} compact />
            {parseError && (
              <div className="mt-3 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {parseError}
              </div>
            )}
          </div>
        )}

        <section className={GLASS}>
          <SectionLabel text="Identité et positionnement de base" />
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1">
              <FieldLabel>Nom complet</FieldLabel>
              <TextInput value={identity.full_name || ""} onChange={(value) => setIdentity((current) => ({ ...current, full_name: value }))} placeholder="Akim Guentas" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>Email</FieldLabel>
              <TextInput value={identity.email || ""} onChange={(value) => setIdentity((current) => ({ ...current, email: value }))} placeholder="akim@example.com" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>Téléphone</FieldLabel>
              <TextInput value={identity.phone || ""} onChange={(value) => setIdentity((current) => ({ ...current, phone: value }))} placeholder="+33 …" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>Localisation</FieldLabel>
              <TextInput value={identity.location || ""} onChange={(value) => setIdentity((current) => ({ ...current, location: value }))} placeholder="Le Havre, France" />
            </div>
            <div className="grid gap-1">
              <FieldLabel>LinkedIn</FieldLabel>
              <TextInput value={identity.linkedin || ""} onChange={(value) => setIdentity((current) => ({ ...current, linkedin: value }))} placeholder="linkedin.com/in/..." />
            </div>
            <div className="grid gap-1">
              <FieldLabel>GitHub</FieldLabel>
              <TextInput value={identity.github || ""} onChange={(value) => setIdentity((current) => ({ ...current, github: value }))} placeholder="github.com/..." />
            </div>
            <div className="grid gap-1 sm:col-span-2">
              <FieldLabel>Titre de base neutre</FieldLabel>
              <TextInput value={baseTitle} onChange={setBaseTitle} placeholder="Analyste data, Chargé de communication, Contrôleur de gestion…" />
              <p className="text-xs leading-5 text-slate-400">Ce champ décrit votre positionnement de base. Le titre du CV ciblé sera ensuite pris depuis l'offre.</p>
            </div>
            <div className="grid gap-1 sm:col-span-2">
              <FieldLabel>Résumé maître</FieldLabel>
              <TextArea value={summaryMaster} onChange={setSummaryMaster} placeholder="Positionnement de base, forces, environnements et logique de valeur." rows={4} />
            </div>
          </div>
        </section>

        <section className={GLASS}>
          <SectionLabel text="Compétences contrôlées" />
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Aucune compétence n&apos;entre librement dans le profil. Vous tapez, le système suggère, vous choisissez. Si rien n&apos;est proprement mappable, l&apos;entrée part en pending review.
          </p>
          <div className="mt-4 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <ControlledSkillSelector
              label="Compétences du profil"
              description="Ces compétences servent de base propre au profil enrichi."
              placeholder="Data, prospection, paie, SAP…"
              selected={selectedSkills}
              onChange={setSelectedSkills}
              onPendingCandidate={queuePendingSkill}
            />
            <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50/70 p-4">
              <div className="text-sm font-semibold text-slate-900">Pending review</div>
              <p className="mt-1 text-xs leading-5 text-slate-500">Ces propositions ne sont pas injectées dans le profil tant qu&apos;elles ne sont pas reliées à un référentiel.</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {pendingSkillCandidates.map((value) => (
                  <span key={value} className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800">
                    {value}
                    <button type="button" onClick={() => setPendingSkillCandidates((current) => current.filter((item) => item !== value))} className="text-amber-500 hover:text-amber-700">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                {pendingSkillCandidates.length === 0 && <div className="text-xs text-slate-400">Aucune entrée en attente pour l&apos;instant.</div>}
              </div>
            </div>
          </div>
        </section>

        <section className={GLASS}>
          <SectionLabel text="Structure de vos experiences" />
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Vue synthétique des signaux structurants déjà présents sur chaque expérience. Cette lecture est basée d&apos;abord sur `skill_links`, puis seulement sur les champs legacy.
          </p>
          <div className="mt-4 grid gap-4">
            {experiences.length > 0 ? (
              experiences.map((experience, index) => (
                <div key={`${experience.title || "experience"}-${index}`} className="rounded-[1.25rem] border border-slate-200 bg-slate-50/60 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-semibold text-slate-950">{experience.title || "Nouvelle expérience"}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {[experience.company, experience.start_date && experience.end_date ? `${experience.start_date} — ${experience.end_date}` : experience.start_date || experience.end_date]
                          .filter(Boolean)
                          .join(" · ") || "À compléter"}
                      </div>
                    </div>
                    {hasPrimarySkillLinks(experience) && (
                      <div className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
                        skill_links
                      </div>
                    )}
                  </div>
                  <div className="mt-4">
                    <ExperiencePrimarySignals experience={experience} />
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-[1.25rem] border border-dashed border-slate-200 bg-slate-50/60 px-4 py-4 text-sm text-slate-500">
                Ajoutez une expérience pour afficher ici sa structure de signaux avant édition.
              </div>
            )}
          </div>
        </section>

        <section className={GLASS}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <SectionLabel text="Expériences enrichies" />
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Ici vous ajoutez le signal qui manque souvent au parsing brut : outils réellement utilisés, compétences mobilisées, autonomie, contexte, données chiffrées et impact.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setExperiences((current) => [...current, normalizeExperience({})])}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              <Plus className="h-4 w-4" />
              Ajouter
            </button>
          </div>
          <div className="mt-4 space-y-4">
            {experiences.map((experience, index) => (
              <ExperienceEditor
                key={`${experience.title || "experience"}-${index}`}
                experience={experience}
                onChange={(next) => setExperiences((current) => current.map((item, itemIndex) => (itemIndex === index ? next : item)))}
                onRemove={() => setExperiences((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                onQueuePendingSkill={queuePendingSkill}
              />
            ))}
            {experiences.length === 0 && <div className="text-sm text-slate-400">Aucune expérience pour l&apos;instant. Importez un CV ou ajoutez un bloc manuellement.</div>}
          </div>
        </section>

        <section className={GLASS}>
          <SectionLabel text="Parcours complémentaire" />
          <div className="mt-4 grid gap-6 lg:grid-cols-3">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-900">Formation</div>
                <button type="button" onClick={() => setEducation((current) => [...current, { degree: "", field: "", institution: "" }])} className="text-xs font-semibold text-slate-500 hover:text-slate-900">Ajouter</button>
              </div>
              {education.map((item, index) => (
                <div key={`edu-${index}`} className="rounded-[1rem] border border-slate-200 bg-white p-3">
                  <div className="grid gap-2">
                    <TextInput value={item.degree || ""} onChange={(value) => setEducation((current) => current.map((edu, eduIndex) => (eduIndex === index ? { ...edu, degree: value } : edu)))} placeholder="Diplôme" />
                    <TextInput value={item.field || ""} onChange={(value) => setEducation((current) => current.map((edu, eduIndex) => (eduIndex === index ? { ...edu, field: value } : edu)))} placeholder="Domaine" />
                    <TextInput value={item.institution || ""} onChange={(value) => setEducation((current) => current.map((edu, eduIndex) => (eduIndex === index ? { ...edu, institution: value } : edu)))} placeholder="Établissement" />
                    <div className="grid grid-cols-2 gap-2">
                      <TextInput value={item.start_date || ""} onChange={(value) => setEducation((current) => current.map((edu, eduIndex) => (eduIndex === index ? { ...edu, start_date: value } : edu)))} placeholder="Début" />
                      <TextInput value={item.end_date || ""} onChange={(value) => setEducation((current) => current.map((edu, eduIndex) => (eduIndex === index ? { ...edu, end_date: value } : edu)))} placeholder="Fin" />
                    </div>
                    <button type="button" onClick={() => setEducation((current) => current.filter((_, eduIndex) => eduIndex !== index))} className="text-right text-xs font-semibold text-rose-500 hover:text-rose-700">Supprimer</button>
                  </div>
                </div>
              ))}
              {education.length === 0 && <div className="text-sm text-slate-400">Aucune formation renseignée.</div>}
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-900">Langues</div>
                <button type="button" onClick={() => setLanguages((current) => [...current, { language: "", level: "B2" }])} className="text-xs font-semibold text-slate-500 hover:text-slate-900">Ajouter</button>
              </div>
              {languages.map((item, index) => (
                <div key={`lang-${index}`} className="flex items-center gap-2 rounded-[1rem] border border-slate-200 bg-white p-3">
                  <input
                    type="text"
                    value={item.language || ""}
                    onChange={(event) => setLanguages((current) => current.map((language, languageIndex) => (languageIndex === index ? { ...language, language: event.target.value } : language)))}
                    placeholder="Français"
                    className="flex-1 rounded-lg border border-slate-200 bg-transparent px-2 py-1 text-sm outline-none focus:border-slate-900"
                  />
                  <select
                    value={item.level || "B2"}
                    onChange={(event) => setLanguages((current) => current.map((language, languageIndex) => (languageIndex === index ? { ...language, level: event.target.value } : language)))}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs outline-none focus:border-slate-900"
                  >
                    {["A1", "A2", "B1", "B2", "C1", "C2", "natif", "fluent"].map((level) => <option key={level}>{level}</option>)}
                  </select>
                  <button type="button" onClick={() => setLanguages((current) => current.filter((_, languageIndex) => languageIndex !== index))} className="text-slate-300 hover:text-rose-500">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {languages.length === 0 && <div className="text-sm text-slate-400">Aucune langue renseignée.</div>}
            </div>

            <div className="space-y-3">
              <StringChipEditor label="Certifications" values={certifications} onChange={setCertifications} placeholder="Google Analytics, TOEIC, SAP…" />
            </div>
          </div>
        </section>

        {projects.length > 0 ? (
          <section className={GLASS}>
            <div className="flex items-center justify-between">
              <SectionLabel text={`Projets (${projects.length})`} />
              <button type="button" onClick={() => setProjects((current) => [...current, { title: "", technologies: [], impact: "" }])} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                <Plus className="h-3.5 w-3.5" /> Ajouter
              </button>
            </div>
            <div className="mt-4 space-y-3">
              {projects.map((project, index) => (
                <div key={`project-${index}`} className="grid gap-3 rounded-[1rem] border border-slate-200 bg-white p-4 sm:grid-cols-2">
                  <TextInput value={project.title || ""} onChange={(value) => setProjects((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, title: value } : item)))} placeholder="Titre du projet" />
                  <TextInput value={(project.technologies || []).join(", ")} onChange={(value) => setProjects((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, technologies: value.split(",").map((skill) => skill.trim()).filter(Boolean) } : item)))} placeholder="Technologies" />
                  <TextInput value={project.impact || ""} onChange={(value) => setProjects((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, impact: value } : item)))} placeholder="Impact" />
                  <TextInput value={project.url || ""} onChange={(value) => setProjects((current) => current.map((item, itemIndex) => (itemIndex === index ? { ...item, url: value } : item)))} placeholder="URL" />
                  <div className="sm:col-span-2 flex justify-end">
                    <button type="button" onClick={() => setProjects((current) => current.filter((_, itemIndex) => itemIndex !== index))} className="text-xs font-semibold text-rose-500 hover:text-rose-700">Supprimer</button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <button type="button" onClick={() => setProjects([{ title: "", technologies: [], impact: "" }])} className="w-full rounded-[1.5rem] border-2 border-dashed border-slate-200 py-4 text-sm font-semibold text-slate-400 transition hover:border-slate-300 hover:text-slate-700">
            + Ajouter des projets personnels
          </button>
        )}
      </div>
    </PremiumAppShell>
  );
}
