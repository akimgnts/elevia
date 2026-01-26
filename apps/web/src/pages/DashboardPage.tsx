import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageContainer } from "../components/layout/PageContainer";
import { KpiCard } from "../components/ui/KpiCard";
import { OfferCard } from "../components/ui/OfferCard";
import { BaseListingCard } from "../components/ui/BaseListingCard";
import { GlassCard } from "../components/ui/GlassCard";
import { Badge } from "../components/ui/Badge";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { fetchCatalogOffers, runMatch, type MatchResponse, type OfferNormalized } from "../lib/api";
import { useProfileStore } from "../store/profileStore";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { userProfile } = useProfileStore();
  const [offers, setOffers] = useState<OfferNormalized[]>([]);
  const [matchResponse, setMatchResponse] = useState<MatchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userProfile) return;

    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const catalog = await fetchCatalogOffers(200, "all");
        setOffers(catalog.offers);
        const match = await runMatch(userProfile, catalog.offers);
        setMatchResponse(match);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [userProfile]);

  const offersMap = useMemo(() => {
    const map = new Map<string, OfferNormalized>();
    for (const offer of offers) {
      map.set(offer.id, offer);
    }
    return map;
  }, [offers]);

  const results = matchResponse?.results ?? [];
  const averageScore =
    results.length > 0
      ? Math.round(results.reduce((sum, r) => sum + r.score, 0) / results.length)
      : 0;

  const topMatches = results.slice(0, 3).map((result) => {
    const offer = offersMap.get(result.offer_id);
    const location = [offer?.city, offer?.country].filter(Boolean).join(", ");
    return {
      id: result.offer_id,
      title: offer?.title || "Offre",
      company: offer?.company || "Entreprise",
      location: location || "Localisation à préciser",
      score: Math.round(result.score),
      tags: [
        offer?.source === "business_france"
          ? "Business France"
          : offer?.source === "france_travail"
            ? "France Travail"
            : "Source inconnue",
      ].filter(Boolean),
    };
  });

  if (!userProfile) {
    return (
      <div className="min-h-screen bg-slate-50">
        <PageContainer className="pt-16 pb-16">
          <EmptyState
            title="Aucun profil détecté"
            description="Analysez votre CV pour activer le matching réel."
            actionLabel="Analyser mon CV"
            onAction={() => navigate("/analyze")}
          />
          <div className="mt-4 text-center text-sm text-slate-500">
            <Link to="/analyze" className="underline">
              Aller à l’analyse
            </Link>
          </div>
        </PageContainer>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <PageContainer className="pt-10 pb-16">
        <div className="mb-8">
          <div className="text-sm font-semibold text-slate-500">Dashboard</div>
          <h1 className="text-3xl font-bold text-slate-900">Votre cockpit Elevia</h1>
          <p className="mt-2 text-slate-600">
            Synthèse IA, tendances marché et offres prioritaires.
          </p>
        </div>

        {error && <ErrorState description={error} />}
        {loading && !error && (
          <div className="text-sm text-slate-500">Chargement des données…</div>
        )}

        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div className="grid gap-6 md:grid-cols-2">
            <KpiCard
              label="Score moyen"
              value={`${averageScore}%`}
              delta={averageScore ? "+6%" : undefined}
            />
            <KpiCard
              label="Offres actives"
              value={`${matchResponse?.received_offers ?? 0}`}
              delta={matchResponse?.received_offers ? "+12" : undefined}
              accent="lime"
            />
            <GlassCard className="col-span-full p-6">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-slate-700">Radar marché</div>
                <Badge variant="info">Temps réel</Badge>
              </div>
              <div className="mt-4 h-40 rounded-xl bg-gradient-to-br from-cyan-50 to-lime-50" />
              <p className="mt-4 text-sm text-slate-600">
                Les secteurs data & supply gagnent en traction sur 3 zones.
              </p>
            </GlassCard>
            <GlassCard className="col-span-full p-6">
              <div className="text-sm font-semibold text-slate-700">Insights IA</div>
              <div className="mt-4 space-y-3">
                <BaseListingCard
                  title="Compétences à renforcer"
                  description="Data storytelling, stakeholder management."
                />
                <BaseListingCard
                  title="Next actions"
                  description="Cibler 5 entreprises en Allemagne cette semaine."
                />
              </div>
            </GlassCard>
          </div>

          <div className="space-y-6">
            <GlassCard className="p-6">
              <div className="text-sm font-semibold text-slate-700">Top matches</div>
              <div className="mt-4 space-y-4">
                {topMatches.map((offer) => (
                  <OfferCard
                    key={offer.id}
                    title={offer.title}
                    company={offer.company}
                    location={offer.location}
                    score={offer.score}
                    tags={offer.tags}
                  />
                ))}
              </div>
            </GlassCard>
            <GlassCard className="p-6">
              <div className="text-sm font-semibold text-slate-700">Activité récente</div>
              <div className="mt-4 space-y-3 text-sm text-slate-600">
                <div>• 3 nouvelles offres analysées (Canada, Allemagne).</div>
                <div>• Profil enrichi avec 2 compétences validées.</div>
                <div>• Relance de 2 candidatures en attente.</div>
              </div>
            </GlassCard>
          </div>
        </div>
      </PageContainer>
    </div>
  );
}
