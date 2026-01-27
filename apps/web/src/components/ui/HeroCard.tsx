import { ArrowUpRight } from "lucide-react";
import { GlassCard } from "./GlassCard";

export type HeroCardProps = {
  title: string;
  value: string;
  subtitle: string;
};

export function HeroCard({ title, value, subtitle }: HeroCardProps) {
  return (
    <GlassCard className="p-5">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</div>
      <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
      <div className="mt-2 inline-flex items-center gap-1 text-xs text-cyan-600">
        <ArrowUpRight className="h-3.5 w-3.5" />
        {subtitle}
      </div>
    </GlassCard>
  );
}
