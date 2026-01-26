import { FileText, Sparkles, Target } from "lucide-react";
import { GlassCard } from "../ui/GlassCard";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";

const steps = [
  {
    icon: FileText,
    title: "Importez votre CV",
    description: "Déposez votre CV ou collez son contenu pour une analyse immédiate.",
  },
  {
    icon: Sparkles,
    title: "IA + Matching",
    description: "Nous alignons vos compétences avec les meilleures offres V.I.E.",
  },
  {
    icon: Target,
    title: "Passez à l'action",
    description: "Suivez vos candidats favoris et priorisez vos candidatures.",
  },
];

export function HowItWorksSection() {
  return (
    <SectionWrapper>
      <PageContainer>
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-bold text-slate-900 md:text-3xl">Un process simple et fluide</h2>
          <p className="mt-3 text-slate-600">3 étapes pour transformer vos données en opportunités concrètes.</p>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {steps.map((step) => (
            <GlassCard key={step.title} className="p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-cyan-50 text-cyan-600">
                <step.icon className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-slate-900">{step.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{step.description}</p>
            </GlassCard>
          ))}
        </div>
      </PageContainer>
    </SectionWrapper>
  );
}
