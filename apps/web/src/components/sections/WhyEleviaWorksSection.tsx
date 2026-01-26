import { BarChart3, Globe2, ShieldCheck, Sparkles } from "lucide-react";
import { GlassCard } from "../ui/GlassCard";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";

const blocks = [
  {
    icon: Sparkles,
    title: "Matching V9",
    description: "Algorithmes hybrides IA + scoring pour un matching précis et explicable.",
  },
  {
    icon: Globe2,
    title: "Couverture mondiale",
    description: "Suivez le marché V.I.E dans 80+ pays avec un radar en temps réel.",
  },
  {
    icon: BarChart3,
    title: "Bento insights",
    description: "Tableaux de bord clairs et actionnables, inspirés des leaders SaaS.",
  },
  {
    icon: ShieldCheck,
    title: "Sécurité & contrôle",
    description: "Vous validez chaque donnée avant qu'elle ne soit utilisée.",
  },
];

export function WhyEleviaWorksSection() {
  return (
    <SectionWrapper>
      <PageContainer>
        <div className="mb-10">
          <h2 className="text-2xl font-bold text-slate-900 md:text-3xl">Pourquoi Elevia fonctionne</h2>
          <p className="mt-3 text-slate-600">
            Une fusion de performance, design et transparence pour accélérer votre parcours.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {blocks.map((block) => (
            <GlassCard key={block.title} className="p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-lime-50 text-lime-600">
                <block.icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-slate-900">{block.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{block.description}</p>
            </GlassCard>
          ))}
        </div>
      </PageContainer>
    </SectionWrapper>
  );
}
