import * as React from "react";
import { cn } from "../../lib/cn";

export type GlassCardProps = React.HTMLAttributes<HTMLDivElement> & {
  hoverable?: boolean;
};

export const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, hoverable = true, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        hoverable ? "card-boost-hover" : "card-boost",
        "transform-gpu",
        className
      )}
      {...props}
    />
  )
);

GlassCard.displayName = "GlassCard";
