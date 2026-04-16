import type { EnrichmentAutoFilled, StructuringReport } from "./profileWizardTypes";

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[1.25rem] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
    </div>
  );
}

export function AgentUnderstandingStep({
  report,
  autoFilledCount,
  remainingQuestionsCount,
  prioritySignalCount,
  autoFilledItems,
}: {
  report?: StructuringReport;
  autoFilledCount: number;
  remainingQuestionsCount: number;
  prioritySignalCount: number;
  autoFilledItems: EnrichmentAutoFilled[];
}) {
  const stats = report?.stats || {};
  const links = stats.skill_links_created || 0;
  const coverage = typeof stats.coverage_ratio === "number" ? Math.round(stats.coverage_ratio * 100) : 0;
  const visibleAutoFilledItems = autoFilledItems.slice(0, 4);

  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-5 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Ce que l&apos;agent a compris</div>
      <div className="mt-3 grid gap-5 lg:grid-cols-[1.25fr_0.75fr] lg:items-start">
        <div>
          <h2 className="text-xl font-semibold text-slate-950">Votre profil est prêt à devenir lisible, utile et actionnable.</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Le wizard transforme le parsing brut en signal produit. Il relie les expériences, les outils et le contexte pour préparer le cockpit, les candidatures et le CV sans vous faire repartir de zéro.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-slate-600">
            <li>• Vérifier ce qui a été compris automatiquement.</li>
            <li>• Réduire la retouche manuelle au minimum.</li>
            <li>• Garder un profil cohérent pour le matching et les documents.</li>
          </ul>
        </div>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
          <Metric label="Expériences" value={`${stats.experiences_processed || 0}`} />
          <Metric label="Liens structurés" value={`${links}`} />
          <Metric label="Couverture" value={`${coverage}%`} />
        </div>
      </div>

      <div className="mt-5 rounded-[1.25rem] border border-sky-200 bg-sky-50 px-4 py-4 text-sm text-sky-950">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-700">Ce que ça change pour vous</div>
        <div className="mt-2 grid gap-2">
          <div>Votre profil est déjà exploitable.</div>
          <div>{autoFilledCount > 0 ? `${autoFilledCount} information(s) ont été complétées automatiquement.` : "Le système a commencé à structurer votre profil automatiquement."}</div>
          <div>{remainingQuestionsCount > 0 ? `Il reste ${remainingQuestionsCount} point(s) à clarifier.` : "Il ne reste aucune clarification bloquante."}</div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          {remainingQuestionsCount > 0 ? `${remainingQuestionsCount} question(s) de clarification avant validation.` : "Aucune question bloquante pour l’instant."}
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          Les liens skill_links restent la source la plus lisible pour les expériences.
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          {prioritySignalCount > 0 ? `${prioritySignalCount} signal(s) prioritaire(s) peuvent déjà être réutilisés côté produit.` : "Le cockpit consommera ensuite ce profil structuré."}
        </div>
        <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          Le CV final pourra réutiliser le même signal sans duplication.
        </div>
      </div>

      <div className="mt-5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Ce que nous avons complété automatiquement</div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {visibleAutoFilledItems.length > 0 ? (
            visibleAutoFilledItems.map((item, index) => (
              <div key={`${item.experience_index ?? "global"}-${item.skill_link_index ?? "link"}-${item.target_field ?? "field"}-${index}`} className="rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-slate-900">{item.target_field || "Champ enrichi"}</div>
                  <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                    Ajouté automatiquement
                  </span>
                </div>
                <div className="mt-2">{item.value || "Complété automatiquement"}</div>
                {typeof item.confidence === "number" && (
                  <div className="mt-2 text-xs text-slate-500">Confiance {item.confidence.toFixed(2)}</div>
                )}
              </div>
            ))
          ) : (
            <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              Aucun enrichissement supplémentaire n’a encore été appliqué automatiquement.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
