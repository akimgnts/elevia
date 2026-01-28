import { motion } from "framer-motion";
import { card, cardPadding, badge as badgeToken, typography } from "../../styles/uiTokens";

export type HeroCardProps = {
  title: string;
  badge: string;
  subtitle: string;
  tags: string[];
  cta: string;
  featured?: boolean;
  className?: string;
};

export function HeroCard({ title, badge, subtitle, tags, cta, featured, className }: HeroCardProps) {
  const cardStyle = featured ? card.hero : card.base;
  const padding = featured ? cardPadding.lg : cardPadding.md;

  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ duration: 0.15 }}
      className={`transform-gpu will-change-transform ${cardStyle} ${padding} ${className ?? ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className={featured ? "text-lg font-semibold text-slate-900" : "text-sm font-semibold text-slate-800"}>
          {title}
        </h3>
        <span className={badgeToken.brand}>{badge}</span>
      </div>
      <p className={`mt-2 ${typography.body}`}>{subtitle}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span key={tag} className={badgeToken.neutral}>
            {tag}
          </span>
        ))}
      </div>
      <button className="mt-5 text-sm font-semibold text-brand-cyan hover:text-cyan-700 transition-colors">
        {cta} →
      </button>
    </motion.div>
  );
}
