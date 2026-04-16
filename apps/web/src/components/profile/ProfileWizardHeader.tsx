import type { ProfileWizardStep } from "./profileWizardTypes";

const STEP_LABELS: Array<{ step: ProfileWizardStep; label: string }> = [
  { step: "understanding", label: "Compréhension agent" },
  { step: "experiences", label: "Expériences" },
  { step: "questions", label: "Questions" },
  { step: "validation", label: "Validation" },
];

export function ProfileWizardHeader({
  currentStep,
  onBack,
}: {
  currentStep: ProfileWizardStep;
  onBack?: () => void;
}) {
  const activeIndex = STEP_LABELS.findIndex((item) => item.step === currentStep);

  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-5 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Wizard profil</div>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {STEP_LABELS.map((item, index) => {
          const active = item.step === currentStep;
          const done = index < activeIndex;
          return (
            <div
              key={item.step}
              className={`rounded-[1.25rem] border px-4 py-3 text-sm ${
                active
                  ? "border-slate-900 bg-slate-900 text-white"
                  : done
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                    : "border-slate-200 bg-slate-50 text-slate-500"
              }`}
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] opacity-70">
                Étape {index + 1}
              </div>
              <div className="mt-1 font-semibold">{item.label}</div>
            </div>
          );
        })}
      </div>
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="mt-4 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          Retour
        </button>
      )}
    </section>
  );
}
