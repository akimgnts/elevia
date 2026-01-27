import { PageContainer } from "../layout/PageContainer";

const testimonials = [
  {
    name: "Lina M.",
    role: "Data Analyst",
    quote: "Le matching est clair et les actions sont concrètes. J’ai gagné du temps." ,
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
    <section className="bg-gradient-to-b from-[#F9FAFB] via-white to-[#F0FDFE] py-16 md:py-20">
      <PageContainer>
        <div className="text-center">
          <h2 className="text-3xl font-bold text-slate-900">Ils nous font confiance</h2>
          <p className="mt-3 text-slate-600">Des retours courts, concrets, et actionnables.</p>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {testimonials.map((item) => (
            <div
              key={item.name}
              className="rounded-2xl border border-white/40 bg-white/80 p-6 shadow-[0_4px_25px_rgba(0,0,0,0.05)] backdrop-blur-xl"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-r from-[#06B6D4] to-[#22C55E] text-sm font-semibold text-white">
                  {item.name[0]}
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-900">{item.name}</div>
                  <div className="text-xs text-slate-500">{item.role}</div>
                </div>
              </div>
              <p className="mt-4 text-sm text-slate-600">“{item.quote}”</p>
            </div>
          ))}
        </div>
      </PageContainer>
    </section>
  );
}
