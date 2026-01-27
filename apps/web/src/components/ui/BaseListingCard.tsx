import { ChevronRight } from "lucide-react";
import { GlassCard } from "./GlassCard";

export type BaseListingCardProps = {
  title: string;
  description: string;
  meta?: string;
};

export function BaseListingCard({ title, description, meta }: BaseListingCardProps) {
  return (
    <GlassCard className="flex items-center justify-between gap-4 p-5">
      <div>
        <div className="text-base font-semibold text-slate-900">{title}</div>
        <div className="mt-1 text-sm text-slate-600">{description}</div>
        {meta && <div className="mt-2 text-xs text-slate-500">{meta}</div>}
      </div>
      <ChevronRight className="h-5 w-5 text-slate-400" />
    </GlassCard>
  );
}
