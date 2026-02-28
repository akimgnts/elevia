import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ingestCv,
  parseFile,
  parseFileEnriched,
  fetchKeySkills,
  type ParseFileResponse,
  type SkillGroupItem,
  type KeySkillItem,
  type KeySkillsResponse,
} from "../lib/api";
import { useProfileStore } from "../store/profileStore";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { PageContainer } from "../components/layout/PageContainer";
import { DevStatusCard } from "../components/DevStatusCard";

const PLACEHOLDER_CV = `Jean Dupont\nData Analyst - 3 ans d'expérience\n\nFORMATION\nMaster Data Science, École Polytechnique (2020)\n\nEXPÉRIENCE\n- Analyste BI chez Acme Corp (2020-2023)\n  Python, SQL, Power BI, Tableau\n- Stage Data Engineer chez StartupXYZ (2019)\n  ETL, dbt, Airflow\n\nCOMPÉTENCES\n- Python, SQL, R\n- Power BI, Tableau, Looker\n- Excel avancé, VBA\n- Jira, Confluence\n\nLANGUES\n- Français (natif)\n- Anglais (C1)\n- Espagnol (B2)`;

// Groups shown first when deriving key skills (fallback when API unavailable)
const KEY_SKILL_PRIORITY = ["Numérique", "Aptitudes & Compétences"];
const MAX_KEY_SKILLS = 12;

