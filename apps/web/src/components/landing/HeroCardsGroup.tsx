import { motion } from "framer-motion";
import { HeroCard } from "./HeroCard";

const cards = [
  {
    title: "CV + Lettre",
    badge: "ATS-Friendly",
    subtitle: "Génération IA • Documents prêts à envoyer",
    tags: ["ATS-Friendly", "Personnalisé", "Rapide"],
    cta: "Générer",
  },
  {
    title: "Offres V.I.E",
    badge: "Match IA 94%",
    subtitle: "Recommandations • Score + raisons",
    tags: ["V.I.E", "Score IA", "Raisons"],
    cta: "Voir",
  },
  {
    title: "Formations",
    badge: "Recommandée",
    subtitle: "Renforcement • Avant candidature",
    tags: ["8 modules", "Sur-mesure", "Rapide"],
    cta: "Démarrer",
  },
];

export function HeroCardsGroup() {
  return (
    <motion.div
      className="relative mt-10 flex items-center justify-center transform-gpu will-change-transform"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="relative h-[260px] w-full">
        <div className="absolute left-1/2 top-0 hidden -translate-x-[66%] md:block">
          <HeroCard
            {...cards[0]}
            className="rotate-[-2.5deg] opacity-95"
          />
        </div>
        <div className="absolute left-1/2 top-0 -translate-x-1/2">
          <HeroCard {...cards[1]} className="opacity-100" />
        </div>
        <div className="absolute left-1/2 top-0 hidden -translate-x-[34%] md:block">
          <HeroCard
            {...cards[2]}
            className="rotate-[2.5deg] opacity-92"
          />
        </div>
      </div>
    </motion.div>
  );
}
