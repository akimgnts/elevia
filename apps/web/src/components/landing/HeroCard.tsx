import { motion } from "framer-motion";

const cardBase =
  "relative h-[230px] w-[330px] rounded-2xl border border-white/40 bg-white/80 p-5 shadow-[0_4px_25px_rgba(0,0,0,0.05)] transition-shadow hover:shadow-[0_8px_40px_rgba(6,182,212,0.20)] backdrop-blur-xl";

const badgeBase =
  "absolute -top-3 right-4 rounded-full bg-gradient-to-r from-[#06B6D4] to-[#22C55E] px-3 py-1 text-xs font-semibold text-white shadow-md";

export type HeroCardProps = {
  title: string;
  badge: string;
  subtitle: string;
  tags: string[];
  cta: string;
  className?: string;
};

export function HeroCard({ title, badge, subtitle, tags, cta, className }: HeroCardProps) {
  return (
    <motion.div
      whileHover={{ scale: 1.04, y: -5 }}
      whileTap={{ scale: 0.98 }}
      className={`transform-gpu will-change-transform ${cardBase} ${className ?? ""}`}
    >
      <div className={badgeBase}>{badge}</div>
      <div className="text-lg font-semibold text-slate-900">{title}</div>
      <p className="mt-2 text-sm text-slate-600">{subtitle}</p>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
        {tags.map((tag) => (
          <span key={tag} className="rounded-full bg-slate-100 px-2 py-1">
            {tag}
          </span>
        ))}
      </div>
      <button className="mt-5 text-sm font-semibold text-cyan-600">{cta} →</button>
    </motion.div>
  );
}
