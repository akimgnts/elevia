import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ingestCv, parseFile, type ParseFileResponse, type SkillGroupItem } from "../lib/api";
import { useProfileStore } from "../store/profileStore";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { PageContainer } from "../components/layout/PageContainer";
import { DevStatusCard } from "../components/DevStatusCard";

const PLACEHOLDER_CV = `Jean Dupont\nData Analyst - 3 ans d'expérience\n\nFORMATION\nMaster Data Science, École Polytechnique (2020)\n\nEXPÉRIENCE\n- Analyste BI chez Acme Corp (2020-2023)\n  Python, SQL, Power BI, Tableau\n- Stage Data Engineer chez StartupXYZ (2019)\n  ETL, dbt, Airflow\n\nCOMPÉTENCES\n- Python, SQL, R\n- Power BI, Tableau, Looker\n- Excel avancé, VBA\n- Jira, Confluence\n\nLANGUES\n- Français (natif)\n- Anglais (C1)\n- Espagnol (B2)`;

// Groups shown first when deriving key skills
const KEY_SKILL_PRIORITY = ["Numérique", "Aptitudes & Compétences"];
const MAX_KEY_SKILLS = 12;

/** Deterministic: pick up to MAX_KEY_SKILLS labels, priority groups first. */
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

  // Priority pass
  for (const name of KEY_SKILL_PRIORITY) {
    const g = groups.find((g) => g.group === name);
    if (g) addFromGroup(g);
  }

  // Remaining groups (stable: sorted by group name)
  const others = groups
    .filter((g) => !KEY_SKILL_PRIORITY.includes(g.group))
    .sort((a, b) => a.group.localeCompare(b.group, "fr"));
  for (const g of others) addFromGroup(g);

  return result;
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

  // ── Results UI state ─────────────────────────────────────────────────────────
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [showFullList, setShowFullList] = useState(false);
  const [fullListSearch, setFullListSearch] = useState("");

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
    setShowFullList(false);
    setFullListSearch("");
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
    setShowFullList(false);
    setExpandedGroups(new Set());
    try {
      const result = await parseFile(selectedFile);
      setParseResult(result);
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
  const validatedCount = parseResult?.validated_skills ?? 0;
  const filteredOut = parseResult?.filtered_out ?? 0;
  const rawDetected = parseResult?.raw_detected ?? 0;

  const keySkills = deriveKeySkills(skillGroups);

  const autreGroup = skillGroups.find((g) => g.group === "Autres");

  const filteredFullList = allLabels.filter((s) =>
    fullListSearch.trim() === "" ||
    s.toLowerCase().includes(fullListSearch.trim().toLowerCase())
  );

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

                {/* (C) Health counters */}
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
                    <span className="text-slate-400">
                      Autres&nbsp;
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                        {autreGroup.count}
                      </span>
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

                {/* Zero-state: no ESCO skills found */}
                {validatedCount === 0 ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-center">
                    <p className="font-semibold text-slate-700">Aucune compétence ESCO reconnue</p>
                    <p className="mt-1 text-sm text-slate-500">
                      Le fichier a peut-être un contenu difficile à extraire.
                      Essayez de coller le texte dans l'onglet "Coller le texte".
                    </p>
                  </div>
                ) : (
                  <>
                    {/* (A) Key skills */}
                    <div>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-semibold text-slate-700">
                          Compétences clés&nbsp;
                          <span className="font-normal text-slate-400">
                            {keySkills.length}&nbsp;/&nbsp;{validatedCount}
                          </span>
                        </span>
                        {/* (B) Voir tout */}
                        <button
                          onClick={() => { setShowFullList(true); setFullListSearch(""); }}
                          className="text-xs font-medium text-cyan-600 hover:text-cyan-800 hover:underline"
                        >
                          Voir toutes les compétences ({validatedCount})
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {keySkills.map((skill) => (
                          <span
                            key={skill}
                            className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-800 ring-1 ring-cyan-200"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* (D) Grouped skills — collapsible */}
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

      {/* ── Full-list modal (B) ────────────────────────────────────────────────── */}
      {showFullList && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowFullList(false); }}
        >
          <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl bg-white shadow-xl">
            {/* Modal header */}
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <span className="font-semibold text-slate-800">
                Toutes les compétences ({allLabels.length})
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
              {filteredFullList.length === 0 ? (
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
              )}
            </div>

            {/* Footer count */}
            <div className="border-t border-slate-100 px-5 py-3 text-xs text-slate-400">
              {filteredFullList.length} compétence{filteredFullList.length !== 1 ? "s" : ""} affichée{filteredFullList.length !== 1 ? "s" : ""}
              {fullListSearch && ` sur ${allLabels.length}`}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
