import { TestimonialCard } from "../ui/TestimonialCard";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";

const testimonials = [
  {
    quote: "Elevia m'a donné une vision claire des offres à forte probabilité.",
    author: "Lina M.",
    role: "Data Analyst",
  },
  {
    quote: "Le dashboard bento est ultra lisible et agréable à utiliser.",
    author: "Thomas R.",
    role: "Product Ops",
  },
  {
    quote: "Les insights IA m'ont permis d'ajuster mon profil en 20 minutes.",
    author: "Sarah K.",
    role: "Marketing",
  },
];

export function TestimonialsSection() {
  return (
    <SectionWrapper>
      <PageContainer>
        <div className="mb-10">
          <h2 className="text-2xl font-bold text-slate-900 md:text-3xl">Ils ont relancé leur trajectoire</h2>
          <p className="mt-3 text-slate-600">Des retours d'utilisateurs qui ont retrouvé de la clarté.</p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {testimonials.map((testimonial) => (
            <TestimonialCard key={testimonial.author} {...testimonial} />
          ))}
        </div>
      </PageContainer>
    </SectionWrapper>
  );
}
