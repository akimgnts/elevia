import { useParams } from "react-router-dom";
import { PageContainer } from "../components/layout/PageContainer";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { GlassCard } from "../components/ui/GlassCard";
import { Progress } from "../components/ui/Progress";

export default function OfferDetailPage() {
  const { id } = useParams();

  return (
    <div className="min-h-screen bg-slate-50">
      <PageContainer className="pt-10 pb-16">
        <div className="mb-6">
          <div className="text-sm font-semibold text-slate-500">Offre {id ?? "#"}</div>
          <h1 className="text-3xl font-bold text-slate-900">Data Analyst V.I.E</h1>
          <p className="mt-2 text-slate-600">Airbus · Montréal, Canada</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <GlassCard className="p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold text-slate-700">Résumé</div>
              <Badge variant="good">82% match</Badge>
            </div>
            <p className="mt-4 text-sm text-slate-600">
              Mission data orientée pilotage KPI, reporting supply chain et dashboarding exécutif.
            </p>
            <div className="mt-6 space-y-3 text-sm text-slate-600">
              <div>• Contrat V.I.E de 12 mois.</div>
              <div>• Outils : Python, SQL, Power BI.</div>
              <div>• Équipe multiculturelle, rythme hybride.</div>
            </div>
          </GlassCard>

          <GlassCard className="p-6">
            <div className="text-sm font-semibold text-slate-700">Votre matching</div>
            <div className="mt-4">
              <Progress value={82} />
              <div className="mt-2 text-xs text-slate-500">82% aligné avec votre profil.</div>
            </div>
            <div className="mt-6 space-y-2 text-sm text-slate-600">
              <div>• Compétences fortes : Python, Analytics.</div>
              <div>• À renforcer : Data storytelling.</div>
            </div>
            <div className="mt-6 flex flex-col gap-3">
              <Button variant="primary">Postuler</Button>
              <Button variant="outline">Sauvegarder</Button>
            </div>
          </GlassCard>
        </div>
      </PageContainer>
    </div>
  );
}
