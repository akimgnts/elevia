import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card } from "../../styles/uiTokens";

const steps = [
  {
    title: "1. Drop ton CV",
    description: "Une extraction claire, sans bruit ni perte d'information.",
  },
  {
    title: "2. Matching intelligent",
    description: "Score + raisons pour comprendre chaque recommandation.",
  },
  {
    title: "3. Plan d'action",
    description: "Priorités, formations, lettres personnalisées en un flux.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className={layout.section}>
      <PageContainer>
        <div className="text-center">
          <h2 className={typography.h2}>Comment ça marche</h2>
          <p className={`mt-3 ${typography.body}`}>
            Un parcours court et précis, pensé pour la réalité des candidatures V.I.E.
          </p>
        </div>
        <div className={`mt-10 grid md:grid-cols-3 ${layout.gridGap}`}>
          {steps.map((step) => (
            <div key={step.title} className={card.base}>
              <div className={typography.label}>{step.title}</div>
              <p className={`mt-3 ${typography.body}`}>{step.description}</p>
            </div>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
