import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Briefcase } from "lucide-react";
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

function formatTopBreakdown(
  items: InboxItem[],
  getLabel: (item: InboxItem) => string | null | undefined,
  emptyLabel: string
) {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const label = getLabel(item)?.trim();
    if (!label) return;
    counts.set(label, (counts.get(label) ?? 0) + 1);
  });

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([label, count]) => ({
      title: label,
      description: `${count} offre${count > 1 ? "s" : ""}`,
    }))
    .concat(
      counts.size > 0
        ? []
        : [
            {
              title: emptyLabel,
              description: "Les donnees remonteront des que l'inbox sera chargee.",
            },
          ]
    );
}

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
  }, [userProfile, profileHash]);

  const averageScore =
    items.length > 0
      ? Math.round(items.reduce((sum, r) => sum + r.score, 0) / items.length)
      : 0;
  const totalOffers = items.length;
  const matchedOffers = items.filter((item) => Math.round(item.score) >= 65).length;

  const topSectors = formatTopBreakdown(
    items,
    (offer) => offer.offer_intelligence?.dominant_domains?.[0] ?? null,
    "Aucun secteur dominant"
  );
  const topCountries = formatTopBreakdown(
    items,
    (offer) => offer.country,
    "Aucun pays dominant"
  );

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
    return <Navigate to="/profile" replace />;
  }

  return (
    <PremiumAppShell
      eyebrow="Cockpit"
      title="Votre cockpit apres profil"
      description="Votre profil est pret. Commencez ici pour cadrer le volume d'offres, les zones de traction et ouvrir ensuite l'inbox avec les bonnes priorites."
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
            to="/candidatures"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <Briefcase className="h-4 w-4" />
            Voir le suivi
          </Link>
        </>
      }
    >
      <div className={spacing.pageTop}>
        {error && <ErrorState description={error} />}
        {loading && !error && (
          <div className="rounded-[1.5rem] border border-white/80 bg-white/70 px-5 py-4 text-sm text-slate-600 shadow-sm backdrop-blur">
            Chargement des donnees...
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.95fr)]">
          <div className="space-y-5">
            <div className="grid gap-5 md:grid-cols-3">
              <KpiCard
                label="Total offres"
                value={`${totalOffers}`}
                className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]"
              />
              <KpiCard
                label="Offres matchees"
                value={`${matchedOffers}`}
                accent="lime"
                className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]"
              />
              <KpiCard
                label="Score moyen"
                value={`${averageScore}%`}
                className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]"
              />
            </div>

            <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <div className="flex items-center justify-between">
                <span className={typography.label}>Vue d'ensemble avant inbox</span>
                <Badge variant="info">Flux profil &rarr; inbox</Badge>
              </div>
              <p className={`mt-4 ${typography.body}`}>
                Le cockpit synthétise l'inbox issue de votre profil: volume exploitable, concentration sectorielle et zones geographiques avant de passer a la revue offre par offre.
              </p>
            </GlassCard>

            <div className="grid gap-5 lg:grid-cols-2">
              <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
                <span className={typography.label}>Top secteurs</span>
                <div className={`mt-4 ${spacing.stack}`}>
                  {topSectors.map((sector) => (
                    <BaseListingCard
                      key={sector.title}
                      title={sector.title}
                      description={sector.description}
                    />
                  ))}
                </div>
              </GlassCard>

              <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
                <span className={typography.label}>Top pays</span>
                <div className={`mt-4 ${spacing.stack}`}>
                  {topCountries.map((country) => (
                    <BaseListingCard
                      key={country.title}
                      title={country.title}
                      description={country.description}
                    />
                  ))}
                </div>
              </GlassCard>
            </div>

            {import.meta.env.DEV && (
              <section>
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

          <div className="space-y-5 xl:sticky xl:top-28 xl:self-start">
            <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <span className={typography.label}>Top matches</span>
              {topMatches.length > 0 ? (
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
              ) : (
                <div className="mt-4">
                  <EmptyState
                    title="Aucune offre analysee pour l'instant"
                    description="Ouvrez l'inbox quand les premiers matches seront disponibles."
                    actionLabel="Aller a l'inbox"
                    onAction={() => navigate("/inbox")}
                  />
                </div>
              )}
            </GlassCard>

            <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
              <span className={typography.label}>Prochaine etape</span>
              <ul className={`mt-4 ${spacing.stack} ${typography.body}`}>
                <li>• Ouvrez l&apos;inbox pour lire les offres une par une.</li>
                <li>• Envoyez les bonnes opportunites vers le suivi des candidatures.</li>
                <li>• Revenez ici pour reprendre une vue synthese apres vos arbitrages.</li>
              </ul>
            </GlassCard>
          </div>
        </div>
      </div>
    </PremiumAppShell>
  );
}
