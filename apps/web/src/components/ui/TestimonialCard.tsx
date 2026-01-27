import { Quote } from "lucide-react";
import { GlassCard } from "./GlassCard";

export type TestimonialCardProps = {
  quote: string;
  author: string;
  role: string;
};

export function TestimonialCard({ quote, author, role }: TestimonialCardProps) {
  return (
    <GlassCard className="p-6">
      <Quote className="h-6 w-6 text-cyan-500" />
      <p className="mt-4 text-sm text-slate-600">“{quote}”</p>
      <div className="mt-4 text-sm font-semibold text-slate-900">{author}</div>
      <div className="text-xs text-slate-500">{role}</div>
    </GlassCard>
  );
}
