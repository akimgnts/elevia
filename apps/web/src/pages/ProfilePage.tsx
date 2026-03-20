import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AlertTriangle, Plus, RotateCcw, Save, Sparkles } from "lucide-react";
import { useProfileStore } from "../store/profileStore";
import { buildMatchingProfile } from "../lib/profileMatching";
import { buildCorrectionEvent, postCorrectionMetric } from "../lib/api";
import type { ProfileMatchingV1 } from "../lib/profileMatching";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";

const CAPABILITY_LEVELS = ["beginner", "intermediate", "expert"] as const;
const CAPABILITY_NAMES = [
  "data_visualization",
  "spreadsheet_logic",
  "crm_management",
  "programming_scripting",
  "project_management",
] as const;

type Capability = {
  name: string;
  level: string;
  score: number;
  proofs: string[];
  tools_detected: string[];
};

type ProfileData = {
  candidate_info?: {
    first_name?: string;
    last_name?: string;
    email?: string;
    years_of_experience?: number;
  };
  detected_capabilities?: Capability[];
  languages?: { code: string; level: string; raw_text?: string }[];
  education_summary?: { level: string; raw_text?: string };
  unmapped_skills_high_confidence?: { raw_skill: string; confidence: number; proof: string }[];
};

type InboxProfileSnapshot = {
  profile_id: string;
  matching_profile: ProfileMatchingV1;
  skills_source: string;
  created_at: string;
};

const INBOX_PROFILE_SNAPSHOT_KEY = "elevia_inbox_profile_snapshot";

