import { useEffect, useMemo, useState } from "react";
import { PageContainer } from "../components/layout/PageContainer";
import { OfferCard } from "../components/ui/OfferCard";
import { Input } from "../components/ui/Input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/Select";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { fetchCatalogOffers, type OfferNormalized } from "../lib/api";

export default function OffersPage() {
  const [offers, setOffers] = useState<OfferNormalized[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState<string | undefined>(undefined);

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
      const matchesQuery =
        offer.title.toLowerCase().includes(query.toLowerCase()) ||
        company.toLowerCase().includes(query.toLowerCase());
      const matchesCountry = !country || offer.country === country;
      return matchesQuery && matchesCountry;
    });
  }, [offers, query, country]);

  return (
    <div className="min-h-screen bg-slate-50">
      <PageContainer className="pt-10 pb-16">
        <div className="mb-8">
          <div className="text-sm font-semibold text-slate-500">Offres V.I.E</div>
          <h1 className="text-3xl font-bold text-slate-900">Explorez les meilleures opportunités</h1>
          <p className="mt-2 text-slate-600">Filtres avancés et matching pour accélérer votre sélection.</p>
        </div>

        <div className="mb-8 grid gap-4 rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-soft md:grid-cols-[2fr_1fr]">
          <Input
            placeholder="Rechercher par intitulé ou entreprise"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Select onValueChange={setCountry}>
            <SelectTrigger>
              <SelectValue placeholder="Pays" />
            </SelectTrigger>
            <SelectContent>
              {countries.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {error && <ErrorState description={error} />}
        {loading && !error && (
          <div className="text-sm text-slate-500">Chargement des offres…</div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <EmptyState title="Aucune offre trouvée" description="Ajustez vos filtres ou réessayez." />
        )}

        <div className="grid gap-6 md:grid-cols-2">
          {filtered.map((offer) => {
            const location = [offer.city, offer.country].filter(Boolean).join(", ");
            return (
              <OfferCard
                key={offer.id}
                title={offer.title || "Offre"}
                company={offer.company || "Entreprise"}
                location={location || "Localisation à préciser"}
                score={undefined}
                tags={[
                  offer.source === "business_france"
                    ? "Business France"
                    : offer.source === "france_travail"
                      ? "France Travail"
                      : "Source inconnue",
                ]}
              />
            );
          })}
        </div>
      </PageContainer>
    </div>
  );
}
