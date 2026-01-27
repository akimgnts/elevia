import { motion } from "framer-motion";
import { card, badge as badgeToken, typography } from "../../styles/uiTokens";

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
  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      className={`transform-gpu will-change-transform ${featured ? card.hero : card.base} ${className ?? ""}`}
    >
      <div className="flex items-start justify-between">
        <div className={featured ? "text-lg font-semibold text-slate-900" : typography.label}>
          {title}
        </div>
        <div className={badgeToken.brand}>{badge}</div>
      </div>
      <p className={`mt-2 ${typography.body}`}>{subtitle}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span key={tag} className={badgeToken.neutral}>
            {tag}
          </span>
        ))}
      </div>
      <button className="mt-5 text-sm font-semibold text-cyan-600 hover:text-cyan-700 transition-colors">
        {cta} →
      </button>
    </motion.div>
  );
}
