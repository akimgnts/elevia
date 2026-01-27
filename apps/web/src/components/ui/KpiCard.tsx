import { ArrowUpRight } from "lucide-react";
import { GlassCard } from "./GlassCard";
import { cn } from "../../lib/cn";

export type KpiCardProps = {
  label: string;
  value: string;
  delta?: string;
  accent?: "cyan" | "lime";
  className?: string;
};

export function KpiCard({ label, value, delta, accent = "cyan", className }: KpiCardProps) {
  const accentClass = accent === "lime" ? "text-lime-600" : "text-cyan-600";
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-3xl font-bold text-slate-900">{value}</div>
      {delta && (
        <div className={cn("mt-2 inline-flex items-center gap-1 text-xs font-semibold", accentClass)}>
          <ArrowUpRight className="h-3.5 w-3.5" />
          {delta}
        </div>
      )}
    </GlassCard>
  );
}
