export function MarketPositionCard({
  matchedSkills,
  missingSkills,
  loading,
  note,
}: {
  matchedSkills: string[];
  missingSkills: string[];
  loading?: boolean;
  note?: string;
}) {
  return (
    <section className="bg-white ring-1 ring-slate-200 rounded-2xl p-5 shadow-card space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-700">Position sur le marché</h3>
        <p className="mt-1 text-xs text-slate-400">
          {note ?? "Basé sur les offres les plus proches du profil."}
        </p>
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Compétences alignées
        </div>
        {loading ? (
          <div className="mt-2 text-xs text-slate-400">Analyse en cours…</div>
        ) : matchedSkills.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {matchedSkills.map((skill) => (
              <span
                key={skill}
                className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-100"
              >
                {skill}
              </span>
            ))}
          </div>
        ) : (
          <div className="mt-2 text-xs text-slate-400">Aucun alignement détecté.</div>
        )}
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Compétences manquantes fréquentes
        </div>
        {loading ? (
          <div className="mt-2 text-xs text-slate-400">Analyse en cours…</div>
        ) : missingSkills.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {missingSkills.map((skill) => (
              <span
                key={skill}
                className="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-100"
              >
                {skill}
              </span>
            ))}
          </div>
        ) : (
          <div className="mt-2 text-xs text-slate-400">
            Aucune compétence manquante signalée.
          </div>
        )}
      </div>
    </section>
  );
}
