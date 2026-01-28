import { MatchingCard } from "../ui/MatchingCard";
import { BaseListingCard } from "../ui/BaseListingCard";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";

export function LiveDemoSection() {
  return (
    <SectionWrapper className="bg-white/60">
      <PageContainer>
        <div className="mb-10">
          <h2 className="text-2xl font-bold text-slate-900 md:text-3xl">Démo live IA</h2>
          <p className="mt-3 text-slate-600">
            Visualisez en direct comment Elevia transforme votre CV en actions prioritaires.
          </p>
        </div>
        <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
          <MatchingCard
            score={88}
            highlights={["Compétences data alignées", "Expérience internationale validée", "Soft skills leadership"]}
          />
          <div className="space-y-4">
            <BaseListingCard
              title="Synthèse de profil"
              description="7 compétences clés validées, 3 à renforcer."
              meta="Données extraites en 45s"
            />
            <BaseListingCard
              title="Priorités d'action"
              description="Mettre à jour le portfolio + cibler 5 entreprises en Europe."
              meta="Recommandation IA"
            />
            <BaseListingCard
              title="Opportunités instantanées"
              description="3 offres V.I.E à 80%+ disponibles maintenant."
              meta="Match"
            />
          </div>
        </div>
      </PageContainer>
    </SectionWrapper>
  );
}
