import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card, cardPadding } from "../../styles/uiTokens";

const points = [
  {
    title: "Matching transparent",
    description: "Des raisons claires pour chaque recommandation, sans boîte noire.",
  },
  {
    title: "V.I.E first",
    description: "Aligné avec les contraintes V.I.E et les attentes Business France.",
  },
  {
    title: "Action immédiate",
    description: "Priorités, lettres et formations dans un seul flux continu.",
  },
];

export function WhyElevia() {
  return (
    <section id="why-elevia" className={layout.section}>
      <PageContainer>
        <div className="grid items-start gap-10 md:grid-cols-[1.1fr_1fr]">
          <header>
            <h2 className={typography.h2}>Pourquoi Elevia</h2>
            <p className={`mt-3 ${typography.lead}`}>
              Un système calibré pour des candidatures internationales réalistes et actionnables.
            </p>
          </header>
          <div className="space-y-3">
            {points.map((point) => (
              <article key={point.title} className={`${card.subtle} ${cardPadding.sm}`}>
                <h3 className="text-sm font-semibold text-slate-900">{point.title}</h3>
                <p className={`mt-1.5 ${typography.body}`}>{point.description}</p>
              </article>
            ))}
          </div>
        </div>
      </PageContainer>
    </section>
  );
}
