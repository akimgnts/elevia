import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, FileUp, ScanSearch, Sparkles, Type } from "lucide-react";
import {
  ingestCv,
  parseFile,
  parseFileEnriched,
  fetchKeySkills,
  saveSavedProfile,
  type ParseFileResponse,
  type SkillGroupItem,
  type KeySkillItem,
  type KeySkillsResponse,
  type RecoveredSkillItem,
  type AuditAIQualityResponse,
} from "../lib/api";
import { useProfileStore } from "../store/profileStore";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { DevStatusCard } from "../components/DevStatusCard";
import { ProfileCard } from "../components/analyze/ProfileCard";
import { MarketPositionCard } from "../components/analyze/MarketPositionCard";
import { ActionsCard } from "../components/analyze/ActionsCard";
import { DevPanel } from "../components/analyze/DevPanel";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import {
  buildUriLabelMap,
  labelFromUri,
  mapLabelsToUris,
  normalizeProfileSkills,
} from "../lib/skills/normalizeSkills";

const PLACEHOLDER_CV = `Jean Dupont\nData Analyst - 3 ans d'expérience\n\nFORMATION\nMaster Data Science, École Polytechnique (2020)\n\nEXPÉRIENCE\n- Analyste BI chez Acme Corp (2020-2023)\n  Python, SQL, Power BI, Tableau\n- Stage Data Engineer chez StartupXYZ (2019)\n  ETL, dbt, Airflow\n\nCOMPÉTENCES\n- Python, SQL, R\n- Power BI, Tableau, Looker\n- Excel avancé, VBA\n- Jira, Confluence\n\nLANGUES\n- Français (natif)\n- Anglais (C1)\n- Espagnol (B2)`;

// (legacy deriveKeySkills removed — Analyze now displays URI-unified skills only)

// ── Reason badge ──────────────────────────────────────────────────────────────

const REASON_BADGE_CLASS: Record<KeySkillItem["reason"], string | null> = {
  weighted: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  idf: "bg-violet-50 text-violet-700 ring-1 ring-violet-200",
  standard: null,
};

const REASON_LABEL: Record<KeySkillItem["reason"], string | null> = {
  weighted: "pondérée",
  idf: "rare",
  standard: null,
};

function ReasonBadge({ reason }: { reason: KeySkillItem["reason"] }) {
  const cls = REASON_BADGE_CLASS[reason];
  const label = REASON_LABEL[reason];
  if (!cls || !label) return null;
  return (
    <span className={`ml-1 rounded px-1 py-0.5 text-[10px] font-semibold ${cls}`}>
      {label}
    </span>
  );
}

type Tab = "file" | "text";

function buildPersistedAnalyzeProfile(result: ParseFileResponse): Record<string, unknown> {
  const profile = { ...(result.profile || {}) } as Record<string, unknown>;
  if (Array.isArray(result.canonical_skills)) {
    profile.canonical_skills = result.canonical_skills;
  }
  if (typeof result.canonical_skills_count === "number") {
    profile.canonical_skills_count = result.canonical_skills_count;
  }
  if (Array.isArray(result.enriched_signals)) {
    profile.enriched_signals = result.enriched_signals;
  }
  if (Array.isArray(result.concept_signals)) {
    profile.concept_signals = result.concept_signals;
  }
  if (result.profile_intelligence && !profile.profile_intelligence) {
    profile.profile_intelligence = result.profile_intelligence;
  }
  if (result.profile_intelligence_ai_assist && !profile.profile_intelligence_ai_assist) {
    profile.profile_intelligence_ai_assist = result.profile_intelligence_ai_assist;
  }
  return profile;
}

