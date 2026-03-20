import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import { KpiCard } from "../components/ui/KpiCard";
import { OfferCard } from "../components/ui/OfferCard";
import { BaseListingCard } from "../components/ui/BaseListingCard";
import { GlassCard } from "../components/ui/GlassCard";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { fetchInbox, type InboxItem } from "../lib/api";
import { buildMatchingProfile } from "../lib/profileMatching";
import { useProfileStore } from "../store/profileStore";
import { typography, spacing } from "../styles/uiTokens";

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
        const { profile: matchingProfile } = buildMatchingProfile(
          userProfile as Record<string, unknown>,
          profileId
        );
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
      offer.matched_skills_display && offer.matched_skills_display.length > 0
        ? `Compétences alignées: ${offer.matched_skills_display.slice(0, 3).join(", ")}`
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
      <PremiumAppShell
        eyebrow="Cockpit"
        title="Votre cockpit Elevia"
        description="Synthese, priorites et prochains mouvements a partir de votre profil."
      >
        <div className={spacing.pageTop}>
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
        </div>
      </PremiumAppShell>
    );
  }

  return (
    <PremiumAppShell
      eyebrow="Cockpit"
      title="Votre cockpit Elevia"
      description="Vue d'ensemble de vos matches, signaux marche et prochaines actions. L'objectif est la clarte, pas le bruit."
      actions={
        <>
          <Link
            to="/inbox"
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            Ouvrir l&apos;inbox
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/market-insights"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <Sparkles className="h-4 w-4" />
            Voir le marche
          </Link>
        </>
      }
    >
      <div className={spacing.pageTop}>

        {/* Error / Loading states */}
        {error && <ErrorState description={error} />}
        {loading && !error && (
          <div className="rounded-[1.5rem] border border-white/80 bg-white/70 px-5 py-4 text-sm text-slate-600 shadow-sm backdrop-blur">
            Chargement des donnees...
          </div>
        )}

        {/* Main grid: 2 columns on lg */}
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          {/* Left column */}
          <div className={`grid gap-5 md:grid-cols-2`}>
            <KpiCard
              label="Score moyen"
              value={`${averageScore}%`}
              delta={averageScore ? "+6%" : undefined}
              className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]"
            />
            <KpiCard
              label="Offres actives"
              value={`${items.length}`}
              delta={items.length ? "+12" : undefined}
              accent="lime"
              className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]"
            />

            {/* Radar card */}
            <GlassCard className="col-span-full border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <div className="flex items-center justify-between">
                <span className={typography.label}>Radar marché</span>
                <Badge variant="info">Temps réel</Badge>
              </div>
              <div className="mt-4 h-36 rounded-[1.5rem] border border-slate-100 bg-gradient-to-br from-white via-emerald-50/70 to-cyan-50/60" />
              <p className={`mt-4 ${typography.body}`}>
                Les secteurs data & supply gagnent en traction sur 3 zones.
              </p>
            </GlassCard>

            {/* Insights card */}
            <GlassCard className="col-span-full border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
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
            <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
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
            <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <span className={typography.label}>Activité récente</span>
              <ul className={`mt-4 ${spacing.stack} ${typography.body}`}>
                <li>• 3 nouvelles offres analysées (Canada, Allemagne).</li>
                <li>• Profil enrichi avec 2 compétences validées.</li>
                <li>• Relance de 2 candidatures en attente.</li>
              </ul>
            </GlassCard>
          </div>
        </div>

        {import.meta.env.DEV && (
          <section className="mt-10">
            <p className={typography.overline}>Dev tools</p>
            <Card className="mt-3 rounded-[1.5rem] border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold text-slate-900">CV Delta A vs A+B</div>
                  <div className="text-xs text-slate-500">
                    Analyse comparative du parsing et enrichissement LLM.
                  </div>
                </div>
                <Link to="/dev/cv-delta" className="text-sm font-semibold text-slate-700 underline">
                  Ouvrir
                </Link>
              </div>
            </Card>
          </section>
        )}
      </div>
    </PremiumAppShell>
  );
}
