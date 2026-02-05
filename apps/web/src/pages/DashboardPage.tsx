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
import { fetchInbox, type InboxItem } from "../lib/api";
import { buildMatchingProfile } from "../lib/profileMatching";
import { useProfileStore } from "../store/profileStore";
import { typography, spacing, layout } from "../styles/uiTokens";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { userProfile, profileHash } = useProfileStore();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userProfile) return;

    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const profileId = profileHash ?? "anonymous";
        if (import.meta.env.DEV) {
          console.info("[dashboard] profile_id", profileId);
        }
        const matchingProfile = buildMatchingProfile(userProfile as Record<string, unknown>, profileId);
        const inbox = await fetchInbox(matchingProfile, profileId, 0, 60);
        setItems(inbox.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [userProfile]);

  const averageScore =
    items.length > 0
      ? Math.round(items.reduce((sum, r) => sum + r.score, 0) / items.length)
      : 0;

  const topMatches = items.slice(0, 3).map((offer) => {
    const location = offer.country || offer.city || "Localisation à préciser";
    const preview =
      offer.matched_skills && offer.matched_skills.length > 0
        ? `Compétences alignées: ${offer.matched_skills.slice(0, 3).join(", ")}`
        : "Aucune compétence détectée en commun.";
    return {
      id: offer.offer_id,
      title: offer.title || "Offre",
      company: offer.company || "Entreprise",
      location,
      preview,
      score: Math.round(offer.score),
      tags: ["V.I.E"],
    };
  });

  if (!userProfile) {
    return (
      <div className={`min-h-screen ${layout.pageBg}`}>
        <PageContainer className={spacing.pageTop}>
          <EmptyState
            title="Aucun profil détecté"
            description="Analysez votre CV pour activer le matching réel."
            actionLabel="Analyser mon CV"
            onAction={() => navigate("/analyze")}
          />
          <div className="mt-4 text-center">
            <Link to="/analyze" className={`${typography.body} underline`}>
              Aller à l'analyse
            </Link>
          </div>
        </PageContainer>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${layout.pageBg}`}>
      <PageContainer className={spacing.pageTop}>
        {/* Page header */}
        <header className="mb-10">
          <p className={typography.overline}>Dashboard</p>
          <h1 className={`mt-1 ${typography.h2}`}>Votre cockpit Elevia</h1>
          <p className={`mt-2 ${typography.body}`}>
            Synthèse, tendances marché et offres prioritaires.
          </p>
        </header>

        {/* Error / Loading states */}
        {error && <ErrorState description={error} />}
        {loading && !error && (
          <p className={typography.body}>Chargement des données…</p>
        )}

        {/* Main grid: 2 columns on lg */}
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          {/* Left column */}
          <div className={`grid gap-5 md:grid-cols-2`}>
            <KpiCard
              label="Score moyen"
              value={`${averageScore}%`}
              delta={averageScore ? "+6%" : undefined}
            />
            <KpiCard
              label="Offres actives"
              value={`${items.length}`}
              delta={items.length ? "+12" : undefined}
              accent="lime"
            />

            {/* Radar card */}
            <GlassCard className="col-span-full p-5">
              <div className="flex items-center justify-between">
                <span className={typography.label}>Radar marché</span>
                <Badge variant="info">Temps réel</Badge>
              </div>
              <div className="mt-4 h-36 rounded-card bg-gradient-to-br from-slate-50 to-slate-100" />
              <p className={`mt-4 ${typography.body}`}>
                Les secteurs data & supply gagnent en traction sur 3 zones.
              </p>
            </GlassCard>

            {/* Insights card */}
            <GlassCard className="col-span-full p-5">
              <span className={typography.label}>Insights</span>
              <div className={`mt-4 ${spacing.stack}`}>
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

          {/* Right column */}
          <div className="space-y-5">
            {/* Top matches */}
            <GlassCard className="p-5">
              <span className={typography.label}>Top matches</span>
              <div className={`mt-4 ${spacing.stack}`}>
                {topMatches.map((offer) => (
                  <OfferCard
                    key={offer.id}
                    title={offer.title}
                    company={offer.company}
                    location={offer.location}
                    preview={offer.preview}
                    score={offer.score}
                    tags={offer.tags}
                    href={`/offers/${encodeURIComponent(offer.id)}`}
                  />
                ))}
              </div>
            </GlassCard>

            {/* Recent activity */}
            <GlassCard className="p-5">
              <span className={typography.label}>Activité récente</span>
              <ul className={`mt-4 ${spacing.stack} ${typography.body}`}>
                <li>• 3 nouvelles offres analysées (Canada, Allemagne).</li>
                <li>• Profil enrichi avec 2 compétences validées.</li>
                <li>• Relance de 2 candidatures en attente.</li>
              </ul>
            </GlassCard>
          </div>
        </div>
      </PageContainer>
    </div>
  );
}
