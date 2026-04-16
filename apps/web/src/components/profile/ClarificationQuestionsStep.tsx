import type { ReactNode } from "react";

import type { WizardQuestion } from "./profileWizardTypes";

type AutonomyLevel = "execution" | "partial" | "autonomous" | "ownership";

function QuestionShell({
  question,
  children,
}: {
  question: WizardQuestion;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[1.25rem] border border-slate-200 bg-slate-50 p-4">
      <div className="text-sm font-semibold text-slate-950">{question.question || "Précisez cette information"}</div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

export function ClarificationQuestionsStep({
  questions,
  experiences,
  onAnswer,
  onNext,
}: {
  questions: WizardQuestion[];
  experiences: Array<{
    tools?: Array<{ label: string }>;
    canonical_skills_used?: Array<{ label: string; uri?: string | null }>;
  }>;
  onAnswer: (question: WizardQuestion, value: string | AutonomyLevel) => void;
  onNext: () => void;
}) {
  if (questions.length === 0) {
    return (
      <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Questions de clarification</div>
        <h2 className="mt-3 text-2xl font-semibold text-slate-950">Aucune ambiguïté critique à résoudre.</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Le profil structuré est suffisamment clair pour passer à la validation.
        </p>
        <button
          type="button"
          onClick={onNext}
          className="mt-6 inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Continuer vers la validation
        </button>
      </section>
    );
  }

  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Questions de clarification</div>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Les réponses modifient directement le profil structuré. L’objectif n’est pas de re-remplir le CV, mais de lever les ambiguïtés restantes.
      </p>
      <div className="mt-5 space-y-4">
        {questions.map((question, index) => {
          const key = `${question.type}-${question.experience_index ?? "global"}-${question.skill_link_index ?? 0}-${index}`;
          const experience =
            question.experience_index != null ? experiences[question.experience_index] : undefined;
          if (question.type === "autonomy") {
            return (
              <QuestionShell key={key} question={question}>
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  {question.source === "enrichment" ? "Question enrichissement" : "Question structuration"}
                </div>
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
                  onChange={(event) => onAnswer(question, event.target.value as AutonomyLevel)}
                  defaultValue=""
                >
                  <option value="" disabled>
                    Choisir un niveau
                  </option>
                  <option value="execution">Exécution</option>
                  <option value="partial">Contribution partielle</option>
                  <option value="autonomous">Autonome</option>
                  <option value="ownership">Ownership</option>
                </select>
              </QuestionShell>
            );
          }

          return (
            <QuestionShell key={key} question={question}>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                {question.source === "enrichment" ? "Question enrichissement" : "Question structuration"}
              </div>
              {question.type === "tool" ? (
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
                  onChange={(event) => onAnswer(question, event.target.value)}
                  defaultValue=""
                >
                  <option value="" disabled>
                    Choisir un outil
                  </option>
                  {((experience?.tools || []) as Array<{ label: string }>).map((tool) => (
                    <option key={tool.label} value={tool.label}>
                      {tool.label}
                    </option>
                  ))}
                </select>
              ) : question.type === "skill" ? (
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900"
                  onChange={(event) => onAnswer(question, event.target.value)}
                  defaultValue=""
                >
                  <option value="" disabled>
                    Choisir une compétence
                  </option>
                  {((experience?.canonical_skills_used || []) as Array<{ label: string }>).map((skill) => (
                    <option key={skill.label} value={skill.label}>
                      {skill.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                  placeholder="Contexte court"
                  onChange={(event) => onAnswer(question, event.target.value)}
                />
              )}
            </QuestionShell>
          );
        })}
      </div>
      <button
        type="button"
        onClick={onNext}
        className="mt-6 inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        Continuer vers la validation
      </button>
    </section>
  );
}
