import * as React from "react";
import { cn } from "../../lib/cn";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-card bg-slate-100",
        className
      )}
      {...props}
    />
  );
}
