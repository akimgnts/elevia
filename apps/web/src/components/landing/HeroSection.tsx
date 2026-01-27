import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { KPISection } from "./KPISection";
import { HeroCardsGroup } from "./HeroCardsGroup";
import { PageContainer } from "../layout/PageContainer";
import { typography, button, badge, spacing } from "../../styles/uiTokens";

export function HeroSection() {
  return (
    <section className={spacing.heroTop}>
      <PageContainer>
        <div className="grid items-center gap-8 lg:grid-cols-2 lg:gap-12">
          {/* Left: Copy */}
          <motion.div
            className="transform-gpu will-change-transform"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className={badge.subtle}>
              ADA Elevia • Next Horizon+
            </div>
            <h1 className={`mt-6 ${typography.h1}`}>
              Ton CV devient un plan d'action clair pour le V.I.E.
            </h1>
            <p className={`mt-4 ${typography.lead}`}>
              Analyse intelligente, matching V.I.E. fiable, et recommandations concrètes pour postuler plus vite.
            </p>
            <KPISection />
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link to="/analyze" className={button.primary}>
                Essayer maintenant
              </Link>
              <Link to="/demo" className={button.secondary}>
                Voir la démo
              </Link>
            </div>
          </motion.div>

          {/* Right: Bento cards */}
          <HeroCardsGroup />
        </div>
      </PageContainer>
    </section>
  );
}
