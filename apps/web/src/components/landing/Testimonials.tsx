import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card, cardPadding } from "../../styles/uiTokens";

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
        <header className="text-center">
          <h2 className={typography.h2}>Ils nous font confiance</h2>
          <p className={`mt-3 ${typography.body} mx-auto max-w-lg`}>
            Des retours courts, concrets, et actionnables.
          </p>
        </header>
        <div className={`mt-10 grid md:grid-cols-3 ${layout.gridGap}`}>
          {testimonials.map((item) => (
            <article key={item.name} className={`${card.base} ${cardPadding.md}`}>
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-brand-cyan to-brand-lime text-sm font-semibold text-white">
                  {item.name[0]}
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                  <p className={typography.caption}>{item.role}</p>
                </div>
              </div>
              <blockquote className={`mt-4 ${typography.body} italic`}>
                "{item.quote}"
              </blockquote>
            </article>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
