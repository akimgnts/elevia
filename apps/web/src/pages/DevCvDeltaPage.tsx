import { useState } from "react";
import type { ChangeEvent } from "react";
import { PageContainer } from "../components/layout/PageContainer";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/badge";
import { ErrorState } from "../components/ui/ErrorState";
import { runCvDelta, type CvDeltaResponse } from "../lib/api/cvDelta";
import { layout, spacing, typography } from "../styles/uiTokens";

const MAX_FILE_BYTES = 5 * 1024 * 1024;

type FileState = {
  file: File | null;
  error: string | null;
};

export default function DevCvDeltaPage() {
  const [fileState, setFileState] = useState<FileState>({ file: null, error: null });
  const [withLlm, setWithLlm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CvDeltaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (!file) {
      setFileState({ file: null, error: null });
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setFileState({ file: null, error: "Fichier trop volumineux. Max 5MB." });
      return;
    }
    setFileState({ file, error: null });
  };

  const onSubmit = async () => {
    if (!fileState.file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await runCvDelta({
        file: fileState.file,
        withLlm,
        provider: "openai",
        model: "gpt-4o-mini",
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
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

        <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <Card className="p-6">
            <h2 className="text-base font-semibold text-slate-900">Upload CV</h2>
            <p className="mt-1 text-sm text-slate-500">PDF ou TXT, 5MB max.</p>

            <div className="mt-4">
              <input
                type="file"
                accept=".pdf,.txt,application/pdf,text/plain"
                onChange={onFileChange}
                className="block w-full text-sm text-slate-700 file:mr-4 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-200"
              />
              {fileState.file && (
                <div className="mt-2 text-xs text-slate-500">
                  {fileState.file.name} • {Math.round(fileState.file.size / 1024)} KB
                </div>
              )}
              {fileState.error && (
                <div className="mt-2 text-xs text-red-600">{fileState.error}</div>
              )}
            </div>

            <div className="mt-5 flex items-center gap-3">
              <input
                id="with-llm"
                type="checkbox"
                checked={withLlm}
                onChange={(event) => setWithLlm(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900"
              />
              <label htmlFor="with-llm" className="text-sm text-slate-700">
                Enable LLM enrichment
              </label>
            </div>

            <div className="mt-6">
              <Button
                variant="primary"
                onClick={onSubmit}
                disabled={!fileState.file || !!fileState.error || loading}
              >
                {loading ? "Analyse en cours..." : "Lancer la comparaison"}
              </Button>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="text-base font-semibold text-slate-900">Résultats</h2>
            <p className="mt-1 text-sm text-slate-500">Sélectionnez un fichier pour afficher la delta.</p>
            {error && (
              <div className="mt-4">
                <ErrorState description={error} />
              </div>
            )}
            {!error && !result && (
              <div className="mt-4 text-sm text-slate-500">
                Aucun résultat pour le moment.
              </div>
            )}
          </Card>
        </div>

        {result && (
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <Card className="p-6">
              <h3 className="text-sm font-semibold text-slate-900">Meta</h3>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Badge variant="info">Mode {result.meta.run_mode}</Badge>
                {result.meta.provider && result.meta.model && (
                  <Badge variant="default">{result.meta.provider} · {result.meta.model}</Badge>
                )}
                <Badge variant={result.meta.cache_hit ? "good" : "default"}>
                  Cache {result.meta.cache_hit ? "hit" : "miss"}
                </Badge>
                <Badge variant="default">Canonical {result.canonical_count}</Badge>
              </div>
              {result.meta.warning && (
                <p className="mt-3 text-xs text-amber-700">
                  {result.meta.warning}
                </p>
              )}
            </Card>

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

            {result.added_esco.length > 0 && (
              <Card className="p-6 lg:col-span-2">
                <h3 className="text-sm font-semibold text-slate-900">Added ESCO</h3>
                <div className="mt-4 max-h-48 overflow-auto">
                  <ul className="space-y-1 text-sm text-slate-600">
                    {result.added_esco.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </Card>
            )}

            {result.removed_esco.length > 0 && (
              <Card className="p-6 lg:col-span-2">
                <h3 className="text-sm font-semibold text-slate-900">Removed ESCO</h3>
                <div className="mt-4 max-h-48 overflow-auto">
                  <ul className="space-y-1 text-sm text-slate-600">
                    {result.removed_esco.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </Card>
            )}
          </div>
        )}
      </PageContainer>
    </div>
  );
}
