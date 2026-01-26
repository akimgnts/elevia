import * as React from "react";
import { cn } from "../../lib/cn";

export type BadgeVariant =
  | "default"
  | "excellent"
  | "good"
  | "medium"
  | "low"
  | "info";

const variantClasses: Record<BadgeVariant, string> = {
  default: "badge-default",
  excellent: "badge-excellent",
  good: "badge-good",
  medium: "badge-medium",
  low: "badge-low",
  info: "badge-info",
};

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-badge px-3 py-1 text-xs font-semibold",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}

export function ScoreBadge({ score }: { score: number }) {
  let variant: BadgeVariant = "default";
  if (score >= 80) variant = "excellent";
  else if (score >= 60) variant = "good";
  else if (score >= 40) variant = "medium";
  else variant = "low";

  return <Badge variant={variant}>{score}%</Badge>;
}
