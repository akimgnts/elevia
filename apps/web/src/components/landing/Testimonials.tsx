import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card } from "../../styles/uiTokens";

const testimonials = [
  {
    name: "Lina M.",
    role: "Data Analyst",
    quote: "Le matching est clair et les actions sont concrètes. J'ai gagné du temps.",
  },
  {
    name: "Thomas R.",
    role: "Product Ops",
    quote: "La structure V.I.E est enfin respectée. Tout est plus simple à suivre.",
  },
  {
    name: "Sarah K.",
    role: "Marketing",
    quote: "Les recommandations de formation sont directement utiles pour candidater.",
  },
];

export function Testimonials() {
  return (
    <section className={layout.section}>
      <PageContainer>
        <div className="text-center">
          <h2 className={typography.h2}>Ils nous font confiance</h2>
          <p className={`mt-3 ${typography.body}`}>Des retours courts, concrets, et actionnables.</p>
        </div>
        <div className={`mt-10 grid md:grid-cols-3 ${layout.gridGap}`}>
          {testimonials.map((item) => (
            <div key={item.name} className={card.base}>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-[#06B6D4] to-[#22C55E] text-sm font-semibold text-white">
                  {item.name[0]}
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">{item.name}</div>
                  <div className={typography.caption}>{item.role}</div>
                </div>
              </div>
              <p className={`mt-4 ${typography.body} italic`}>"{item.quote}"</p>
            </div>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
