import * as React from "react";
import { cn } from "../../lib/cn";

export function Heading1({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h1
      className={cn("text-3xl md:text-4xl font-bold text-slate-900", className)}
      {...props}
    />
  );
}

export function Heading2({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn("text-2xl md:text-3xl font-bold text-slate-900", className)}
      {...props}
    />
  );
}

export function Heading3({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-xl md:text-2xl font-semibold text-slate-900", className)}
      {...props}
    />
  );
}

export function BodyText({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-base leading-relaxed text-slate-600", className)} {...props} />
  );
}

export function Caption({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-sm text-slate-600", className)} {...props} />
  );
}

export function Label({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={cn("text-xs font-semibold uppercase tracking-wide", className)} {...props} />
  );
}
