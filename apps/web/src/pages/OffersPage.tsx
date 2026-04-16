import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Building2, MapPin, Search, Sparkles } from "lucide-react";
import { upsertApplication } from "../api/applications";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { fetchCatalogOffers, type OfferNormalized } from "../lib/api";
import { buildOfferPreview } from "../lib/text";
import { useProfileStore } from "../store/profileStore";

type SourceFilter = "all" | "france_travail" | "business_france";

function sourceLabel(source: OfferNormalized["source"]): string {
  if (source === "business_france") return "Business France";
  if (source === "france_travail") return "France Travail";
  return "Source inconnue";
}

function sourceTone(source: OfferNormalized["source"]): string {
  if (source === "business_france") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (source === "france_travail") return "bg-sky-50 text-sky-700 border-sky-200";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

export default function OffersPage() {
  const { userProfile } = useProfileStore();
  const [offers, setOffers] = useState<OfferNormalized[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState<string>("all");
  const [source, setSource] = useState<SourceFilter>("all");
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const [saveError, setSaveError] = useState<string | null>(null);

  const countries = useMemo(() => {
    const unique = new Set<string>();
    for (const offer of offers) {
      if (offer.country) unique.add(offer.country);
    }
    return Array.from(unique).sort();
  }, [offers]);

  useEffect(() => {
    async function loadOffers() {
      setLoading(true);
      setError(null);
      try {
        const catalog = await fetchCatalogOffers(200, "all");
        setOffers(catalog.offers);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoading(false);
      }
    }

    loadOffers();
  }, []);

  const filtered = useMemo(() => {
    return offers.filter((offer) => {
      const company = offer.company ?? "";
      const haystack = `${offer.title} ${company} ${offer.city ?? ""} ${offer.country ?? ""}`.toLowerCase();
      const matchesQuery = query.trim() === "" || haystack.includes(query.trim().toLowerCase());
      const matchesCountry = country === "all" || offer.country === country;
      const matchesSource = source === "all" || offer.source === source;
      return matchesQuery && matchesCountry && matchesSource;
    });
  }, [offers, query, country, source]);

  async function handleTrackOffer(offerId: string) {
    setSaveError(null);
    setSavingIds((prev) => new Set(prev).add(offerId));
    try {
      await upsertApplication({
        offer_id: offerId,
        status: "saved",
        source: "manual",
      });
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Impossible d'ajouter l'offre au suivi");
    } finally {
      setSavingIds((prev) => {
        const next = new Set(prev);
        next.delete(offerId);
        return next;
      });
    }
  }

  return (
    <PremiumAppShell
      eyebrow="Catalogue"
      title="Consulter les offres avant meme d'utiliser l'outil"
      description="Cette page montre qu'il existe deja des offres reelles et consultables. L'analyse du CV sert ensuite a dire lesquelles mer itent vraiment ton energie."
      actions={
        <>
          <Link
            to={userProfile ? "/inbox" : "/analyze"}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            {userProfile ? "Voir mes offres compatibles" : "Analyser mon CV"}
            <ArrowRight className="h-4 w-4" />
          </Link>
          <Link
            to="/market-insights"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <Sparkles className="h-4 w-4" />
            Explorer le marche
          </Link>
        </>
      }
      contentClassName="max-w-7xl"
    >
      <div className="grid gap-6">
        <section className="border-b border-slate-200/80 pb-6">
          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Rôle de cette page</div>
              <div className="mt-2 text-lg font-semibold text-slate-950">Le catalogue complet, avant le tri par pertinence.</div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Ici vous parcourez tout le catalogue. L&apos;inbox sert ensuite à comparer ce catalogue à votre profil actif et à prioriser ce qui mérite votre énergie.
              </p>
              <div className="mt-4 flex flex-wrap gap-5 text-sm text-slate-600">
                <span><span className="font-semibold text-slate-950">{offers.length}</span> offres chargées</span>
                <span><span className="font-semibold text-slate-950">{filtered.length}</span> offres visibles après filtres</span>
                <span>Explorer d&apos;abord, qualifier ensuite</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 lg:justify-end">
              <Link
                to={userProfile ? "/inbox" : "/analyze"}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                {userProfile ? "Comparer à mon profil" : "Créer mon profil"}
              </Link>
              <Link
                to="/applications"
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                Ouvrir le suivi
              </Link>
            </div>
          </div>
        </section>

        <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-4 shadow-sm">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1.6fr)_220px_220px]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Rechercher par intitule, entreprise, ville ou pays"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-10 py-2.5 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
              />
            </div>

            <select
              value={country}
              onChange={(event) => setCountry(event.target.value)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
            >
              <option value="all">Tous les pays</option>
              {countries.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

            <select
              value={source}
              onChange={(event) => setSource(event.target.value as SourceFilter)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
            >
              <option value="all">Toutes les sources</option>
              <option value="france_travail">France Travail</option>
              <option value="business_france">Business France</option>
            </select>
          </div>
        </section>

        {error && <ErrorState description={error} />}
        {saveError && <ErrorState description={saveError} />}
        {loading && !error && (
          <div className="rounded-[1.75rem] border border-white/80 bg-white/80 px-6 py-8 text-sm text-slate-500 shadow-sm">
            Chargement des offres...
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <EmptyState title="Aucune offre trouvee" description="Ajustez vos filtres ou reessayez." />
        )}

        {!loading && !error && filtered.length > 0 && (
          <section className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((offer) => {
              const location = [offer.city, offer.country].filter(Boolean).join(", ");
              const preview = buildOfferPreview(offer.display_description, offer.description);
              const isSaving = savingIds.has(offer.id);
              return (
                <article
                  key={offer.id}
                  className="group block rounded-[1.75rem] border border-slate-200/80 bg-white/95 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.08)] transition-all hover:-translate-y-0.5 hover:shadow-[0_24px_55px_rgba(15,23,42,0.12)]"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${sourceTone(offer.source)}`}>
                          {sourceLabel(offer.source)}
                        </span>
                      </div>
                      <Link to={`/offers/${encodeURIComponent(offer.id)}`} className="line-clamp-2 text-lg font-semibold leading-snug text-slate-950 hover:underline">
                        {offer.title || "Offre"}
                      </Link>
                      <div className="mt-2 flex items-center gap-2 text-sm text-slate-600">
                        <Building2 className="h-4 w-4 text-slate-400" />
                        <span className="line-clamp-1">{offer.company || "Entreprise"}</span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
                        <MapPin className="h-4 w-4 text-slate-400" />
                        <span className="line-clamp-1">{location || "Localisation a preciser"}</span>
                      </div>
                    </div>

                    <div className="shrink-0 rounded-2xl border border-sky-100 bg-sky-50 px-3 py-3 text-center">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-700">
                        Offre
                      </div>
                      <div className="mt-1 text-sm font-semibold text-slate-900">Reelle</div>
                    </div>
                  </div>

                  <div className="mt-4 rounded-[1.25rem] border border-sky-100 bg-sky-50/80 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">
                      Ce que vous pouvez verifier
                    </div>
                    <div className="mt-2 text-sm leading-relaxed text-slate-700 line-clamp-4">
                      {preview || "Description indisponible."}
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => handleTrackOffer(offer.id)}
                      disabled={isSaving}
                      className="rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                    >
                      {isSaving ? "Ajout…" : "Ajouter au suivi"}
                    </button>
                    <Link
                      to={userProfile ? "/inbox" : "/analyze"}
                      className="inline-flex items-center gap-1 text-sm font-semibold text-slate-900"
                    >
                      {userProfile ? "Comparer à mon profil" : "Créer mon profil"}
                      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                    </Link>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </PremiumAppShell>
  );
}
