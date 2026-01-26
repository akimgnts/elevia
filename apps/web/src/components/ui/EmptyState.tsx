import { Sparkles } from "lucide-react";
import { Button } from "./Button";
import { cn } from "../../lib/cn";

export type EmptyStateProps = {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
};

export function EmptyState({
  title = "Aucun résultat",
  description = "Ajustez vos filtres ou relancez l'analyse.",
  actionLabel = "Relancer",
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-2xl border border-slate-200 bg-white/80 p-6 text-center",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-cyan-50 text-cyan-600">
        <Sparkles className="h-6 w-6" />
      </div>
      <div className="text-base font-semibold text-slate-900">{title}</div>
      <div className="text-sm text-slate-600">{description}</div>
      {onAction && (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
