import * as React from "react";
import { cn } from "../../lib/cn";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-button border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 shadow-xs outline-none transition-colors placeholder:text-slate-400 focus:border-brand-cyan focus:ring-2 focus:ring-brand-cyan/10 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);

Input.displayName = "Input";
