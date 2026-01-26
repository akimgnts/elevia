import { MapPin, Sparkles } from "lucide-react";
import { Badge, ScoreBadge } from "./Badge";
import { GlassCard } from "./GlassCard";
import { cn } from "../../lib/cn";

export type OfferCardProps = {
  title: string;
  company: string;
  location: string;
  score?: number;
  tags?: string[];
  className?: string;
};

export function OfferCard({ title, company, location, score, tags = [], className }: OfferCardProps) {
  return (
    <GlassCard className={cn("p-5", className)}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-lg font-semibold text-slate-900">{title}</div>
          <div className="text-sm text-slate-600">{company}</div>
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <MapPin className="h-3.5 w-3.5" />
            {location}
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          {typeof score === "number" ? (
            <ScoreBadge score={score} />
          ) : (
            <Badge variant="default">—</Badge>
          )}
          <div className="flex items-center gap-1 text-xs text-cyan-600">
            <Sparkles className="h-3.5 w-3.5" />
            Match IA
          </div>
        </div>
      </div>
      {tags.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {tags.map((tag) => (
            <Badge key={tag} variant="default">
              {tag}
            </Badge>
          ))}
        </div>
      )}
    </GlassCard>
  );
}
