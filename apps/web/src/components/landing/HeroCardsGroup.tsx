import { motion } from "framer-motion";
import { HeroCard } from "./HeroCard";

const cards = [
  {
    title: "CV + Lettre",
    badge: "ATS-Friendly",
    subtitle: "Génération IA • Documents prêts à envoyer",
    tags: ["ATS-Friendly", "Personnalisé", "Rapide"],
    cta: "Générer",
    featured: false,
  },
  {
    title: "Offres V.I.E",
    badge: "Match IA 94%",
    subtitle: "Recommandations • Score + raisons",
    tags: ["V.I.E", "Score IA", "Raisons"],
    cta: "Voir",
    featured: true,
  },
  {
    title: "Formations",
    badge: "Recommandée",
    subtitle: "Renforcement • Avant candidature",
    tags: ["8 modules", "Sur-mesure", "Rapide"],
    cta: "Démarrer",
    featured: false,
  },
];

export function HeroCardsGroup() {
  return (
    <motion.div
      className="transform-gpu will-change-transform"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
    >
      {/* Bento grid: 2 cols on desktop, stack on mobile */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Featured card spans full width on first row */}
        <div className="md:col-span-2">
          <HeroCard {...cards[1]} featured />
        </div>
        {/* Two smaller cards side by side */}
        <HeroCard {...cards[0]} />
        <HeroCard {...cards[2]} />
      </div>
    </motion.div>
  );
}
