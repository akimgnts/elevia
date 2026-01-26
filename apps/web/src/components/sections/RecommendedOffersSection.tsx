import { OfferCard } from "../ui/OfferCard";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";

const offers = [
  {
    title: "Data Analyst V.I.E",
    company: "Airbus",
    location: "Montréal, Canada",
    score: 92,
    tags: ["Python", "SQL", "Power BI"],
  },
  {
    title: "Product Ops V.I.E",
    company: "Sanofi",
    location: "Berlin, Allemagne",
    score: 84,
    tags: ["Operations", "Supply", "Agile"],
  },
  {
    title: "Growth Analyst V.I.E",
    company: "BNP Paribas",
    location: "Tokyo, Japon",
    score: 78,
    tags: ["Analytics", "Market", "CRM"],
  },
];

export function RecommendedOffersSection() {
  return (
    <SectionWrapper>
      <PageContainer>
        <div className="mb-10 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 md:text-3xl">Top 3 matches</h2>
            <p className="mt-3 text-slate-600">Vos meilleures opportunités prêtes à être activées.</p>
          </div>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {offers.map((offer) => (
            <OfferCard key={offer.title} {...offer} />
          ))}
        </div>
      </PageContainer>
    </SectionWrapper>
  );
}
