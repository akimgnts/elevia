import { motion } from "framer-motion";
import { Button } from "../ui/Button";
import { Badge } from "../ui/badge";
import { HeroCard } from "../ui/HeroCard";
import { PageContainer } from "../layout/PageContainer";
import { SectionWrapper } from "../layout/SectionWrapper";
import { fadeInUp, staggerContainer, staggerItem } from "../../lib/animations";

export function HeroSection() {
  return (
    <SectionWrapper className="pt-32 md:pt-40">
      <PageContainer>
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="show"
          className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]"
        >
          <motion.div variants={staggerItem} className="space-y-6">
            <Badge className="w-fit" variant="info">
              ADA Elevia V9 · Next Horizon+
            </Badge>
            <h1 className="text-4xl font-bold text-slate-900 md:text-5xl">
              Vos opportunités V.I.E sur un horizon clair et actionnable.
            </h1>
            <p className="text-base text-slate-600">
              Analysez votre CV, déclenchez un matching IA précis, et pilotez vos prochaines étapes dans un dashboard inspiré des meilleurs outils productivité.
            </p>
            <div className="flex flex-wrap gap-4">
              <Button variant="primary">Commencer gratuitement</Button>
              <Button variant="secondary">Voir la démo</Button>
            </div>
          </motion.div>
          <motion.div variants={fadeInUp} className="grid gap-4 md:grid-cols-2">
            <HeroCard title="Match" value="92%" subtitle="+12% ce mois" />
            <HeroCard title="Offres activées" value="48" subtitle="3 nouvelles aujourd'hui" />
            <HeroCard title="Temps gagné" value="6h" subtitle="/ semaine" />
            <HeroCard title="Entreprises" value="29" subtitle="ciblées" />
          </motion.div>
        </motion.div>
      </PageContainer>
    </SectionWrapper>
  );
}
