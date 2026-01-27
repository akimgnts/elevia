import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { KPISection } from "./KPISection";
import { HeroCardsGroup } from "./HeroCardsGroup";
import { PageContainer } from "../layout/PageContainer";

export function HeroSection() {
  return (
    <section className="relative pt-24 md:pt-32">
      <PageContainer>
        <motion.div
          className="transform-gpu will-change-transform"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="inline-flex items-center rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm">
            ADA Elevia • Next Horizon+
          </div>
          <h1 className="mt-6 text-4xl font-bold text-slate-900 md:text-5xl">
            Ton CV devient un plan d’action clair pour le V.I.E.
          </h1>
          <p className="mt-4 max-w-2xl text-base text-slate-600 md:text-lg">
            Analyse intelligente, matching V.I.E. fiable, et recommandations concrètes pour postuler plus vite.
          </p>
          <KPISection />
        </motion.div>

        <HeroCardsGroup />

        <div className="mt-12 flex flex-wrap items-center gap-4">
          <Link
            to="/analyse"
            className="rounded-xl bg-gradient-to-r from-[#06B6D4] to-[#22C55E] px-8 py-3 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.02]"
          >
            Essayer
          </Link>
          <Link
            to="/demo"
            className="rounded-xl border border-slate-200 bg-white/80 px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm"
          >
            Voir la démo
          </Link>
        </div>
      </PageContainer>
    </section>
  );
}
