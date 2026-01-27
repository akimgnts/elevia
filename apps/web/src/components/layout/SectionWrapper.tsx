import * as React from "react";
import { cn } from "../../lib/cn";

export function SectionWrapper({ className, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn("py-16 md:py-20", className)} {...props} />
  );
}
