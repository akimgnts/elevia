import { useEffect, useMemo, useState } from "react";
import { Building2, Calendar, MapPin, Search } from "lucide-react";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { fetchCatalogOffers, type OfferNormalized, type OffersCatalogResponse } from "../lib/api";
import { buildOfferPreview } from "../lib/text";

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

function formatDate(value: string | null): string | null {
  if (!value) return null;
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

export default function ExplorePage() {
  const [catalog, setCatalog] = useState<OffersCatalogResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState<string>("all");
  const [source, setSource] = useState<SourceFilter>("all");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchCatalogOffers(300, "all");
        setCatalog(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const offers = catalog?.offers ?? [];

  const countries = useMemo(() => {
    const unique = new Set<string>();
    for (const offer of offers) {
      if (offer.country) unique.add(offer.country);
    }
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [offers]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return offers.filter((offer) => {
      const haystack = [
        offer.title,
        offer.company ?? "",
        offer.city ?? "",
        offer.country ?? "",
        offer.display_description ?? "",
        offer.description ?? "",
      ]
        .join(" ")
        .toLowerCase();

      const matchesQuery = normalizedQuery === "" || haystack.includes(normalizedQuery);
      const matchesCountry = country === "all" || offer.country === country;
      const matchesSource = source === "all" || offer.source === source;
      return matchesQuery && matchesCountry && matchesSource;
    });
  }, [offers, query, country, source]);

  return (
    <PremiumAppShell
      eyebrow="Explorer"
      title="Toutes les offres disponibles"
      description="Une vue simple pour parcourir les offres deja presentes dans la base, sans analyse de profil, sans score et sans matching."
      contentClassName="max-w-7xl"
    >
      <div className="grid gap-6">
        <section className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Offres visibles</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{filtered.length}</div>
            <div className="mt-2 text-sm text-slate-500">resultats apres recherche et filtres</div>
          </div>
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Offres chargees</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{offers.length}</div>
            <div className="mt-2 text-sm text-slate-500">catalogue charge pour cette page</div>
          </div>
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Pays detectes</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{countries.length}</div>
            <div className="mt-2 text-sm text-slate-500">zones couvertes dans les offres chargees</div>
          </div>
        </section>

        <section className="rounded-[1.75rem] border border-white/80 bg-white/80 p-4 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1.6fr)_220px_220px]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                placeholder="Rechercher par intitule, entreprise, ville, pays ou texte"
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

        {loading && !error && (
          <div className="rounded-[1.75rem] border border-white/80 bg-white/80 px-6 py-8 text-sm text-slate-500 shadow-sm">
            Chargement des offres...
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <EmptyState title="Aucune offre trouvee" description="Ajustez la recherche ou les filtres." />
        )}

        {!loading && !error && filtered.length > 0 && (
          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {filtered.map((offer) => {
              const location = [offer.city, offer.country].filter(Boolean).join(", ");
              const publicationDate = formatDate(offer.publication_date);
              const preview = buildOfferPreview(offer.display_description, offer.description);

              return (
                <article
                  key={offer.id}
                  className="rounded-[1.75rem] border border-slate-200/80 bg-white/95 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.08)]"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${sourceTone(offer.source)}`}>
                          {sourceLabel(offer.source)}
                        </span>
                        {offer.contract_duration && (
                          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                            {offer.contract_duration} mois
                          </span>
                        )}
                      </div>

                      <h2 className="line-clamp-2 text-lg font-semibold leading-snug text-slate-950">
                        {offer.title || "Offre"}
                      </h2>

                      <div className="mt-3 space-y-2 text-sm text-slate-600">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-slate-400" />
                          <span className="line-clamp-1">{offer.company || "Entreprise non renseignee"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4 text-slate-400" />
                          <span className="line-clamp-1">{location || "Localisation non renseignee"}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-slate-400" />
                          <span>{publicationDate || "Date de publication non renseignee"}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 rounded-[1.25rem] border border-slate-200 bg-slate-50/80 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Apercu
                    </div>
                    <div className="mt-2 line-clamp-5 text-sm leading-relaxed text-slate-700">
                      {preview || "Description indisponible."}
                    </div>
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
