import { Link } from "react-router-dom";

export function ProfileValidationStep({
  completePct,
  structuredExperienceCount,
  structuredLinkCount,
  remainingAmbiguities,
  estimatedMatches,
  onValidate,
}: {
  completePct: number;
  structuredExperienceCount: number;
  structuredLinkCount: number;
  remainingAmbiguities: number;
  estimatedMatches?: number;
  onValidate: () => void;
}) {
  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Validation finale</div>
      <h2 className="mt-3 text-2xl font-semibold text-slate-950">Vous êtes maintenant prêt à voir vos opportunités.</h2>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Le profil a été structuré, relu et peut désormais alimenter le matching, le CV, le cockpit et les prochaines décisions produit.
      </p>

      <div className="mt-5 grid gap-4 md:grid-cols-4">
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Complétude</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{completePct}%</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Expériences</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{structuredExperienceCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Skill links</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{structuredLinkCount}</div>
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Ambiguïtés restantes</div>
          <div className="mt-2 text-2xl font-semibold text-slate-950">{remainingAmbiguities}</div>
        </div>
      </div>

      <div className="mt-5 rounded-[1.25rem] border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
        <div className="font-semibold">Projection vers la suite</div>
        <p className="mt-1 leading-6">
          {estimatedMatches != null
            ? `${estimatedMatches} opportunités peuvent maintenant être explorées depuis le cockpit et l’inbox.`
            : "Ce profil va maintenant être utilisé pour le matching, la génération de CV et le cockpit."}
        </p>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onValidate}
          className="inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Valider mon profil
        </button>
        <Link
          to="/cockpit"
          className="inline-flex items-center rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Voir mon cockpit
        </Link>
      </div>
    </section>
  );
}
