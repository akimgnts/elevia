import { typography } from "../../styles/uiTokens";

const items = [
  { label: "Matching", value: "94%" },
  { label: "Offres actives", value: "420+" },
  { label: "Temps gagné", value: "-6h" },
];

export function KPISection() {
  return (
    <div className="mt-6 flex flex-wrap gap-6">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-2">
          <span className="text-lg font-semibold text-slate-900">{item.value}</span>
          <span className={typography.caption}>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
