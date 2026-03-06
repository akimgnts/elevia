export function ActionsCard({ actions }: { actions: string[] }) {
  return (
    <section className="bg-white ring-1 ring-slate-200 rounded-2xl p-5 shadow-card space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-700">Actions</h3>
        <p className="mt-1 text-xs text-slate-400">
          2 actions maximum pour améliorer la pertinence.
        </p>
      </div>

      {actions.length > 0 ? (
        <ul className="space-y-2 text-sm text-slate-700">
          {actions.slice(0, 2).map((action, idx) => (
            <li key={`${action}-${idx}`} className="flex items-start gap-2">
              <span className="mt-0.5 text-emerald-500">•</span>
              <span>{action}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-xs text-slate-400">Aucune action prioritaire détectée.</div>
      )}
    </section>
  );
}
