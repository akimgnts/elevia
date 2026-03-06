import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ingestCv,
  parseFile,
  parseFileEnriched,
  fetchKeySkills,
  fetchRecoverSkills,
  fetchAuditAiQuality,
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
import { PageContainer } from "../components/layout/PageContainer";
import { DevStatusCard } from "../components/DevStatusCard";
import { ProfileCard } from "../components/analyze/ProfileCard";
import { MarketPositionCard } from "../components/analyze/MarketPositionCard";
import { ActionsCard } from "../components/analyze/ActionsCard";
import { DevPanel } from "../components/analyze/DevPanel";
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

  // ── Key skills state (from API) ───────────────────────────────────────────
  const [keySkillsResult, setKeySkillsResult] = useState<KeySkillsResponse | null>(null);

  // ── Results UI state ─────────────────────────────────────────────────────────
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [showFullList, setShowFullList] = useState(false);
  const [fullListSearch, setFullListSearch] = useState("");
  const [debugOpen, setDebugOpen] = useState(false);
  const [recoveredSkills, setRecoveredSkills] = useState<RecoveredSkillItem[]>([]);
  const [recoveringSkills, setRecoveringSkills] = useState(false);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);
  const [recoveryMeta, setRecoveryMeta] = useState<{
    ai_available: boolean;
    ai_error: string | null;
    request_id: string | null;
    raw_count?: number | null;
    candidate_count?: number | null;
    dropped_count?: number | null;
    noise_ratio?: number | null;
    tech_density?: number | null;
    cache_hit?: boolean | null;
    ai_fired?: boolean | null;
  } | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditResult, setAuditResult] = useState<AuditAIQualityResponse | null>(null);
  const [validatedSearch, setValidatedSearch] = useState("");
  const [filteredSearch, setFilteredSearch] = useState("");
  const [rawSearch, setRawSearch] = useState("");


  const toggleGroup = (group: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

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

  const handleRunMatching = async () => {
    if (!parseResult) return;
    setMatchingLoading(true);
    try {
      await setIngestResult(parseResult.profile);
      navigate("/inbox");
    } finally {
      setMatchingLoading(false);
    }
  };

  // ── AI skill recovery (DEV-only) ─────────────────────────────────────────────
  const handleRecover = async (force = false) => {
    const cluster = profileCluster?.dominant_cluster;
    if (!cluster) return;
    setRecoveringSkills(true);
    setRecoveryError(null);
    setRecoveredSkills([]);
    setRecoveryMeta(null);
    try {
      const validatedSet = new Set(validatedLabels.map((l) => l.toLowerCase()));
      const ignored = filteredTokens ?? [];
      const ignoredSet = new Set(ignored.map((t) => t.toLowerCase()));
      const noise = (rawTokens ?? []).filter(
        (t) => !validatedSet.has(t.toLowerCase()) && !ignoredSet.has(t.toLowerCase()),
      );
      const profileFingerprint = parseResult?.profile_fingerprint ?? null;
      const extractedTextHash = parseResult?.extracted_text_hash ?? null;
      const resp = await fetchRecoverSkills({
        cluster,
        ignored_tokens: ignored,
        noise_tokens: noise,
        validated_esco_labels: validatedLabels,
        profile_fingerprint: profileFingerprint,
        extracted_text_hash: extractedTextHash,
        force,
      });
      const errorCode = resp.error_code || resp.ai_error || resp.error || null;
      let resolvedCode = errorCode ?? (resp.ai_available === false ? "AI_DISABLED" : null);
      if (!resolvedCode && resp.error_message) {
        resolvedCode = "UNKNOWN_ERROR";
      }
      setRecoveryMeta({
        ai_available: resp.ai_available,
        ai_error: resolvedCode,
        request_id: resp.request_id ?? null,
        raw_count: resp.raw_count ?? null,
        candidate_count: resp.candidate_count ?? null,
        dropped_count: resp.dropped_count ?? null,
        noise_ratio: resp.noise_ratio ?? null,
        tech_density: resp.tech_density ?? null,
        cache_hit: resp.cache_hit ?? false,
        ai_fired: resp.ai_fired ?? null,
      });
      if (resp.recovered_skills.length > 0) {
        setRecoveredSkills(resp.recovered_skills);
        if (resp.cache_hit) {
          setRecoveryError("Résultat récupéré (cache).");
        }
      } else if (resolvedCode === "OPENAI_KEY_MISSING") {
        setRecoveryError("Clé IA non configurée (OPENAI_API_KEY manquante côté API).");
      } else if (resolvedCode === "DEV_TOOLS_DISABLED") {
        setRecoveryError("DEV tools désactivés (ELEVIA_DEV_TOOLS=1 requis).");
      } else if (resolvedCode === "MODEL_MISSING") {
        setRecoveryError("Modèle IA non configuré (OPENAI_MODEL manquant côté API).");
      } else if (resolvedCode === "LLM_CALL_FAILED") {
        setRecoveryError("IA indisponible : échec d'appel LLM (voir logs).");
      } else if (resolvedCode === "CLUSTER_MISSING") {
        setRecoveryError("Cluster manquant pour la récupération IA.");
      } else if (resolvedCode === "INVALID_REQUEST") {
        setRecoveryError("Requête invalide (fingerprint manquant).");
      } else if (resolvedCode === "NETWORK_ERROR") {
        setRecoveryError("Erreur réseau : impossible de joindre l'API.");
      } else if (resolvedCode === "AI_DISABLED") {
        setRecoveryError("IA désactivée ou non disponible (pas de clé/config).");
      } else if (resolvedCode === "UNKNOWN_ERROR") {
        setRecoveryError(`IA indisponible : ${resp.error_message || "UNKNOWN_ERROR"}`);
      } else if (resp.error_message) {
        setRecoveryError(`IA indisponible : ${resp.error_message}`);
      } else {
        setRecoveryError("Aucune compétence supplémentaire détectée.");
      }
    } catch (err) {
      setRecoveryError("Erreur réseau : impossible de joindre l'API.");
    } finally {
      setRecoveringSkills(false);
    }
  };

  const handleAuditQuality = async () => {
    const cluster = profileCluster?.dominant_cluster;
    if (!cluster) return;
    setAuditLoading(true);
    setAuditError(null);
    setAuditResult(null);
    try {
      const resp = await fetchAuditAiQuality({
        cluster,
        validated_esco_labels: validatedLabels,
        recovered_skills: recoveredSkills.map((s) => s.label),
      });
      if (resp.error_code) {
        setAuditError(resp.error_message || resp.error_code);
      } else {
        setAuditResult(resp);
      }
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Audit IA indisponible");
    } finally {
      setAuditLoading(false);
    }
  };

  // ── Derived display data ──────────────────────────────────────────────────────

  const skillGroups: SkillGroupItem[] = parseResult?.skill_groups ?? [];
  const allLabels: string[] = parseResult?.skills_canonical ?? [];
  const validatedItems = parseResult?.validated_items ?? [];
  const rawDetected = parseResult?.raw_detected ?? 0;
  const validatedCount = parseResult?.validated_skills ?? validatedItems.length;
  const filteredOut = parseResult?.filtered_out ?? Math.max(0, rawDetected - validatedCount);
  const legacyLlmRequested = isDev && legacyLlmEnabled;
  const llmEffective = parseResult?.pipeline_variant === "legacy_llm_enrichment";
  const aiAvailable = parseResult?.ai_available ?? false;
  const aiError = parseResult?.ai_error ?? null;
  const aiAdded = parseResult?.ai_added_count ?? 0;

  // Key skills: API-ranked (with badges) or fallback (no badges)
  const apiKeySkills: KeySkillItem[] = keySkillsResult?.key_skills ?? [];
  const labelMap = buildUriLabelMap(validatedItems, parseResult?.resolved_to_esco);
  const normalizedProfile = normalizeProfileSkills(parseResult?.profile ?? null, labelMap);
  const keySkillUris = mapLabelsToUris(apiKeySkills.map((s) => s.label), labelMap);
  const topSkillUris = (keySkillUris.length > 0 ? keySkillUris : normalizedProfile.uris).slice(0, 4);
  const topSkills = topSkillUris.map((uri) => labelMap[uri] ?? labelFromUri(uri));
  const languageGroup = skillGroups.find((g) => g.group.toLowerCase().includes("lang"));
  const languages = languageGroup?.items ?? [];

  const autreGroup = skillGroups.find((g) => g.group === "Autres");
  const autreRatio = validatedCount > 0 ? (autreGroup?.count ?? 0) / validatedCount : 0;

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
  const rawTokens = parseResult?.raw_tokens ?? null;
  const filteredTokens = parseResult?.filtered_tokens ?? null;
  const pipelineUsed = parseResult?.pipeline_used ?? null;
  const pipelineVariant = parseResult?.pipeline_variant ?? null;
  const compassEEnabled = parseResult?.compass_e_enabled ?? false;
  const baselineEscoCount = parseResult?.baseline_esco_count ?? 0;
  const totalEscoCount = parseResult?.total_esco_count ?? 0;
  const aliasHitsCount = parseResult?.alias_hits_count ?? 0;
  const aliasHits = parseResult?.alias_hits ?? [];
  const skillsUriCount = parseResult?.skills_uri_count ?? validatedItems.length;
  const skillsUriCollapsed = parseResult?.skills_uri_collapsed_dupes ?? 0;
  const skillsUnmappedCount = parseResult?.skills_unmapped_count ?? filteredOut;
  const skillsDupes = parseResult?.skills_dupes ?? [];
  const allWarnings = parseResult?.warnings ?? [];
  const visibleWarnings = legacyLlmRequested
    ? allWarnings
    : allWarnings.filter((w) => !w.includes("DEPRECATED: enrich_llm=1"));

  const profileCluster = parseResult?.profile_cluster ?? null;
  const clusterDistribution = profileCluster?.distribution_percent ?? {};

  // Domain signal derived data
  const domainSkillsActive = parseResult?.domain_skills_active ?? [];
  const domainSkillsPendingCount = parseResult?.domain_skills_pending_count ?? 0;
  const resolvedToEsco = parseResult?.resolved_to_esco ?? [];
  const rejectedTokens = parseResult?.rejected_tokens ?? [];

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
  const injectedEscoFromDomain = parseResult?.injected_esco_from_domain ?? 0;
  const recoveryCached = recoveryMeta?.cache_hit ?? false;
  const topClusterDist = Object.entries(clusterDistribution)
    .filter(([, value]) => value > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  const filterTokens = (items: string[], query: string) => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => item.toLowerCase().includes(q));
  };

  const filteredValidatedLabels = filterTokens(validatedLabels, validatedSearch);
  const filteredRawTokens = rawTokens ? filterTokens(rawTokens, rawSearch) : [];
  const filteredIgnoredTokens = filteredTokens ? filterTokens(filteredTokens, filteredSearch) : [];

  const copyToClipboard = async (items: string[]) => {
    if (!items.length) return;
    try {
      await navigator.clipboard.writeText(items.join("\n"));
    } catch {
      // ignore clipboard failures
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50">
      <PageContainer className="pt-12 pb-16">
        <DevStatusCard />

        <div className="mb-8">
          <div className="text-sm font-semibold text-slate-500">Analyse</div>
          <h1 className="text-3xl font-bold text-slate-900">Déposez votre CV</h1>
          <p className="mt-2 text-slate-600">
            Nous analysons vos compétences pour activer le matching VIE.
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-4 flex gap-0 border-b border-slate-200">
          <button
            onClick={() => setTab("file")}
            className={`px-5 py-2.5 text-sm font-semibold transition-colors ${
              tab === "file"
                ? "border-b-2 border-cyan-500 text-cyan-600"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Fichier PDF / TXT
          </button>
          <button
            onClick={() => setTab("text")}
            className={`px-5 py-2.5 text-sm font-semibold transition-colors ${
              tab === "text"
                ? "border-b-2 border-cyan-500 text-cyan-600"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Coller le texte
          </button>
        </div>

        {/* ── File tab ─────────────────────────────────────────────────────────── */}
        {tab === "file" && (
          <GlassCard className="p-6">
            {/* Drop zone */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
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
              <div className="inline-flex rounded-full bg-slate-100 p-1 text-xs font-semibold">
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

                <div className="flex justify-end">
                  <Button onClick={handleRunMatching} disabled={matchingLoading || validatedCount === 0}>
                    {matchingLoading ? "Chargement..." : "Voir mes offres correspondantes"}
                  </Button>
                </div>

                {devMode && (
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
                    }}
                  />
                )}
              </div>
            )}
          </GlassCard>
        )}

        {/* ── Text tab ─────────────────────────────────────────────────────────── */}
        {tab === "text" && (
          <GlassCard className="p-6">
            <label className="text-sm font-semibold text-slate-700">Texte du CV</label>
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
                Aucun fichier n'est importé. Le texte reste sous votre contrôle.
              </span>
              <Button onClick={handleTextSubmit} disabled={textLoading}>
                {textLoading ? "Analyse en cours..." : "Trouver mes offres"}
              </Button>
            </div>
          </GlassCard>
        )}
      </PageContainer>

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
    </div>
  );
}
