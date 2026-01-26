import { Target } from "lucide-react";
import { Badge } from "./Badge";
import { GlassCard } from "./GlassCard";

export type MatchingCardProps = {
  score: number;
  highlights: string[];
};

export function MatchingCard({ score, highlights }: MatchingCardProps) {
  return (
    <GlassCard className="p-5">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-700">Matching global</div>
        <Badge variant={score >= 80 ? "excellent" : score >= 60 ? "good" : score >= 40 ? "medium" : "low"}>
          {score}%
        </Badge>
      </div>
      <div className="mt-4 flex items-center gap-2 text-3xl font-bold text-slate-900">
        <Target className="h-7 w-7 text-cyan-500" />
        {score}%
      </div>
      <div className="mt-4 space-y-2 text-sm text-slate-600">
        {highlights.map((item) => (
          <div key={item}>• {item}</div>
        ))}
      </div>
    </GlassCard>
  );
}
