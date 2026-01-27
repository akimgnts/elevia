import { Link } from "react-router-dom";
import { PageContainer } from "../layout/PageContainer";

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
    <section id="pricing" className="bg-gradient-to-b from-[#F0FDFE] via-white to-[#F9FAFB] py-16 md:py-20">
      <PageContainer>
        <div className="text-center">
          <h2 className="text-3xl font-bold text-slate-900">Tarifs clairs</h2>
          <p className="mt-3 text-slate-600">Choisis le rythme qui te convient.</p>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-2xl border border-white/40 bg-white/80 p-6 shadow-[0_4px_25px_rgba(0,0,0,0.05)] backdrop-blur-xl ${
                plan.highlight ? "shadow-[0_8px_40px_rgba(6,182,212,0.20)]" : ""
              }`}
            >
              <div className="text-sm font-semibold text-slate-500">{plan.name}</div>
              <div className="mt-2 text-2xl font-bold text-slate-900">{plan.price}</div>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                {plan.features.map((feature) => (
                  <li key={feature}>• {feature}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 rounded-3xl border border-white/40 bg-white/80 p-8 text-center shadow-[0_4px_25px_rgba(0,0,0,0.05)] backdrop-blur-xl">
          <h3 className="text-2xl font-bold text-slate-900">Drop ton CV maintenant</h3>
          <p className="mt-2 text-slate-600">
            Lance l’analyse et récupère tes meilleures recommandations.
          </p>
          <div className="mt-6 flex justify-center">
            <Link
              to="/analyse"
              className="rounded-xl bg-gradient-to-r from-[#06B6D4] to-[#22C55E] px-8 py-3 text-sm font-semibold text-white shadow-md"
            >
              Drop ton CV maintenant
            </Link>
          </div>
        </div>
      </PageContainer>
    </section>
  );
}
