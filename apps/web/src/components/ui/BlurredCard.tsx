import * as React from "react";
import { Lock } from "lucide-react";
import { cn } from "../../lib/cn";

export type BlurredCardProps = React.HTMLAttributes<HTMLDivElement> & {
  label?: string;
};

export function BlurredCard({ className, label = "Disponible en Premium", ...props }: BlurredCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-slate-200 bg-white/80 p-6",
        className
      )}
      {...props}
    >
      <div className="absolute inset-0 bg-slate-50/70 backdrop-blur-sm" />
      <div className="relative z-10 flex items-center gap-3 text-slate-600">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100">
          <Lock className="h-5 w-5" />
        </div>
        <div className="text-sm font-semibold">{label}</div>
      </div>
    </div>
  );
}
