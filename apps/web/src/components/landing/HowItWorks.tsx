import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card, cardPadding } from "../../styles/uiTokens";

const steps = [
  {
    step: "01",
    title: "Drop ton CV",
    description: "Une extraction claire, sans bruit ni perte d'information.",
  },
  {
    step: "02",
    title: "Matching intelligent",
    description: "Score + raisons pour comprendre chaque recommandation.",
  },
  {
    step: "03",
    title: "Plan d'action",
    description: "Priorités, formations, lettres personnalisées en un flux.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className={layout.section}>
      <PageContainer>
        <header className="text-center">
          <h2 className={typography.h2}>Comment ça marche</h2>
          <p className={`mt-3 ${typography.body} mx-auto max-w-lg`}>
            Un parcours court et précis, pensé pour la réalité des candidatures V.I.E.
          </p>
        </header>
        <div className={`mt-10 grid md:grid-cols-3 ${layout.gridGap}`}>
          {steps.map((step) => (
            <article key={step.step} className={`${card.base} ${cardPadding.md}`}>
              <span className="text-xs font-semibold text-brand-cyan">{step.step}</span>
              <h3 className="mt-2 text-sm font-semibold text-slate-900">{step.title}</h3>
              <p className={`mt-2 ${typography.body}`}>{step.description}</p>
            </article>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
