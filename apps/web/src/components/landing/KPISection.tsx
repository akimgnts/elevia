export function KPISection() {
  const items = [
    { label: "Matching", value: "94%" },
    { label: "Offres actives", value: "420+" },
    { label: "Temps gagné", value: "-6h" },
  ];

  return (
    <div className="mt-6 flex flex-wrap gap-6 text-sm text-slate-600">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-2">
          <span className="text-lg font-semibold text-slate-900">{item.value}</span>
          <span className="text-slate-500">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
