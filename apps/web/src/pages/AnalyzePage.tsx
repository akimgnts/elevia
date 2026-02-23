import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ingestCv, parseFile, type ParseFileResponse } from "../lib/api";
import { useProfileStore } from "../store/profileStore";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { PageContainer } from "../components/layout/PageContainer";
import { DevStatusCard } from "../components/DevStatusCard";

const PLACEHOLDER_CV = `Jean Dupont\nData Analyst - 3 ans d'expérience\n\nFORMATION\nMaster Data Science, École Polytechnique (2020)\n\nEXPÉRIENCE\n- Analyste BI chez Acme Corp (2020-2023)\n  Python, SQL, Power BI, Tableau\n- Stage Data Engineer chez StartupXYZ (2019)\n  ETL, dbt, Airflow\n\nCOMPÉTENCES\n- Python, SQL, R\n- Power BI, Tableau, Looker\n- Excel avancé, VBA\n- Jira, Confluence\n\nLANGUES\n- Français (natif)\n- Anglais (C1)\n- Espagnol (B2)`;

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

            {/* Results */}
            {parseResult && (
              <div className="mt-6 space-y-4 border-t border-slate-100 pt-5">
                <div className="flex flex-wrap items-center gap-3">
                  <div>
                    <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-bold text-emerald-700">
                      {parseResult.validated_skills} compétence{parseResult.validated_skills !== 1 ? "s" : ""} validée{parseResult.validated_skills !== 1 ? "s" : ""} pour le matching
                    </span>
                    {parseResult.filtered_out > 0 && (
                      <div className="mt-1 text-xs text-slate-400 pl-1">
                        {parseResult.filtered_out} élément{parseResult.filtered_out !== 1 ? "s" : ""} ignoré{parseResult.filtered_out !== 1 ? "s" : ""} (non reconnu{parseResult.filtered_out !== 1 ? "s" : ""} par ESCO)
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-slate-400">
                    {parseResult.extracted_text_length} caractères · {parseResult.filename}
                  </span>
                </div>

                {parseResult.warnings.length > 0 && (
                  <div className="rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">
                    {parseResult.warnings.join(" · ")}
                  </div>
                )}

                {/* Skill pills */}
                <div className="flex flex-wrap gap-2">
                  {parseResult.skills_canonical.slice(0, 30).map((skill) => (
                    <span
                      key={skill}
                      className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                    >
                      {skill}
                    </span>
                  ))}
                  {parseResult.skills_canonical.length > 30 && (
                    <span className="rounded-full bg-slate-200 px-3 py-1 text-xs text-slate-500">
                      +{parseResult.skills_canonical.length - 30} de plus
                    </span>
                  )}
                </div>

                <div className="flex justify-end pt-2">
                  <Button onClick={handleRunMatching} disabled={matchingLoading}>
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
    </div>
  );
}