export default function AnalyzePage() {
  const navigate = useNavigate();
  const { setIngestResult } = useProfileStore();
  // ── Tab ─────────────────────────────────────────────────────────────────────
  const [tab, setTab] = useState<Tab>("file");

  // ── Text tab state ──────────────────────────────────────────────────────────
  const [cvText, setCvText] = useState("");
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState<string | null>(null);

  // ── File tab state ──────────────────────────────────────────────────────────
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [parseResult, setParseResult] = useState<ParseFileResponse | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [matchingLoading, setMatchingLoading] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<"baseline" | "enriched">("baseline");
  const [legacyLlmEnabled, setLegacyLlmEnabled] = useState(false);
  const isDev = import.meta.env.DEV;
  const devMode =
    isDev &&
    typeof window !== "undefined" &&
    (new URLSearchParams(window.location.search).get("dev") === "1" ||
      localStorage.getItem("devMode") === "1");
  const showDevPanel = isDev && (!!parseResult?.analyze_dev || devMode);

  // ── Key skills state (from API) ───────────────────────────────────────────
  const [keySkillsResult, setKeySkillsResult] = useState<KeySkillsResponse | null>(null);

  // ── Results UI state ─────────────────────────────────────────────────────────
  const [_expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [showFullList, setShowFullList] = useState(false);
  const [fullListSearch, setFullListSearch] = useState("");
  const [_debugOpen, setDebugOpen] = useState(false);
  const [_recoveredSkills, setRecoveredSkills] = useState<RecoveredSkillItem[]>([]);
  const [_recoveringSkills, setRecoveringSkills] = useState(false);
  const [_recoveryError, setRecoveryError] = useState<string | null>(null);
  const [_auditLoading, setAuditLoading] = useState(false);
  const [_auditError, setAuditError] = useState<string | null>(null);
  const [_auditResult, setAuditResult] = useState<AuditAIQualityResponse | null>(null);
  const [_validatedSearch, setValidatedSearch] = useState("");
  const [_filteredSearch, setFilteredSearch] = useState("");
  const [_rawSearch, setRawSearch] = useState("");


  // ── Text tab handlers ────────────────────────────────────────────────────────

  const handleTextSubmit = async () => {
    if (!cvText.trim()) {
      setTextError("Colle le texte de ton CV avant de continuer.");
      return;
    }
    setTextLoading(true);
    setTextError(null);
    try {
      const profile = await ingestCv(cvText);
      await setIngestResult(profile);
      if (profile && typeof profile === "object") {
        await saveSavedProfile(profile as Record<string, unknown>).catch(() => undefined);
      }
      navigate("/profile");
    } catch (err) {
      setTextError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setTextLoading(false);
    }
  };

  // ── File tab handlers ────────────────────────────────────────────────────────

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setParseResult(null);
    setParseError(null);
    setKeySkillsResult(null);
    setRecoveredSkills([]);
    setRecoveringSkills(false);
    setRecoveryError(null);
    setAuditLoading(false);
    setAuditError(null);
    setAuditResult(null);
    setShowFullList(false);
    setFullListSearch("");
    setDebugOpen(false);
    setValidatedSearch("");
    setFilteredSearch("");
    setRawSearch("");
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleParse = async () => {
    if (!selectedFile) return;
    setParsing(true);
    setParseError(null);
    setParseResult(null);
    setKeySkillsResult(null);
    setRecoveredSkills([]);
    setRecoveringSkills(false);
    setRecoveryError(null);
    setAuditLoading(false);
    setAuditError(null);
    setAuditResult(null);
    setShowFullList(false);
    setExpandedGroups(new Set());
    setDebugOpen(false);
    setValidatedSearch("");
    setFilteredSearch("");
    setRawSearch("");
    try {
      const useLegacyLlm = isDev && legacyLlmEnabled;
      const result = useLegacyLlm
        ? await parseFileEnriched(selectedFile)
        : await parseFile(selectedFile);
      setParseResult(result);
      const persistedProfile = buildPersistedAnalyzeProfile(result);
      await setIngestResult(persistedProfile);
      await saveSavedProfile(persistedProfile).catch(() => undefined);

      // Bridge domain signals to InboxPage (profile-level, not per-offer)
      if ((result.injected_esco_from_domain ?? 0) > 0 || (result.domain_skills_active?.length ?? 0) > 0) {
        localStorage.setItem("elevia_domain_signals", JSON.stringify({
          domain_skills_active: result.domain_skills_active ?? [],
          resolved_to_esco: result.resolved_to_esco ?? [],
          injected_esco_from_domain: result.injected_esco_from_domain ?? 0,
          total_esco_count: result.total_esco_count ?? 0,
        }));
      }

      // Fetch key skills ranking (graceful: never block on failure)
      if (result.validated_items?.length > 0) {
        try {
          const ks = await fetchKeySkills(result.validated_items);
          setKeySkillsResult(ks);
        } catch {
          // Fallback: no badges, use deriveKeySkills()
          setKeySkillsResult(null);
        }
      }

    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Erreur lors de l'analyse");
    } finally {
      setParsing(false);
    }
  };

  const handleOpenProfile = async () => {
    if (!parseResult) return;
    setMatchingLoading(true);
    try {
      await setIngestResult(buildPersistedAnalyzeProfile(parseResult));
      navigate("/profile");
    } finally {
      setMatchingLoading(false);
    }
  };

  // ── Derived display data ──────────────────────────────────────────────────────

  const skillGroups: SkillGroupItem[] = parseResult?.skill_groups ?? [];
  const allLabels: string[] = parseResult?.skills_canonical ?? [];
  const validatedItems = parseResult?.validated_items ?? [];
  const validatedCount = parseResult?.validated_skills ?? validatedItems.length;
  const legacyLlmRequested = isDev && legacyLlmEnabled;

  // Key skills: API-ranked (with badges) or fallback (no badges)
  const apiKeySkills: KeySkillItem[] = keySkillsResult?.key_skills ?? [];
  const labelMap = buildUriLabelMap(validatedItems, parseResult?.resolved_to_esco);
  const normalizedProfile = normalizeProfileSkills(parseResult?.profile ?? null, labelMap);
  const keySkillUris = mapLabelsToUris(apiKeySkills.map((s) => s.label), labelMap);
  const topSkillUris = (keySkillUris.length > 0 ? keySkillUris : normalizedProfile.uris).slice(0, 4);
  const topSkills = topSkillUris.map((uri) => labelMap[uri] ?? labelFromUri(uri));
  const languageGroup = skillGroups.find((g) => g.group.toLowerCase().includes("lang"));
  const languages = languageGroup?.items ?? [];

  // Modal list: API all_skills_ranked (with badges) or plain labels
  const apiAllSkills: KeySkillItem[] = keySkillsResult?.all_skills_ranked ?? [];
  const hasApiAll = apiAllSkills.length > 0;

  const filteredApiAll = apiAllSkills.filter(
    (s) =>
      fullListSearch.trim() === "" ||
      s.label.toLowerCase().includes(fullListSearch.trim().toLowerCase()),
  );
  const filteredFullList = allLabels.filter(
    (s) =>
      fullListSearch.trim() === "" ||
      s.toLowerCase().includes(fullListSearch.trim().toLowerCase()),
  );

  const validatedLabels = validatedItems.map((item) => item.label);
  const filteredTokens = parseResult?.filtered_tokens ?? null;
  const pipelineUsed = parseResult?.pipeline_used ?? null;
  const pipelineVariant = parseResult?.pipeline_variant ?? null;
  const compassEEnabled = parseResult?.compass_e_enabled ?? false;
  const allWarnings = parseResult?.warnings ?? [];
  const visibleWarnings = legacyLlmRequested
    ? allWarnings
    : allWarnings.filter((w) => !w.includes("DEPRECATED: enrich_llm=1"));

  const profileCluster = parseResult?.profile_cluster ?? null;

  // Domain signal derived data

  const profileSkillsUri = (parseResult?.profile?.skills_uri ?? []) as string[];
  const profileSkillsUriPromoted =
    (parseResult?.profile as { skills_uri_promoted?: string[] } | undefined)?.skills_uri_promoted ?? [];
  const skillsUriEffective = normalizedProfile.uris;

  const marketMatched = topSkills;
  const marketMissing: string[] = [];
  const marketNote = "Données marché indisponibles — affichage basé sur le profil.";

  const actionItems: string[] = [];
  if (marketMissing[0]) {
    actionItems.push(`Ajouter « ${marketMissing[0]} » au CV`);
  }
  if (profileCluster?.dominant_cluster) {
    actionItems.push(`Générer un CV optimisé pour ${profileCluster.dominant_cluster}`);
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <PremiumAppShell
      eyebrow="Analyse"
      title="Transformer le CV en profil exploitable"
      description="Le but ici n'est pas seulement d'extraire du texte. Elevia construit d'abord un profil lisible, puis alimente le cockpit, l'inbox et les candidatures."
      actions={
        <>
          <Link
            to="/profile"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Structurer mon profil
          </Link>
          <button
            type="button"
            onClick={handleOpenProfile}
            disabled={!parseResult || matchingLoading}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {matchingLoading ? "Chargement..." : "Voir mon profil"}
            <ArrowRight className="h-4 w-4" />
          </button>
        </>
      }
    >
      <div className="pt-2 pb-16">
        <DevStatusCard />

        <section className="mb-8 border-b border-slate-200/80 pb-6">
          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr] lg:items-start">
            <div>
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                <ScanSearch className="h-4 w-4" />
                Point d&apos;entrée du flux
              </div>
              <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">
                Déposez votre CV ou collez le texte.
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 md:text-base">
                Cette page construit la base utilisée ensuite par le profil, le cockpit, l&apos;inbox et les documents.
                L&apos;objectif ici est de rendre cette lecture utile avant toute décision.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                  Parsing déterministe
                </span>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                  Profil normalisé
                </span>
                <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                  Base du matching
                </span>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              {[
                ["Un profil comparable", "Compétences, langues et signaux structurants transformés en base exploitable."],
                ["Une lecture immédiate", "Top skills, cluster détecté et premières pistes d'action avant le cockpit."],
                ["Une suite produit cohérente", "La même base alimente ensuite le profil, le cockpit, les offres et l'inbox."],
              ].map(([label, copy]) => (
                <div key={label} className="rounded-[1.25rem] border border-slate-200/80 bg-white/80 px-4 py-4">
                  <div className="text-sm font-semibold text-slate-900">{label}</div>
                  <div className="mt-1 text-sm leading-6 text-slate-600">{copy}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Tabs */}
        <div className="mb-4 inline-flex rounded-full border border-slate-200 bg-white/80 p-1 shadow-sm">
          <button
            onClick={() => setTab("file")}
            className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors ${
              tab === "file"
                ? "bg-slate-900 text-white shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <FileUp className="h-4 w-4" />
            Fichier PDF / TXT
          </button>
          <button
            onClick={() => setTab("text")}
            className={`inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors ${
              tab === "text"
                ? "bg-slate-900 text-white shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Type className="h-4 w-4" />
            Coller le texte
          </button>
        </div>

        {/* ── File tab ─────────────────────────────────────────────────────────── */}
        {tab === "file" && (
          <GlassCard className="border-white/80 bg-white/80 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`cursor-pointer rounded-[1.5rem] border-2 border-dashed p-10 text-center transition-colors ${
                dragOver
                  ? "border-cyan-400 bg-cyan-50"
                  : selectedFile
                    ? "border-emerald-400 bg-emerald-50"
                    : "border-slate-200 bg-white/60 hover:border-cyan-300 hover:bg-cyan-50/40"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileSelect(file);
                }}
              />
              {selectedFile ? (
                <div>
                  <div className="text-2xl">📄</div>
                  <div className="mt-2 font-semibold text-emerald-700">{selectedFile.name}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    {(selectedFile.size / 1024).toFixed(0)} Ko — cliquer pour changer
                  </div>
                </div>
              ) : (
                <div>
                  <div className="text-3xl text-slate-400">↑</div>
                  <div className="mt-2 font-semibold text-slate-600">
                    Glisser-déposer ou cliquer pour sélectionner
                  </div>
                  <div className="text-xs text-slate-400 mt-1">PDF ou TXT · max 10 Mo</div>
                </div>
              )}
            </div>

            {/* Mode switch */}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Mode
              </span>
              <div className="inline-flex rounded-full border border-slate-200 bg-slate-100 p-1 text-xs font-semibold">
                <button
                  onClick={() => setAnalysisMode("baseline")}
                  className={`rounded-full px-3 py-1 transition ${
                    analysisMode === "baseline"
                      ? "bg-white text-slate-900 shadow"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  A (déterministe)
                </button>
                <button
                  onClick={() => setAnalysisMode("enriched")}
                  className={`rounded-full px-3 py-1 transition ${
                    analysisMode === "enriched"
                      ? "bg-white text-slate-900 shadow"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  A + IA (enrichi)
                </button>
              </div>
            </div>

            {isDev && (
              <div className="mt-2 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                <span className="font-semibold">DEV</span>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="h-4 w-4"
                    checked={legacyLlmEnabled}
                    onChange={(e) => setLegacyLlmEnabled(e.target.checked)}
                  />
                  Legacy LLM (deprecated)
                </label>
              </div>
            )}

            {/* Parse button */}
            <div className="mt-4 flex justify-end">
              <Button onClick={handleParse} disabled={!selectedFile || parsing}>
                {parsing ? "Analyse en cours..." : "Analyser le fichier"}
              </Button>
            </div>

            {/* Parse error */}
            {parseError && (
              <div className="mt-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-600">
                {parseError}
              </div>
            )}

            {/* ── Results ─────────────────────────────────────────────────────── */}
            {parseResult && (
              <div className="mt-6 space-y-6 border-t border-slate-100 pt-6">
                <div className="rounded-[1.5rem] border border-emerald-200 bg-gradient-to-r from-emerald-50 via-white to-cyan-50 p-5">
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">
                        <Sparkles className="h-4 w-4" />
                        Analyse terminee
                      </div>
                      <div className="mt-2 text-lg font-semibold text-slate-950">
                        {validatedCount} competence{validatedCount !== 1 ? "s" : ""} validee{validatedCount !== 1 ? "s" : ""}
                      </div>
                      <div className="mt-1 text-sm text-slate-600">
                        {parseResult.extracted_text_length} caracteres extraits · {parseResult.filename}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => setShowFullList(true)}
                        className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                      >
                        Voir toutes les competences
                      </button>
                      <Button onClick={handleOpenProfile} disabled={matchingLoading || validatedCount === 0}>
                        {matchingLoading ? "Chargement..." : "Structurer mon profil"}
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-3">
                  <ProfileCard
                    cluster={profileCluster?.dominant_cluster ?? null}
                    topSkills={topSkills}
                    languages={languages}
                    footer={
                      <div className="text-xs text-slate-400">
                        {parseResult.extracted_text_length} car. · {parseResult.filename}
                      </div>
                    }
                  />
                  <MarketPositionCard
                    matchedSkills={marketMatched}
                    missingSkills={marketMissing}
                    loading={false}
                    note={marketNote}
                  />
                  <ActionsCard actions={actionItems} />
                </div>

                {showDevPanel && (
                  <DevPanel
                    data={{
                      pipeline_used: pipelineUsed,
                      pipeline_variant: pipelineVariant,
                      compass_e_enabled: compassEEnabled,
                      tight_candidates: parseResult.tight_candidates ?? [],
                      filtered_tokens: filteredTokens ?? [],
                      validated_labels: validatedLabels,
                      skills_uri: profileSkillsUri,
                      skills_uri_promoted: profileSkillsUriPromoted,
                      skills_uri_effective: skillsUriEffective,
                      warnings: visibleWarnings,
                      analyze_dev: parseResult.analyze_dev,
                    }}
                  />
                )}
              </div>
            )}
          </GlassCard>
        )}

        {/* ── Text tab ─────────────────────────────────────────────────────────── */}
        {tab === "text" && (
          <GlassCard className="border-white/80 bg-white/80 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="mb-3">
              <label className="text-sm font-semibold text-slate-700">Texte du CV</label>
              <p className="mt-1 text-sm text-slate-500">
                Utile pour un test rapide, une reprise manuelle ou un debug sans passer par l&apos;upload de fichier.
              </p>
            </div>
            <textarea
              value={cvText}
              onChange={(e) => setCvText(e.target.value)}
              placeholder={PLACEHOLDER_CV}
              disabled={textLoading}
              className="mt-3 h-64 w-full resize-y rounded-xl border border-slate-200 bg-white/90 p-4 text-sm text-slate-700 shadow-sm outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
            />
            {textError && (
              <div className="mt-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-600">
                {textError}
              </div>
            )}
            <div className="mt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <span className="text-xs text-slate-500">
                Aucun fichier n&apos;est importe. Le texte reste sous votre controle.
              </span>
              <Button onClick={handleTextSubmit} disabled={textLoading}>
                {textLoading ? "Analyse en cours..." : "Structurer mon profil"}
              </Button>
            </div>
          </GlassCard>
        )}
      </div>

      {/* ── D) Full-list modal ────────────────────────────────────────────────── */}
      {showFullList && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowFullList(false); }}
        >
          <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-xl">
            {/* Modal header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <span className="font-semibold text-slate-800">
                Toutes les compétences ({hasApiAll ? apiAllSkills.length : allLabels.length})
              </span>
              <button
                onClick={() => setShowFullList(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                aria-label="Fermer"
              >
                ✕
              </button>
            </div>

            {/* Search */}
            <div className="border-b border-slate-100 px-5 py-3">
              <input
                type="search"
                value={fullListSearch}
                onChange={(e) => setFullListSearch(e.target.value)}
                placeholder="Rechercher..."
                autoFocus
                className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
              />
            </div>

            {/* Skill list */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {hasApiAll ? (
                filteredApiAll.length === 0 ? (
                  <p className="text-center text-sm text-slate-400">Aucun résultat</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {filteredApiAll.map((skill) => (
                      <span
                        key={skill.label}
                        className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                      >
                        {skill.label}
                        <ReasonBadge reason={skill.reason} />
                      </span>
                    ))}
                  </div>
                )
              ) : (
                filteredFullList.length === 0 ? (
                  <p className="text-center text-sm text-slate-400">Aucun résultat</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {filteredFullList.map((skill) => (
                      <span
                        key={skill}
                        className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                )
              )}
            </div>

            {/* Footer count */}
            <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-400">
              {hasApiAll
                ? `${filteredApiAll.length} compétence${filteredApiAll.length !== 1 ? "s" : ""} affichée${filteredApiAll.length !== 1 ? "s" : ""}${fullListSearch ? ` sur ${apiAllSkills.length}` : ""}`
                : `${filteredFullList.length} compétence${filteredFullList.length !== 1 ? "s" : ""} affichée${filteredFullList.length !== 1 ? "s" : ""}${fullListSearch ? ` sur ${allLabels.length}` : ""}`
              }
            </div>
          </div>
        </div>
      )}
    </PremiumAppShell>
  );
}
