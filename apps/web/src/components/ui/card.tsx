import * as React from "react";
import { cn } from "../../lib/cn";

export type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  elevated?: boolean;
};

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, elevated = true, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-card border border-slate-100 bg-white transition-shadow",
        elevated ? "shadow-sm" : "shadow-card",
        className
      )}
      {...props}
    />
  )
);

Card.displayName = "Card";
