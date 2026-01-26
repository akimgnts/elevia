import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";
import { cn } from "../../lib/cn";

export type ErrorStateProps = {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
};

export function ErrorState({
  title = "Une erreur est survenue",
  description = "Essayez de rafraîchir la page ou réessayez plus tard.",
  actionLabel = "Réessayer",
  onAction,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-2xl border border-red-100 bg-red-50/80 p-6 text-center text-red-700",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <div className="text-base font-semibold">{title}</div>
      <div className="text-sm text-red-600">{description}</div>
      {onAction && (
        <Button variant="outline" onClick={onAction} className="border-red-200 text-red-600">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
