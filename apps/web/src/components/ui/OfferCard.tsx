import { Link } from "react-router-dom";
import { MapPin } from "lucide-react";
import { Badge, ScoreBadge } from "./badge";
import { GlassCard } from "./GlassCard";
import { cn } from "../../lib/cn";

export type OfferCardProps = {
  title: string;
  company: string;
  location: string;
  preview?: string;
  score?: number;
  tags?: string[];
  href?: string;
  className?: string;
};

export function OfferCard({ title, company, location, preview, score, tags = [], href, className }: OfferCardProps) {
  const card = (
    <GlassCard className={cn("p-5", href && "transition-shadow hover:shadow-md", className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="text-lg font-semibold text-slate-900">{title}</div>
          <div className="text-sm text-slate-600">{company}</div>
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            {location}
          </div>
          {preview && (
            <p className="mt-2 line-clamp-2 text-sm text-slate-500">{preview}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          {typeof score === "number" ? (
            <ScoreBadge score={score} />
          ) : (
            <Badge variant="default">—</Badge>
          )}
          <div className="text-xs text-slate-400">
            Match
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

  if (href) {
    return (
      <Link to={href} className="block no-underline">
        {card}
      </Link>
    );
  }

  return card;
}
