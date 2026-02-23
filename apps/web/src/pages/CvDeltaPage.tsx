import { useMemo, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { DevStatusCard } from "../components/DevStatusCard";
import { PageContainer } from "../components/layout/PageContainer";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/badge";
import { ErrorState } from "../components/ui/ErrorState";
import {
  runCvDelta,
  type CvDeltaResponse,
  type CvDeltaRequest,
  CvDeltaApiError,
} from "../lib/api";
import { layout, spacing, typography } from "../styles/uiTokens";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const DEFAULT_PROVIDER = "openai" as const;
const DEFAULT_MODEL = "gpt-4o-mini";

const TROUBLESHOOTING_URL =
  "https://github.com/akimgnts/elevia/blob/main/docs/START_HERE.md";

type ErrorInfo = {
  title: string;
  description: string;
  details?: string;
};

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function validateFile(file: File | null): string | null {
  if (!file) return null;
  if (file.size > MAX_FILE_BYTES) return "Fichier trop volumineux. Max 5MB.";
  const allowed = ["application/pdf", "text/plain"];
  if (!allowed.includes(file.type) && !file.name.endsWith(".pdf") && !file.name.endsWith(".txt")) {
    return "Format non supporté. Utilisez un PDF ou un TXT.";
  }
  return null;
}

export default function CvDeltaPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [withLlm, setWithLlm] = useState(false);
  const [provider, setProvider] = useState<"openai">(DEFAULT_PROVIDER);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CvDeltaResponse | null>(null);
  const [errorInfo, setErrorInfo] = useState<ErrorInfo | null>(null);
  const [showErrorDetails, setShowErrorDetails] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const canSubmit = useMemo(() => !!file && !fileError && !loading, [file, fileError, loading]);

  const handleFile = (nextFile: File | null) => {
    const error = validateFile(nextFile);
    setFile(nextFile);
    setFileError(error);
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    handleFile(nextFile);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    const nextFile = event.dataTransfer.files?.[0] ?? null;
    handleFile(nextFile);
  };

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(true);
  };

  const onDragLeave = () => {
    setDragActive(false);
  };

  const onSubmit = async () => {
    if (!file) return;
    setLoading(true);
    setErrorInfo(null);
    setShowErrorDetails(false);
    setResult(null);
    try {
      const request: CvDeltaRequest = {
        file,
        withLlm,
        provider,
        model,
      };
      const response = await runCvDelta(request);
      setResult(response);
    } catch (err) {
      if (err instanceof CvDeltaApiError) {
        if (err.status === 403 && err.details.includes("Dev tools disabled")) {
          setErrorInfo({
            title: "Dev tools désactivés",
            description: "Activez ELEVIA_DEV_TOOLS=1 côté API pour utiliser cette page.",
            details: err.details,
          });
        } else {
          setErrorInfo({
            title: "Erreur API",
            description: "La requête a échoué. Vérifiez l’API et réessayez.",
            details: err.details,
          });
        }
      } else {
        setErrorInfo({
          title: "Backend indisponible",
          description: "Impossible de joindre l’API. Vérifiez que le backend tourne.",
          details: err instanceof Error ? err.message : "Erreur inconnue",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const jsonPayload = result ? JSON.stringify(result, null, 2) : "";

  const onCopy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(jsonPayload);
  };

  const onDownload = () => {
    if (!result) return;
    const blob = new Blob([jsonPayload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `cv-delta_${new Date().toISOString().slice(0, 19)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`min-h-screen ${layout.pageBg}`}>
      <PageContainer className={spacing.pageTop}>
        <header className="mb-8">
          <p className={typography.overline}>Dev Tools</p>
          <h1 className={`mt-1 ${typography.h2}`}>CV Delta A vs A+B</h1>
          <p className={`mt-2 ${typography.body}`}>
            Compare le parsing déterministe avec l’enrichissement LLM optionnel.
          </p>
        </header>

        <DevStatusCard />

        {errorInfo && (
          <Card className="mb-6 border border-amber-200 bg-amber-50/70 p-5">
            <div className="text-sm font-semibold text-amber-900">{errorInfo.title}</div>
            <p className="mt-1 text-sm text-amber-800">{errorInfo.description}</p>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-amber-900">
              <a className="underline" href={TROUBLESHOOTING_URL} target="_blank" rel="noreferrer">
                Troubleshooting
              </a>
              {errorInfo.details && (
                <button
                  type="button"
                  className="underline"
                  onClick={() => setShowErrorDetails((prev) => !prev)}
                >
                  {showErrorDetails ? "Masquer détails" : "Afficher détails"}
                </button>
              )}
            </div>
            {showErrorDetails && errorInfo.details && (
              <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-white/70 p-3 text-xs text-amber-900">
                {errorInfo.details}
              </pre>
            )}
          </Card>
        )}

        <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <Card className="p-6">
            <h2 className="text-base font-semibold text-slate-900">Upload CV</h2>
            <p className="mt-1 text-sm text-slate-500">PDF ou TXT, 5MB max.</p>

            <div
              className={`mt-4 flex flex-col items-center justify-center rounded-2xl border border-dashed p-6 text-center transition-colors ${
                dragActive ? "border-slate-400 bg-slate-50" : "border-slate-200 bg-white"
              }`}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
            >
              <p className="text-sm text-slate-600">Glissez-déposez un fichier ou parcourez.</p>
              <label className="mt-3 inline-flex cursor-pointer items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700">
                Choisir un fichier
                <input
                  type="file"
                  accept=".pdf,.txt,application/pdf,text/plain"
                  onChange={onFileChange}
                  className="hidden"
                />
              </label>
            </div>

            {file && (
              <div className="mt-3 text-xs text-slate-500">
                {file.name} • {formatBytes(file.size)}
              </div>
            )}
            {fileError && <div className="mt-2 text-xs text-red-600">{fileError}</div>}

            <div className="mt-5">
              <div className="text-xs font-semibold text-slate-500">Mode</div>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                    !withLlm ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600"
                  }`}
                  onClick={() => setWithLlm(false)}
                >
                  A (déterministe)
                </button>
                <button
                  type="button"
                  className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                    withLlm ? "border-slate-900 bg-slate-900 text-white" : "border-slate-200 text-slate-600"
                  }`}
                  onClick={() => setWithLlm(true)}
                >
                  A+B (LLM)
                </button>
              </div>
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                Avancé
              </summary>
              <div className="mt-3 grid gap-3 text-sm text-slate-700">
                <div>
                  <label className="text-xs font-semibold text-slate-500">Provider</label>
                  <select
                    className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                    value={provider}
                    onChange={(event) => setProvider(event.target.value as "openai")}
                    disabled={!withLlm}
                  >
                    <option value="openai">openai</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-500">Model</label>
                  <input
                    className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    disabled={!withLlm}
                  />
                </div>
              </div>
            </details>

            <div className="mt-6 flex flex-wrap gap-3">
              <Button variant="primary" onClick={onSubmit} disabled={!canSubmit}>
                {loading ? "Analyse en cours..." : "Lancer la comparaison"}
              </Button>
              <Button variant="secondary" onClick={onCopy} disabled={!result}>
                Copier JSON
              </Button>
              <Button variant="secondary" onClick={onDownload} disabled={!result}>
                Télécharger JSON
              </Button>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="text-base font-semibold text-slate-900">Résultats</h2>
            <p className="mt-1 text-sm text-slate-500">Sélectionnez un fichier pour afficher la delta.</p>
            {!errorInfo && !result && !loading && (
              <div className="mt-4 text-sm text-slate-500">Aucun résultat pour le moment.</div>
            )}
            {loading && (
              <div className="mt-4 text-sm text-slate-600">Analyse en cours…</div>
            )}
            {errorInfo && !loading && (
              <div className="mt-4">
                <ErrorState description={errorInfo.description} />
              </div>
            )}
          </Card>
        </div>

        {result && (
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <Card className="p-5">
              <div className="text-xs font-semibold text-slate-500">Mode</div>
              <div className="mt-2 text-base font-semibold text-slate-900">
                {result.meta.run_mode}
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-semibold text-slate-500">Canonical</div>
              <div className="mt-2 text-base font-semibold text-slate-900">
                {result.canonical_count}
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-semibold text-slate-500">Cache</div>
              <div className="mt-2">
                <Badge variant={result.meta.cache_hit ? "good" : "default"}>
                  {result.meta.cache_hit ? "hit" : "miss"}
                </Badge>
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-semibold text-slate-500">Provider / Model</div>
              <div className="mt-2 text-sm text-slate-700">
                {result.meta.provider && result.meta.model
                  ? `${result.meta.provider} · ${result.meta.model}`
                  : "—"}
              </div>
            </Card>

            {result.meta.warning && (
              <Card className="p-5 lg:col-span-2">
                <div className="text-xs font-semibold text-amber-600">Warning</div>
                <div className="mt-2 text-sm text-amber-700">{result.meta.warning}</div>
              </Card>
            )}

            <Card className="p-6">
              <h3 className="text-sm font-semibold text-slate-900">Delta summary</h3>
              <div className="mt-4 grid gap-3 text-sm text-slate-600">
                <div>Added skills: {result.added_skills.length}</div>
                <div>Removed skills: {result.removed_skills.length}</div>
                <div>Unchanged skills: {result.unchanged_skills_count}</div>
                <div>Added ESCO: {result.added_esco.length}</div>
                <div>Removed ESCO: {result.removed_esco.length}</div>
              </div>
            </Card>

            <Card className="p-6">
              <h3 className="text-sm font-semibold text-slate-900">Added skills</h3>
              <div className="mt-4 max-h-48 overflow-auto">
                {result.added_skills.length === 0 && (
                  <p className="text-sm text-slate-500">Aucune compétence ajoutée.</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {result.added_skills.map((skill) => (
                    <Badge key={skill} variant="good">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            </Card>

            <Card className="p-6">
              <h3 className="text-sm font-semibold text-slate-900">Removed skills</h3>
              <div className="mt-4 max-h-48 overflow-auto">
                {result.removed_skills.length === 0 && (
                  <p className="text-sm text-slate-500">Aucune compétence supprimée.</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {result.removed_skills.map((skill) => (
                    <Badge key={skill} variant="low">
                      {skill}
                    </Badge>
                  ))}
                </div>
              </div>
            </Card>

            {(result.added_esco.length > 0 || result.removed_esco.length > 0) && (
              <Card className="p-6 lg:col-span-2">
                <h3 className="text-sm font-semibold text-slate-900">ESCO delta</h3>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="text-xs font-semibold text-slate-500">Added ESCO</div>
                    <ul className="mt-2 space-y-1 text-sm text-slate-600">
                      {result.added_esco.length === 0 && <li>—</li>}
                      {result.added_esco.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-slate-500">Removed ESCO</div>
                    <ul className="mt-2 space-y-1 text-sm text-slate-600">
                      {result.removed_esco.length === 0 && <li>—</li>}
                      {result.removed_esco.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </Card>
            )}

            <Card className="p-6 lg:col-span-2">
              <details>
                <summary className="cursor-pointer text-sm font-semibold text-slate-900">
                  JSON brut
                </summary>
                <pre className="mt-3 max-h-64 overflow-auto rounded-xl bg-slate-50 p-4 text-xs text-slate-700">
                  {jsonPayload}
                </pre>
              </details>
            </Card>
          </div>
        )}
      </PageContainer>
    </div>
  );
}