/** Deterministic fallback: pick up to MAX_KEY_SKILLS labels, priority groups first. */
function deriveKeySkills(groups: SkillGroupItem[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  const addFromGroup = (g: SkillGroupItem) => {
    for (const skill of [...g.items].sort()) {
      if (!seen.has(skill) && result.length < MAX_KEY_SKILLS) {
        seen.add(skill);
        result.push(skill);
      }
    }
  };

  for (const name of KEY_SKILL_PRIORITY) {
    const g = groups.find((g) => g.group === name);
    if (g) addFromGroup(g);
  }

  const others = groups
    .filter((g) => !KEY_SKILL_PRIORITY.includes(g.group))
    .sort((a, b) => a.group.localeCompare(b.group, "fr"));
  for (const g of others) addFromGroup(g);

  return result;
}

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
  const [analysisMode, setAnalysisMode] = useState<"baseline" | "llm">("baseline");

  // ── Key skills state (from API) ───────────────────────────────────────────
  const [keySkillsResult, setKeySkillsResult] = useState<KeySkillsResponse | null>(null);

  // ── Results UI state ─────────────────────────────────────────────────────────
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [showFullList, setShowFullList] = useState(false);
  const [fullListSearch, setFullListSearch] = useState("");
  const [debugOpen, setDebugOpen] = useState(false);
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
    setShowFullList(false);
    setExpandedGroups(new Set());
    setDebugOpen(false);
    setValidatedSearch("");
    setFilteredSearch("");
    setRawSearch("");
    try {
      const result =
        analysisMode === "llm"
          ? await parseFileEnriched(selectedFile)
          : await parseFile(selectedFile);
      setParseResult(result);

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

  // ── Derived display data ──────────────────────────────────────────────────────

  const skillGroups: SkillGroupItem[] = parseResult?.skill_groups ?? [];
  const allLabels: string[] = parseResult?.skills_canonical ?? [];
  const validatedItems = parseResult?.validated_items ?? [];
  const rawDetected = parseResult?.raw_detected ?? 0;
  const validatedCount = parseResult?.validated_skills ?? validatedItems.length;
  const filteredOut = parseResult?.filtered_out ?? Math.max(0, rawDetected - validatedCount);
  const llmRequested = analysisMode === "llm";
  const llmEffective = parseResult?.mode === "llm";
  const aiAvailable = parseResult?.ai_available ?? false;
  const aiError = parseResult?.ai_error ?? null;
  const aiAdded = parseResult?.ai_added_count ?? 0;

  // Key skills: API-ranked (with badges) or fallback (no badges)
  const apiKeySkills: KeySkillItem[] = keySkillsResult?.key_skills ?? [];
  const fallbackKeySkills: string[] = deriveKeySkills(skillGroups);
  const hasApiRanking = apiKeySkills.length > 0;

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
  const aliasHitsCount = parseResult?.alias_hits_count ?? 0;
  const aliasHits = parseResult?.alias_hits ?? [];
  const skillsUriCount = parseResult?.skills_uri_count ?? validatedItems.length;
  const skillsUriCollapsed = parseResult?.skills_uri_collapsed_dupes ?? 0;
  const skillsUnmappedCount = parseResult?.skills_unmapped_count ?? filteredOut;
  const skillsDupes = parseResult?.skills_dupes ?? [];

  const profileCluster = parseResult?.profile_cluster ?? null;
  const clusterDistribution = profileCluster?.distribution_percent ?? {};
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
                  onClick={() => setAnalysisMode("llm")}
                  className={`rounded-full px-3 py-1 transition ${
                    analysisMode === "llm"
                      ? "bg-white text-slate-900 shadow"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  A + IA (enrichi)
                </button>
              </div>
            </div>

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
              <div className="mt-6 space-y-5 border-t border-slate-100 pt-5">

                {/* A) Health counters */}
                <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
                  <span className="font-semibold text-emerald-700">
                    Validées&nbsp;
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold">
                      {validatedCount}
                    </span>
                  </span>
                  <span className="text-slate-500">
                    Ignorées&nbsp;
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                      {filteredOut}
                    </span>
                  </span>
                  <span className="text-slate-400">
                    Brut détecté&nbsp;
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                      {rawDetected}
                    </span>
                  </span>
                  {autreGroup && autreGroup.count > 0 && (
                    <span className={autreRatio > 0.4 ? "text-amber-600 font-medium" : "text-slate-400"}>
                      Autres&nbsp;
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                        {autreGroup.count}
                      </span>
                      {autreRatio > 0.4 && (
                        <span className="ml-1 text-xs">⚠ signal faible</span>
                      )}
                    </span>
                  )}
                  <span className="ml-auto text-xs text-slate-400">
                    {parseResult.extracted_text_length} car. · {parseResult.filename}
                  </span>
                </div>

                {/* Warnings */}
                {(parseResult.warnings?.length ?? 0) > 0 && (
                  <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">
                    {(parseResult.warnings ?? []).join(" · ")}
                  </div>
                )}

                {/* Profile cluster */}
                {profileCluster && (
                  <div className="rounded-xl border border-slate-200 bg-white/70 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-semibold text-slate-700">Domaine détecté</div>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                        {profileCluster.dominant_cluster}
                      </span>
                    </div>
                    <div className="mt-2 text-sm text-slate-600">
                      Dominance: <span className="font-semibold">{profileCluster.dominance_percent}%</span>
                    </div>
                    {topClusterDist.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                        {topClusterDist.map(([cluster, value]) => (
                          <span key={cluster} className="rounded bg-slate-100 px-2 py-1">
                            {cluster}: {value}%
                          </span>
                        ))}
                      </div>
                    )}
                    {profileCluster.note === "LOW_SIGNAL" && (
                      <div className="mt-2 text-xs font-medium text-amber-700">
                        Signal insuffisant (parsing à renforcer)
                      </div>
                    )}
                    {profileCluster.note === "TRANSVERSAL" && (
                      <div className="mt-2 text-xs font-medium text-slate-600">
                        Profil transversal
                      </div>
                    )}
                  </div>
                )}

                {/* LLM fallback */}
                {llmRequested && parseResult && !aiAvailable && (
                  <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">
                    IA indisponible: clé OPENAI_API_KEY manquante (apps/api/.env). Résultat déterministe.
                  </div>
                )}

                {llmRequested && parseResult && aiAvailable && aiError === "llm_failed" && (
                  <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">
                    IA indisponible (erreur appel). Résultat déterministe.
                  </div>
                )}

                {/* LLM delta */}
                {llmEffective && (
                  <div className="text-xs font-medium text-slate-500">
                    IA a ajouté: +{aiAdded} compétence{aiAdded !== 1 ? "s" : ""} candidate{aiAdded !== 1 ? "s" : ""}
                  </div>
                )}

                {/* Zero-state: no ESCO skills found */}
                {validatedCount === 0 ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-center">
                    <p className="font-semibold text-slate-700">Aucune compétence ESCO reconnue</p>
                    <p className="mt-1 text-sm text-slate-500">
                      Le fichier a peut-être un contenu difficile à extraire.
                      Essayez de coller le texte dans l'onglet "Coller le texte".
                    </p>
                    <p className="mt-2 text-xs text-slate-400">
                      Brut détecté: {rawDetected} · Ignorées: {filteredOut}
                    </p>
                  </div>
                ) : (
                  <>
                    {/* B) Key skills — with reason badges when API available */}
                    <div>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-semibold text-slate-700">
                          Compétences clés&nbsp;
                          <span className="font-normal text-slate-400">
                            {hasApiRanking ? apiKeySkills.length : fallbackKeySkills.length}
                            &nbsp;/&nbsp;{validatedCount}
                          </span>
                        </span>
                        <button
                          onClick={() => { setShowFullList(true); setFullListSearch(""); }}
                          className="text-xs font-medium text-cyan-600 hover:text-cyan-800 hover:underline"
                        >
                          Voir toutes les compétences ({validatedCount})
                        </button>
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {hasApiRanking ? (
                          apiKeySkills.map((skill) => (
                            <span
                              key={skill.label}
                              className="inline-flex items-center rounded-full bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-800 ring-1 ring-cyan-200"
                            >
                              {skill.label}
                              <ReasonBadge reason={skill.reason} />
                            </span>
                          ))
                        ) : (
                          fallbackKeySkills.map((skill) => (
                            <span
                              key={skill}
                              className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-800 ring-1 ring-cyan-200"
                            >
                              {skill}
                            </span>
                          ))
                        )}
                      </div>

                      {/* Badge legend (only shown when API ranking available) */}
                      {hasApiRanking && (
                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
                          <span>Signal :</span>
                          <span className="inline-flex items-center gap-1">
                            <span className="rounded px-1 py-0.5 bg-amber-50 text-amber-700 ring-1 ring-amber-200 font-semibold">pondérée</span>
                            requise dans ce domaine
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <span className="rounded px-1 py-0.5 bg-violet-50 text-violet-700 ring-1 ring-violet-200 font-semibold">rare</span>
                            peu commune (IDF élevé)
                          </span>
                        </div>
                      )}
                    </div>

                    {/* C) Grouped skills — collapsible */}
                    {skillGroups.length > 0 && (
                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                          Détail par groupe
                        </p>
                        <div className="space-y-1.5">
                          {skillGroups.map((group) => {
                            const isOpen = expandedGroups.has(group.group);
                            return (
                              <div
                                key={group.group}
                                className="rounded-xl border border-slate-100 bg-white/80"
                              >
                                <button
                                  onClick={() => toggleGroup(group.group)}
                                  className="flex w-full items-center justify-between px-4 py-2.5 text-left"
                                >
                                  <span className="text-sm font-semibold text-slate-700">
                                    {group.group}
                                    <span className="ml-1.5 font-normal text-slate-400">
                                      — {group.count}
                                    </span>
                                  </span>
                                  <span className="text-xs text-slate-400">
                                    {isOpen ? "▲" : "▼"}
                                  </span>
                                </button>
                                {isOpen && (
                                  <div className="border-t border-slate-100 px-4 pb-3 pt-2">
                                    <div className="flex flex-wrap gap-1.5">
                                      {group.items.map((skill) => (
                                        <span
                                          key={skill}
                                          className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
                                        >
                                          {skill}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* Debug toggle + panels */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <button
                    onClick={() => setDebugOpen((prev) => !prev)}
                    className="flex w-full items-center justify-between text-left text-sm font-semibold text-slate-700"
                  >
                    <span>Debug (pour toi) — pas pour l’utilisateur final</span>
                    <span className="text-xs text-slate-400">{debugOpen ? "▲" : "▼"}</span>
                  </button>

                  {debugOpen && (
                    <div className="mt-4 space-y-3">
                      <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-500">
                        Compétences (URIs): <span className="font-semibold text-slate-700">{skillsUriCount}</span>
                        {" · "}
                        Doublons collapse: <span className="font-semibold text-slate-700">{skillsUriCollapsed}</span>
                        {" · "}
                        Non mappées: <span className="font-semibold text-slate-700">{skillsUnmappedCount}</span>
                      </div>

                      {skillsDupes.length > 0 && (
                        <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-500">
                          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                            Doublons sémantiques collapse (URI)
                          </div>
                          <div className="flex flex-col gap-1">
                            {skillsDupes.map((d, idx) => (
                              <div key={`${d.label}-${idx}`} className="text-slate-600">
                                <span className="font-semibold text-slate-700">{d.label}</span>
                                {d.surfaces?.length ? (
                                  <span className="text-slate-400">
                                    {" "}← {d.surfaces.slice(0, 4).join(", ")}
                                  </span>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="grid gap-3 md:grid-cols-3">
                      {/* Validated */}
                      <div className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Validées ESCO ({validatedCount})
                            {aliasHitsCount > 0 && (
                              <span
                                title={`${aliasHitsCount} compétence(s) récupérée(s) via la table d'alias FR`}
                                className="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[9px] font-bold text-amber-700 ring-1 ring-amber-300"
                              >
                                +{aliasHitsCount} alias
                              </span>
                            )}
                          </span>
                          <button
                            onClick={() => copyToClipboard(filteredValidatedLabels)}
                            className="text-xs font-medium text-cyan-600 hover:text-cyan-800"
                            disabled={filteredValidatedLabels.length === 0}
                          >
                            Copier
                          </button>
                        </div>
                        <input
                          type="search"
                          value={validatedSearch}
                          onChange={(e) => setValidatedSearch(e.target.value)}
                          placeholder="Rechercher..."
                          className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
                        />
                        <div className="mt-2 max-h-40 overflow-y-auto text-xs text-slate-700">
                          {filteredValidatedLabels.length === 0 ? (
                            <p className="text-slate-400">Aucun résultat</p>
                          ) : (
                            <div className="flex flex-wrap gap-1">
                              {filteredValidatedLabels.map((item) => (
                                <span
                                  key={item}
                                  className="rounded-full bg-slate-100 px-2 py-0.5"
                                >
                                  {item}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        {aliasHits.length > 0 && (
                          <div className="mt-2 border-t border-slate-100 pt-2">
                            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-amber-600">
                              Via alias ({aliasHits.length})
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {aliasHits.map((h) => (
                                <span
                                  key={h.alias}
                                  title={`"${h.alias}" → ${h.label}`}
                                  className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-800 ring-1 ring-amber-200"
                                >
                                  {h.alias} → {h.label}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Ignored */}
                      <div className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Ignorées ({filteredOut})
                          </span>
                          <button
                            onClick={() => copyToClipboard(filteredIgnoredTokens)}
                            className="text-xs font-medium text-cyan-600 hover:text-cyan-800"
                            disabled={filteredIgnoredTokens.length === 0}
                          >
                            Copier
                          </button>
                        </div>
                        {filteredTokens ? (
                          <>
                            <input
                              type="search"
                              value={filteredSearch}
                              onChange={(e) => setFilteredSearch(e.target.value)}
                              placeholder="Rechercher..."
                              className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
                            />
                            <div className="mt-2 max-h-40 overflow-y-auto text-xs text-slate-700">
                              {filteredIgnoredTokens.length === 0 ? (
                                <p className="text-slate-400">Aucun résultat</p>
                              ) : (
                                <div className="flex flex-wrap gap-1">
                                  {filteredIgnoredTokens.map((item) => (
                                    <span
                                      key={item}
                                      className="rounded-full bg-slate-100 px-2 py-0.5"
                                    >
                                      {item}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </>
                        ) : (
                          <p className="mt-2 text-xs text-slate-400">
                            Liste indisponible — compte uniquement.
                          </p>
                        )}
                      </div>

                      {/* Raw */}
                      <div className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Brut détecté ({rawDetected})
                          </span>
                          <button
                            onClick={() => copyToClipboard(filteredRawTokens)}
                            className="text-xs font-medium text-cyan-600 hover:text-cyan-800"
                            disabled={filteredRawTokens.length === 0}
                          >
                            Copier
                          </button>
                        </div>
                        {rawTokens ? (
                          <>
                            <input
                              type="search"
                              value={rawSearch}
                              onChange={(e) => setRawSearch(e.target.value)}
                              placeholder="Rechercher..."
                              className="mt-2 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
                            />
                            <div className="mt-2 max-h-40 overflow-y-auto text-xs text-slate-700">
                              {filteredRawTokens.length === 0 ? (
                                <p className="text-slate-400">Aucun résultat</p>
                              ) : (
                                <div className="flex flex-wrap gap-1">
                                  {filteredRawTokens.map((item) => (
                                    <span
                                      key={item}
                                      className="rounded-full bg-slate-100 px-2 py-0.5"
                                    >
                                      {item}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </>
                        ) : (
                          <p className="mt-2 text-xs text-slate-400">
                            Liste indisponible — compte uniquement.
                          </p>
                        )}
                      </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* CTA */}
                <div className="flex justify-end pt-1">
                  <Button onClick={handleRunMatching} disabled={matchingLoading || validatedCount === 0}>
                    {matchingLoading ? "Chargement..." : "Lancer le matching →"}
                  </Button>
                </div>
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
