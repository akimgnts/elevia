import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card } from "../../styles/uiTokens";

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
        <div className="grid gap-10 md:grid-cols-[1.1fr_1fr]">
          <div>
            <h2 className={typography.h2}>Pourquoi Elevia</h2>
            <p className={`mt-3 ${typography.lead}`}>
              Un système calibré pour des candidatures internationales réalistes et actionnables.
            </p>
          </div>
          <div className="space-y-4">
            {points.map((point) => (
              <div key={point.title} className={card.subtle}>
                <div className="text-sm font-semibold text-slate-900">{point.title}</div>
                <p className={`mt-2 ${typography.body}`}>{point.description}</p>
              </div>
            ))}
          </div>
        </div>
      </PageContainer>
    </section>
  );
}
