import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, MapPin, Calendar, Building2 } from "lucide-react";
import { PageContainer } from "../components/layout/PageContainer";
import { Badge } from "../components/ui/badge";
import { GlassCard } from "../components/ui/GlassCard";
import { ErrorState } from "../components/ui/ErrorState";
import { fetchCatalogOffers, fetchSampleOffers } from "../lib/api";
import { cleanFullText, buildMissions, buildOfferPreview } from "../lib/text";
import { typography, spacing, layout } from "../styles/uiTokens";

interface OfferData {
  id: string;
  title: string;
  description?: string;
  display_description?: string;
  company?: string | null;
  company_name?: string | null;
  city?: string | null;
  country?: string | null;
  location_label?: string | null;
  publication_date?: string | null;
  start_date?: string | null;
  contract_duration?: number | null;
  source?: string;
  skills?: string[];
  required_skills?: string[];
  languages?: string[];
  required_languages?: string[];
  is_vie?: boolean;
}

export default function OfferDetailPage() {
  const { offerId } = useParams<{ offerId: string }>();
  const [offer, setOffer] = useState<OfferData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!offerId) return;

    async function loadOffer() {
      setLoading(true);
      setError(null);
      try {
        // TODO: replace with GET /offers/:id when backend endpoint exists
        // For now, fetch both sources and find by id
        const [catalog, sample] = await Promise.allSettled([
          fetchCatalogOffers(500, "all"),
          fetchSampleOffers(300),
        ]);

        let found: OfferData | undefined;

        if (catalog.status === "fulfilled") {
          found = catalog.value.offers.find((o) => o.id === offerId) as OfferData | undefined;
        }

        if (!found && sample.status === "fulfilled") {
          const sampleOffers = sample.value.offers as Array<Record<string, unknown>>;
          const match = sampleOffers.find(
            (o) => o.id === offerId || o.offer_id === offerId
          );
          if (match) {
            found = {
              id: (match.id as string) || (match.offer_id as string) || offerId!,
              title: (match.title as string) || "Offre",
              description: match.description as string | undefined,
              company: (match.company as string) || (match.company_name as string) || null,
              country: match.country as string | null,
              location_label: match.location_label as string | null,
              skills: (match.skills || match.required_skills) as string[] | undefined,
              languages: (match.languages || match.required_languages) as string[] | undefined,
              is_vie: match.is_vie as boolean | undefined,
            };
          }
        }

        if (found) {
          setOffer(found);
        } else {
          setError(`Offre « ${offerId} » introuvable.`);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoading(false);
      }
    }

    loadOffer();
  }, [offerId]);

  if (loading) {
    return (
      <div className={`min-h-screen ${layout.pageBg}`}>
        <PageContainer className={spacing.pageTop}>
          <p className={typography.body}>Chargement de l'offre…</p>
        </PageContainer>
      </div>
    );
  }

  if (error || !offer) {
    return (
      <div className={`min-h-screen ${layout.pageBg}`}>
        <PageContainer className={spacing.pageTop}>
          <Link to="/offres" className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
            <ArrowLeft className="h-4 w-4" />
            Retour aux offres
          </Link>
          <ErrorState description={error || "Offre introuvable"} />
        </PageContainer>
      </div>
    );
  }

  const companyName = offer.company || offer.company_name || null;
  const location = offer.location_label || [offer.city, offer.country].filter(Boolean).join(", ") || null;
  const skills = offer.skills || offer.required_skills || [];
  const languages = offer.languages || offer.required_languages || [];
  const rawDesc = offer.display_description || offer.description || "";
  const fullText = rawDesc ? cleanFullText(rawDesc) : null;
  const missions = buildMissions(offer.display_description, offer.description);
  const preview = buildOfferPreview(offer.display_description, offer.description);
  const pubDate = offer.publication_date
    ? new Date(offer.publication_date).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
    : null;

  return (
    <div className={`min-h-screen ${layout.pageBg}`}>
      <PageContainer className={spacing.pageTop}>
        {/* Back link */}
        <Link to="/offres" className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700">
          <ArrowLeft className="h-4 w-4" />
          Retour aux offres
        </Link>

        {/* Header */}
        <header className="mb-8">
          <h1 className={typography.h2}>{offer.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-600">
            {companyName && (
              <span className="flex items-center gap-1.5">
                <Building2 className="h-4 w-4 text-slate-400" />
                {companyName}
              </span>
            )}
            {location && (
              <span className="flex items-center gap-1.5">
                <MapPin className="h-4 w-4 text-slate-400" />
                {location}
              </span>
            )}
            {pubDate && (
              <span className="flex items-center gap-1.5">
                <Calendar className="h-4 w-4 text-slate-400" />
                {pubDate}
              </span>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {offer.is_vie && <Badge variant="info">V.I.E</Badge>}
            {offer.source && offer.source !== "unknown" && (
              <Badge variant="default">
                {offer.source === "business_france" ? "Business France" : offer.source === "france_travail" ? "France Travail" : offer.source}
              </Badge>
            )}
            {offer.contract_duration && (
              <Badge variant="default">{offer.contract_duration} mois</Badge>
            )}
          </div>
        </header>

        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          {/* Left column — content */}
          <div className="space-y-6">
            {/* Missions section */}
            {(missions.intro || missions.bullets.length > 0) && (
              <GlassCard className="p-6">
                <h2 className={typography.label}>Missions</h2>
                {missions.intro && (
                  <p className={`mt-3 ${typography.body}`}>{missions.intro}</p>
                )}
                {missions.bullets.length > 0 && (
                  <ul className={`mt-3 space-y-2 ${typography.body}`}>
                    {missions.bullets.map((bullet, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="mt-1 text-brand-cyan">•</span>
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </GlassCard>
            )}

            {/* Full description */}
            {fullText && (
              <GlassCard className="p-6">
                <h2 className={typography.label}>Description complète</h2>
                <div className={`mt-3 whitespace-pre-line ${typography.body}`}>
                  {fullText}
                </div>
              </GlassCard>
            )}

            {/* Fallback if no description at all */}
            {!fullText && !missions.intro && missions.bullets.length === 0 && preview && (
              <GlassCard className="p-6">
                <h2 className={typography.label}>Résumé</h2>
                <p className={`mt-3 ${typography.body}`}>{preview}</p>
              </GlassCard>
            )}
          </div>

          {/* Right column — metadata */}
          <div className="space-y-5">
            {/* Skills */}
            {skills.length > 0 && (
              <GlassCard className="p-5">
                <h2 className={typography.label}>Compétences requises</h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  {skills.map((skill) => (
                    <Badge key={skill} variant="default">
                      {skill.replace(/_/g, " ")}
                    </Badge>
                  ))}
                </div>
              </GlassCard>
            )}

            {/* Languages */}
            {languages.length > 0 && (
              <GlassCard className="p-5">
                <h2 className={typography.label}>Langues</h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  {languages.map((lang) => (
                    <Badge key={lang} variant="default">
                      {lang}
                    </Badge>
                  ))}
                </div>
              </GlassCard>
            )}

            {/* Quick info */}
            <GlassCard className="p-5">
              <h2 className={typography.label}>Informations</h2>
              <dl className={`mt-3 space-y-2 ${typography.body}`}>
                {companyName && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Entreprise</dt>
                    <dd className="font-medium text-slate-900">{companyName}</dd>
                  </div>
                )}
                {location && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Lieu</dt>
                    <dd className="font-medium text-slate-900">{location}</dd>
                  </div>
                )}
                {offer.contract_duration && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Durée</dt>
                    <dd className="font-medium text-slate-900">{offer.contract_duration} mois</dd>
                  </div>
                )}
                {offer.start_date && (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Début</dt>
                    <dd className="font-medium text-slate-900">
                      {new Date(offer.start_date).toLocaleDateString("fr-FR")}
                    </dd>
                  </div>
                )}
              </dl>
            </GlassCard>
          </div>
        </div>
      </PageContainer>
    </div>
  );
}
