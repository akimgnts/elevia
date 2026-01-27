import { PageContainer } from "../layout/PageContainer";

const steps = [
  {
    title: "1. Drop ton CV",
    description: "Une extraction claire, sans bruit ni perte d’information.",
  },
  {
    title: "2. Matching intelligent",
    description: "Score + raisons pour comprendre chaque recommandation.",
  },
  {
    title: "3. Plan d’action",
    description: "Priorités, formations, lettres personnalisées en un flux.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-gradient-to-b from-[#F0FDFE] via-white to-[#ECFDF5] py-16 md:py-20">
      <PageContainer>
        <div className="text-center">
          <h2 className="text-3xl font-bold text-slate-900">Comment ça marche</h2>
          <p className="mt-3 text-slate-600">
            Un parcours court et précis, pensé pour la réalité des candidatures V.I.E.
          </p>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {steps.map((step) => (
            <div
              key={step.title}
              className="rounded-2xl border border-white/40 bg-white/80 p-6 shadow-[0_4px_25px_rgba(0,0,0,0.05)] backdrop-blur-xl"
            >
              <div className="text-sm font-semibold text-slate-500">{step.title}</div>
              <p className="mt-3 text-slate-600">{step.description}</p>
            </div>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