function readInboxProfileSnapshot(): InboxProfileSnapshot | null {
  try {
    const raw = localStorage.getItem(INBOX_PROFILE_SNAPSHOT_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as InboxProfileSnapshot;
  } catch {
    return null;
  }
}

function labelizeCapability(name: string): string {
  return name.replace(/_/g, " ");
}

function levelBadgeClass(level: string): string {
  if (level === "expert") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (level === "intermediate") return "bg-sky-50 text-sky-700 border-sky-200";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { aiProfile, userProfile, profileHash, sessionId, setUserProfile, clear } = useProfileStore();
  const snapshotMode = new URLSearchParams(location.search).get("snapshot") === "inbox";
  const inboxSnapshot = snapshotMode ? readInboxProfileSnapshot() : null;
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!aiProfile || !userProfile) {
      navigate("/analyze", { replace: true });
    }
  }, [aiProfile, userProfile, navigate]);

  useEffect(() => {
    if (userProfile) {
      const profile = userProfile as ProfileData;
      setCapabilities(profile.detected_capabilities || []);
    }
  }, [userProfile]);

  if (snapshotMode && inboxSnapshot) {
    return (
      <PremiumAppShell
        eyebrow="Snapshot"
        title="Profil compare depuis l'Inbox"
        description="Cette vue montre exactement les competences retenues pour le matching, afin d'expliquer les scores et les decisions."
        actions={
          <>
            <button
              onClick={() => navigate("/inbox")}
              className="rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Retour Inbox
            </button>
            <button
              onClick={() => navigate("/profile")}
              className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Profil complet
            </button>
          </>
        }
      >
        <div className="grid gap-6">
          <section className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="grid gap-2 text-sm text-slate-600 md:grid-cols-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">profile_id</div>
                <div className="mt-1 font-medium text-slate-900">{inboxSnapshot.profile_id}</div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">source</div>
                <div className="mt-1 font-medium text-slate-900">{inboxSnapshot.skills_source}</div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">snapshot</div>
                <div className="mt-1 font-medium text-slate-900">
                  {new Date(inboxSnapshot.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
            <h2 className="text-xl font-semibold text-slate-950">Competences utilisees pour le matching</h2>
            <div className="mt-4 flex flex-wrap gap-2">
              {inboxSnapshot.matching_profile.matching_skills.map((skill) => (
                <span
                  key={skill}
                  className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                >
                  {skill}
                </span>
              ))}
            </div>
          </section>
        </div>
      </PremiumAppShell>
    );
  }

  if (!aiProfile || !userProfile) {
    return <div className="p-6 text-sm text-slate-500">Redirection...</div>;
  }

  const profile = userProfile as ProfileData;
  const aiProfileData = aiProfile as ProfileData;
  const { profile: matchingProfile } = buildMatchingProfile(profile, profileHash || "anonymous");

  const aiCapNames = new Set((aiProfileData.detected_capabilities || []).map((c) => c.name));
  const userCapNames = new Set(capabilities.map((c) => c.name));
  const added = capabilities.filter((c) => !aiCapNames.has(c.name));
  const removed = (aiProfileData.detected_capabilities || []).filter((c) => !userCapNames.has(c.name));
  const modified = capabilities.filter((c) => {
    const aiCap = (aiProfileData.detected_capabilities || []).find((ac) => ac.name === c.name);
    return aiCap && aiCap.level !== c.level;
  });

  const hasChanges = added.length > 0 || removed.length > 0 || modified.length > 0;
  const availableToAdd = CAPABILITY_NAMES.filter((n) => !capabilities.some((c) => c.name === n));

  function handleLevelChange(index: number, newLevel: string) {
    const updated = [...capabilities];
    updated[index] = { ...updated[index], level: newLevel };
    setCapabilities(updated);
  }

  function handleRemove(index: number) {
    setCapabilities(capabilities.filter((_, i) => i !== index));
  }

  function handleAdd(name: string) {
    if (capabilities.some((c) => c.name === name)) return;
    setCapabilities([
      ...capabilities,
      {
        name,
        level: "beginner",
        score: 30,
        proofs: ["Ajoute manuellement"],
        tools_detected: [],
      },
    ]);
  }

  async function handleSaveAndMatch() {
    setSaving(true);

    const updatedProfile = {
      ...profile,
      detected_capabilities: capabilities,
    };
    await setUserProfile(updatedProfile);

    const correctionEvent = buildCorrectionEvent({
      sessionId: sessionId || `session_${Date.now()}`,
      profileHash: profileHash || "unknown",
      added: added.map((c) => c.name),
      deleted: removed.map((c) => c.name),
      modifiedLevel: modified.map((c) => ({
        name: c.name,
        from: (aiProfileData.detected_capabilities || []).find((ac) => ac.name === c.name)?.level || "unknown",
        to: c.level,
      })),
      unmappedCount: profile.unmapped_skills_high_confidence?.length || 0,
      detectedCapabilitiesCount: capabilities.length,
    });

    await postCorrectionMetric(correctionEvent);
    setSaving(false);
    navigate("/dashboard");
  }

  return (
    <PremiumAppShell
      eyebrow="Profil"
      title="Validation du profil"
      description="Ajustez les capacites detectees avant de lancer le matching. Les modifications sont tracees, mais le socle du matching reste visible."
      actions={
        <>
          <button
            onClick={() => {
              clear();
              navigate("/analyze", { replace: true });
            }}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <RotateCcw className="h-4 w-4" />
            Reset profil
          </button>
          <button
            onClick={handleSaveAndMatch}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-wait disabled:opacity-70"
          >
            <Save className="h-4 w-4" />
            {saving ? "Enregistrement..." : "Valider et voir mes matchs"}
          </button>
        </>
      }
    >
      <div className="grid gap-6">
        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Candidat</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              {profile.candidate_info?.first_name} {profile.candidate_info?.last_name}
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              {profile.candidate_info?.email || "Email non renseigne"} · {profile.candidate_info?.years_of_experience || 0} ans d&apos;experience
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
                {capabilities.length} capacites detectees
              </span>
              <span className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {matchingProfile.matching_skills.length} skills retenues pour le matching
              </span>
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              <Sparkles className="h-4 w-4 text-emerald-600" />
              Synthese des modifications
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                <div className="text-xs font-medium text-slate-500">Ajouts</div>
                <div className="mt-1 text-2xl font-semibold text-slate-950">{added.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                <div className="text-xs font-medium text-slate-500">Suppressions</div>
                <div className="mt-1 text-2xl font-semibold text-slate-950">{removed.length}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
                <div className="text-xs font-medium text-slate-500">Niveaux modifies</div>
                <div className="mt-1 text-2xl font-semibold text-slate-950">{modified.length}</div>
              </div>
            </div>
            <p className="mt-4 text-sm text-slate-600">
              {hasChanges
                ? "Les changements seront envoyes aux metriques de correction puis utilises pour le cockpit."
                : "Aucune modification pour le moment. Vous pouvez quand meme verifier le profil avant matching."}
            </p>
          </div>
        </section>

        <section className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Capacites detectees</div>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                Capacites detectees ({capabilities.length})
              </h2>
            </div>
            <p className="max-w-2xl text-sm text-slate-600">
              Ces capacites restent un signal UX. Le bloc plus bas montre ce qui nourrit effectivement le matching.
            </p>
          </div>

          <div className="mt-6 grid gap-4">
            {capabilities.map((cap, idx) => {
              const isAdded = added.some((a) => a.name === cap.name);
              const isModified = modified.some((m) => m.name === cap.name);
              return (
                <div
                  key={cap.name}
                  className={`rounded-[1.5rem] border p-5 transition ${
                    isAdded
                      ? "border-emerald-200 bg-emerald-50/70"
                      : isModified
                        ? "border-amber-200 bg-amber-50/70"
                        : "border-slate-200 bg-white"
                  }`}
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-semibold text-slate-950">{labelizeCapability(cap.name)}</h3>
                        {isAdded && (
                          <span className="rounded-full border border-emerald-200 bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                            Ajoute
                          </span>
                        )}
                        {isModified && (
                          <span className="rounded-full border border-amber-200 bg-amber-100 px-2.5 py-1 text-[11px] font-semibold text-amber-700">
                            Modifie
                          </span>
                        )}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${levelBadgeClass(cap.level)}`}>
                          {cap.level}
                        </span>
                        <span className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                          Score {cap.score}
                        </span>
                      </div>
                      <div className="mt-4 text-sm text-slate-600">
                        Outils detectes: {cap.tools_detected.join(", ") || "—"}
                      </div>
                      {cap.proofs.length > 0 && (
                        <div className="mt-2 text-sm text-slate-500">
                          Preuves: {cap.proofs.join(" · ")}
                        </div>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <select
                        value={cap.level}
                        onChange={(e) => handleLevelChange(idx, e.target.value)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                      >
                        {CAPABILITY_LEVELS.map((lvl) => (
                          <option key={lvl} value={lvl}>
                            {lvl}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => handleRemove(idx)}
                        className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
                      >
                        Supprimer
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {availableToAdd.length > 0 && (
          <section className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Ajout manuel</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Ajouter une capacite</h2>
            <div className="mt-5 flex flex-wrap gap-3">
              {availableToAdd.map((name) => (
                <button
                  key={name}
                  onClick={() => handleAdd(name)}
                  className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-semibold text-cyan-700 transition hover:bg-cyan-100"
                >
                  <Plus className="h-4 w-4" /> {labelizeCapability(name)}
                </button>
              ))}
            </div>
          </section>
        )}

        {removed.length > 0 && (
          <section className="rounded-[1.75rem] border border-rose-200 bg-rose-50/90 p-5 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 text-rose-600" />
              <div className="text-sm text-rose-700">
                <span className="font-semibold">Capacites supprimees:</span>{" "}
                {removed.map((r) => labelizeCapability(r.name)).join(", ")}
              </div>
            </div>
          </section>
        )}

        {profile.unmapped_skills_high_confidence && profile.unmapped_skills_high_confidence.length > 0 && (
          <section className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Hors referentiel</div>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
              Competences hors referentiel ({profile.unmapped_skills_high_confidence.length})
            </h2>
            <p className="mt-3 text-sm text-slate-600">
              Ces competences restent visibles comme signal secondaire si elles existent dans le profil.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {profile.unmapped_skills_high_confidence.map((skill) => (
                <span
                  key={skill.raw_skill}
                  className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                >
                  {skill.raw_skill} ({Math.round(skill.confidence * 100)}%)
                </span>
              ))}
            </div>
          </section>
        )}

        <section className="rounded-[1.75rem] border border-white/80 bg-white/75 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Source de verite matching</div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Profil utilise pour le matching</h2>
          <p className="mt-3 text-sm text-slate-600">
            Ce bloc est la vue la plus utile pour verifier ce que le moteur consomme reellement.
          </p>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Skills utilisees ({matchingProfile.matching_skills.length})
              </div>
              <div className="mt-3 text-sm leading-relaxed text-slate-700">
                {matchingProfile.matching_skills.length > 0 ? matchingProfile.matching_skills.join(", ") : "—"}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Langues</div>
              <div className="mt-3 text-sm leading-relaxed text-slate-700">
                {Array.isArray(matchingProfile.languages) && matchingProfile.languages.length > 0
                  ? matchingProfile.languages
                      .map((lang) => (typeof lang === "string" ? lang : lang?.code || ""))
                      .filter(Boolean)
                      .join(", ")
                  : "—"}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Niveau d&apos;etudes</div>
              <div className="mt-3 text-sm leading-relaxed text-slate-700">
                {matchingProfile.education || matchingProfile.education_summary?.level || "—"}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Pays preferes</div>
              <div className="mt-3 text-sm leading-relaxed text-slate-700">
                {matchingProfile.preferred_countries && matchingProfile.preferred_countries.length > 0
                  ? matchingProfile.preferred_countries.join(", ")
                  : "—"}
              </div>
            </div>
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Profile hash: {profileHash?.slice(0, 16)}...
          </div>
        </section>
      </div>
    </PremiumAppShell>
  );
}
