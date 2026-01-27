import { Link } from "react-router-dom";
import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card, button } from "../../styles/uiTokens";
import { cn } from "../../lib/cn";

const plans = [
  {
    name: "Starter",
    price: "Gratuit",
    features: ["Analyse CV", "3 matchs", "Lettre IA"],
  },
  {
    name: "Pro",
    price: "29€/mois",
    features: ["Matching illimité", "Formations", "Suivi candidatures"],
    highlight: true,
  },
  {
    name: "Premium",
    price: "59€/mois",
    features: ["Coaching", "Priorité IA", "Support dédié"],
  },
];

export function PricingSection() {
  return (
    <section id="pricing" className={layout.section}>
      <PageContainer>
        <div className="text-center">
          <h2 className={typography.h2}>Tarifs clairs</h2>
          <p className={`mt-3 ${typography.body}`}>Choisis le rythme qui te convient.</p>
        </div>
        <div className={`mt-10 grid md:grid-cols-3 ${layout.gridGap}`}>
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={cn(
                card.base,
                plan.highlight && "ring-2 ring-cyan-500/20 shadow-md"
              )}
            >
              <div className={typography.label}>{plan.name}</div>
              <div className="mt-2 text-2xl font-semibold text-slate-900">{plan.price}</div>
              <ul className={`mt-4 space-y-2 ${typography.body}`}>
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <span className="text-emerald-500">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className={`mt-12 text-center ${card.hero}`}>
          <h3 className={typography.h3}>Drop ton CV maintenant</h3>
          <p className={`mt-2 ${typography.body}`}>
            Lance l'analyse et récupère tes meilleures recommandations.
          </p>
          <div className="mt-6 flex justify-center">
            <Link to="/analyze" className={button.primary}>
              Drop ton CV maintenant
            </Link>
          </div>
        </div>
      </PageContainer>
    </section>
  );
}
