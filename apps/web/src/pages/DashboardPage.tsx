import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Compass, Globe2, Layers3, Target } from "lucide-react";
import { KpiCard } from "../components/ui/KpiCard";
import { OfferCard } from "../components/ui/OfferCard";
import { GlassCard } from "../components/ui/GlassCard";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { fetchCatalogOffers, fetchInbox } from "../lib/api";
import { buildMatchingProfile } from "../lib/profileMatching";
import { normalizeAndSortInboxItems, type NormalizedInboxItem } from "../lib/inboxItems";
import { useProfileStore } from "../store/profileStore";

type CockpitSummary = {
  totalOffers: number;
  matchedOffers: number;
  strongMatches: number;
  averageScore: number;
  topCountries: string[];
  topSectors: string[];
};

function takeTopLabels(values: Array<string | null | undefined>, limit: number): string[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    const cleaned = (value || "").trim();
    if (!cleaned) continue;
    counts.set(cleaned, (counts.get(cleaned) || 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([label]) => label);
}

function buildCockpitSummary(items: NormalizedInboxItem[], totalOffers: number): CockpitSummary {
  const matchedOffers = items.length;
  const strongMatches = items.filter((item) => item.score >= 75).length;
  const averageScore =
    matchedOffers > 0
      ? Math.round(items.reduce((sum, item) => sum + item.score, 0) / matchedOffers)
      : 0;

  const topCountries = takeTopLabels(
    items.map((item) => item.country || item.city || null),
    3,
  );
  const topSectors = takeTopLabels(
    items.flatMap((item) => item.offer_intelligence?.dominant_domains?.slice(0, 1) || [item.offer_cluster || null]),
    3,
  );

  return {
    totalOffers,
    matchedOffers,
    strongMatches,
    averageScore,
    topCountries,
    topSectors,
  };
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { userProfile, profileHash } = useProfileStore();
  const [items, setItems] = useState<NormalizedInboxItem[]>([]);
  const [totalOffers, setTotalOffers] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const careerProfile = (userProfile as { career_profile?: { experiences?: Array<{ skill_links?: unknown[]; canonical_skills_used?: unknown[]; tools?: unknown[]; skills?: unknown[] }> } } | null)?.career_profile;
  const structuredExperiences = Array.isArray(careerProfile?.experiences) ? careerProfile.experiences : [];
  const structuredExperienceCount = structuredExperiences.filter(
    (experience) => Array.isArray(experience.skill_links) && experience.skill_links.length > 0,
  ).length;
  const structuredLinkCount = structuredExperiences.reduce(
    (sum, experience) => sum + (Array.isArray(experience.skill_links) ? experience.skill_links.length : 0),
    0,
  );
  const hasStructuredProfile = structuredExperienceCount > 0;

  useEffect(() => {
    if (!userProfile) return;

    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const profileId = profileHash ?? "anonymous";
        const { profile: matchingProfile } = buildMatchingProfile(
          userProfile as Record<string, unknown>,
          profileId,
        );
        const [catalog, inbox] = await Promise.all([
          fetchCatalogOffers(1, "all"),
          fetchInbox(matchingProfile, profileId, 0, 60),
        ]);
        setTotalOffers(catalog.meta.total_available || catalog.offers.length || 0);
        setItems(normalizeAndSortInboxItems(inbox.items));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [profileHash, userProfile]);

  const summary = useMemo(() => buildCockpitSummary(items, totalOffers), [items, totalOffers]);

  const topMatches = items.slice(0, 3).map((offer) => {
    const location = offer.country || offer.city || "Localisation à préciser";
    const preview =
      offer.offer_intelligence?.offer_summary ||
      offer.explanation.summary_reason ||
      "Offre disponible pour revue.";
    return {
      id: offer.offer_id,
      title: offer.title || "Offre",
      company: offer.company || "Entreprise",
      location,
      preview,
      score: Math.round(offer.score),
      tags: [offer.offer_id.startsWith("BF-") ? "V.I.E" : "Offre"],
    };
  });

  if (!userProfile) {
    return (
      <PremiumAppShell
        eyebrow="Cockpit"
        title="Votre cockpit Elevia"
        description="Le cockpit lit un profil déjà structuré. Il synthétise ensuite les offres, les priorités et le suivi."
      >
        <div className="pt-6">
          <EmptyState
            title="Aucun profil détecté"
            description="Commencez par structurer votre profil. Le cockpit viendra ensuite synthétiser vos offres et vos priorités."
            actionLabel="Ouvrir le profil"
            onAction={() => navigate("/profile")}
          />
        </div>
      </PremiumAppShell>
    );
  }

  return (
    <PremiumAppShell
      eyebrow="Cockpit"
      title="Votre cockpit Elevia"
      description="Votre profil structuré pilote ce cockpit, l'inbox et le suivi des candidatures."
      actions={
        <>
          <Link
            to={hasStructuredProfile ? "/inbox" : "/profile"}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            {hasStructuredProfile ? "Voir mes offres pertinentes" : "Structurer mon profil"}
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/profile"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Ouvrir le profil
          </Link>
          <Link
            to="/applications"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Candidatures
          </Link>
        </>
      }
    >
      <div className="grid gap-6 pt-2">
        {error && <ErrorState description={error} />}
        {loading && !error && (
          <div className="rounded-[1.5rem] border border-white/80 bg-white/70 px-5 py-4 text-sm text-slate-600 shadow-sm backdrop-blur">
            Chargement du cockpit…
          </div>
        )}

        <section className="border-b border-slate-200/80 pb-6">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Profil actif
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-lg font-semibold text-slate-950">
                {typeof (userProfile as { target_title?: string } | null)?.target_title === "string"
                  ? (userProfile as { target_title?: string }).target_title
                  : "Profil prêt pour le matching"}
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Ce profil sert de source de vérité pour vos matchs, vos préparations de CV et votre suivi.
              </p>
            </div>
            <Link
              to="/profile"
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Ouvrir le profil
            </Link>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700">
              {structuredExperienceCount} expérience{structuredExperienceCount > 1 ? "s" : ""} structurée{structuredExperienceCount > 1 ? "s" : ""}
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700">
              {structuredLinkCount} skill_link{structuredLinkCount > 1 ? "s" : ""}
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 font-medium text-slate-700">
              {hasStructuredProfile ? "Cockpit prêt" : "Profil à structurer"}
            </span>
          </div>
        </section>

        {!hasStructuredProfile && (
          <div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900 shadow-sm">
            Votre cockpit peut être consulté, mais il sera plus utile après la structuration du profil. Commencez par le profil pour relier expériences, skills et outils.
          </div>
        )}

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <KpiCard label="Offres totales" value={`${summary.totalOffers}`} accent="cyan" className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]" />
          <KpiCard label="Offres compatibles" value={`${summary.matchedOffers}`} className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]" />
          <KpiCard label="Matches solides" value={`${summary.strongMatches}`} accent="lime" className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]" />
          <KpiCard label="Score moyen" value={`${summary.averageScore}%`} className="border-white/80 bg-white/80 shadow-[0_12px_40px_rgba(15,23,42,0.08)]" />
          <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Secteurs et pays clés</div>
            <div className="mt-3 flex flex-wrap gap-2 text-sm text-slate-700">
              {(summary.topCountries.length > 0 ? summary.topCountries : ["À venir"]).map((country) => (
                <span key={country} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                  {country}
                </span>
              ))}
              {(summary.topSectors.length > 0 ? summary.topSectors : ["À venir"]).map((sector) => (
                <span key={sector} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                  {sector}
                </span>
              ))}
            </div>
          </GlassCard>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Lecture du cockpit
                </div>
                <h2 className="mt-2 text-xl font-semibold text-slate-950">
                  {hasStructuredProfile ? "Où agir maintenant" : "Structurez d'abord le profil"}
                </h2>
              </div>
              <Compass className="h-5 w-5 text-slate-400" />
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Target className="h-4 w-4 text-emerald-600" /> Priorité</div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {hasStructuredProfile
                    ? summary.strongMatches > 0
                      ? `${summary.strongMatches} offre${summary.strongMatches > 1 ? "s" : ""} méritent une action rapide depuis l'inbox.`
                      : "Aucun fort match pour l'instant. Passez par le profil pour ajuster vos signaux avant d'ouvrir l'inbox."
                    : "Le cockpit reste lisible, mais la hiérarchie produit commence par le profil. Structurez vos expériences avant d'ouvrir l'inbox."}
                </p>
              </div>
              <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Layers3 className="h-4 w-4 text-indigo-600" /> Secteurs</div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {(summary.topSectors.length > 0 ? summary.topSectors : ["Aucun secteur dominant"]).join(" · ")}
                </p>
              </div>
              <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Globe2 className="h-4 w-4 text-sky-600" /> Pays</div>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {(summary.topCountries.length > 0 ? summary.topCountries : ["Aucun pays dominant"]).join(" · ")}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-5 shadow-sm">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Suite logique</div>
            <div className="mt-4 space-y-3 text-sm text-slate-600">
              <p><span className="font-semibold text-slate-900">1.</span> Vérifier et structurer le profil.</p>
              <p><span className="font-semibold text-slate-900">2.</span> Ouvrir l'inbox pour lire les offres compatibles.</p>
              <p><span className="font-semibold text-slate-900">3.</span> Préparer CV et lettre dans Candidatures.</p>
            </div>
          </div>
        </section>

        <GlassCard className="border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Meilleurs matchs</div>
              <h2 className="mt-2 text-xl font-semibold text-slate-950">À envoyer vers l'inbox ou le suivi</h2>
            </div>
            <Link to="/inbox" className="text-sm font-semibold text-slate-700 underline underline-offset-4">
              Ouvrir l'inbox
            </Link>
          </div>
          {topMatches.length === 0 ? (
            <div className="mt-4 rounded-[1.25rem] border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              Aucun match à afficher pour l'instant.
            </div>
          ) : (
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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
          )}
        </GlassCard>
      </div>
    </PremiumAppShell>
  );
}
