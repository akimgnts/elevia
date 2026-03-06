import type { ReactNode } from "react";

export function ProfileCard({
  cluster,
  topSkills,
  languages,
  footer,
}: {
  cluster: string | null;
  topSkills: string[];
  languages: string[];
  footer?: ReactNode;
}) {
  return (
    <section className="bg-white ring-1 ring-slate-200 rounded-2xl p-5 shadow-card space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-700">Profil détecté</h3>
        <div className="mt-2 inline-flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Cluster
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
            {cluster ?? "—"}
          </span>
        </div>
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Compétences principales
        </div>
        {topSkills.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {topSkills.map((skill) => (
              <span
                key={skill}
                className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-100"
              >
                {skill}
              </span>
            ))}
          </div>
        ) : (
          <div className="mt-2 text-xs text-slate-400">Aucune compétence détectée.</div>
        )}
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Langues
        </div>
        {languages.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {languages.map((lang) => (
              <span
                key={lang}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
              >
                {lang}
              </span>
            ))}
          </div>
        ) : (
          <div className="mt-2 text-xs text-slate-400">Langues non détectées.</div>
        )}
      </div>

      {footer ? <div className="pt-2">{footer}</div> : null}
    </section>
  );
}
