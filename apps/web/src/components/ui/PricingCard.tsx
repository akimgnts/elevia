import { Check } from "lucide-react";
import { Button } from "./Button";
import { GlassCard } from "./GlassCard";
import { cn } from "../../lib/cn";

export type PricingCardProps = {
  name: string;
  price: string;
  description: string;
  features: string[];
  highlighted?: boolean;
};

export function PricingCard({
  name,
  price,
  description,
  features,
  highlighted = false,
}: PricingCardProps) {
  return (
    <GlassCard
      className={cn(
        "p-6",
        highlighted && "border-cyan-200 shadow-glow"
      )}
    >
      <div className="text-sm font-semibold text-cyan-600">{name}</div>
      <div className="mt-2 text-3xl font-bold text-slate-900">{price}</div>
      <p className="mt-2 text-sm text-slate-600">{description}</p>
      <div className="mt-4 space-y-2 text-sm text-slate-600">
        {features.map((feature) => (
          <div key={feature} className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 text-lime-500" />
            <span>{feature}</span>
          </div>
        ))}
      </div>
      <Button className="mt-6 w-full" variant={highlighted ? "primary" : "secondary"}>
        Choisir ce plan
      </Button>
    </GlassCard>
  );
}
