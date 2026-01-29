import { Button } from "../ui/Button";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";

export function FinalCTASection() {
  return (
    <SectionWrapper>
      <PageContainer>
        <div className="rounded-3xl border border-slate-200 bg-white px-8 py-12 text-center shadow-soft">
          <h2 className="text-2xl font-bold text-slate-900 md:text-3xl">Prêt à activer votre prochaine mission ?</h2>
          <p className="mt-3 text-slate-600">
            Commencez gratuitement et recevez vos premières recommandations en moins de 3 minutes.
          </p>
          <div className="mt-6 flex justify-center gap-4">
            <Button variant="primary">Commencer gratuitement</Button>
            <Button variant="outline">Parler à un conseiller</Button>
          </div>
        </div>
      </PageContainer>
    </SectionWrapper>
  );
}
