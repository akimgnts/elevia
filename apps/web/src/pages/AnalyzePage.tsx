import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ingestCv } from "../lib/api";
import { useProfileStore } from "../store/profileStore";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { PageContainer } from "../components/layout/PageContainer";

const PLACEHOLDER_CV = `Jean Dupont\nData Analyst - 3 ans d'expérience\n\nFORMATION\nMaster Data Science, École Polytechnique (2020)\n\nEXPÉRIENCE\n- Analyste BI chez Acme Corp (2020-2023)\n  Python, SQL, Power BI, Tableau\n- Stage Data Engineer chez StartupXYZ (2019)\n  ETL, dbt, Airflow\n\nCOMPÉTENCES\n- Python, SQL, R\n- Power BI, Tableau, Looker\n- Excel avancé, VBA\n- Jira, Confluence\n\nLANGUES\n- Français (natif)\n- Anglais (C1)\n- Espagnol (B2)`;

export default function AnalyzePage() {
  const navigate = useNavigate();
  const { setIngestResult } = useProfileStore();
  const [cvText, setCvText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!cvText.trim()) {
      setError("Colle le texte de ton CV avant de continuer.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const profile = await ingestCv(cvText);
      await setIngestResult(profile);
      navigate("/profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <PageContainer className="pt-12 pb-16">
        <div className="mb-8">
          <div className="text-sm font-semibold text-slate-500">Analyse IA</div>
          <h1 className="text-3xl font-bold text-slate-900">Déposez votre CV</h1>
          <p className="mt-2 text-slate-600">
            Nous analysons vos compétences, expériences et préférences pour activer le matching.
          </p>
        </div>

        <GlassCard className="p-6">
          <label className="text-sm font-semibold text-slate-700">Texte du CV</label>
          <textarea
            value={cvText}
            onChange={(e) => setCvText(e.target.value)}
            placeholder={PLACEHOLDER_CV}
            disabled={loading}
            className="mt-3 h-64 w-full resize-y rounded-xl border border-slate-200 bg-white/90 p-4 text-sm text-slate-700 shadow-sm outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
          />
          {error && (
            <div className="mt-4 rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-600">
              {error}
            </div>
          )}
          <div className="mt-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <span className="text-xs text-slate-500">
              Aucun fichier n'est importé. Le texte reste sous votre contrôle.
            </span>
            <Button onClick={handleSubmit} disabled={loading}>
              {loading ? "Analyse en cours..." : "Trouver mes offres"}
            </Button>
          </div>
        </GlassCard>
      </PageContainer>
    </div>
  );
}
