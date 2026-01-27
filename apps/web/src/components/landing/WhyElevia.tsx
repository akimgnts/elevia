import { PageContainer } from "../layout/PageContainer";

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
    <section id="why-elevia" className="bg-gradient-to-b from-[#F0FDFE] via-white to-[#F9FAFB] py-16 md:py-20">
      <PageContainer>
        <div className="grid gap-10 md:grid-cols-[1.1fr_1fr]">
          <div>
            <h2 className="text-3xl font-bold text-slate-900">Pourquoi Elevia</h2>
            <p className="mt-3 text-slate-600">
              Un système calibré pour des candidatures internationales réalistes et actionnables.
            </p>
          </div>
          <div className="space-y-4">
            {points.map((point) => (
              <div
                key={point.title}
                className="rounded-2xl border border-white/40 bg-white/80 p-5 shadow-[0_4px_25px_rgba(0,0,0,0.05)] backdrop-blur-xl"
              >
                <div className="text-sm font-semibold text-slate-900">{point.title}</div>
                <p className="mt-2 text-sm text-slate-600">{point.description}</p>
              </div>
            ))}
          </div>
        </div>
      </PageContainer>
    </section>
  );
}
