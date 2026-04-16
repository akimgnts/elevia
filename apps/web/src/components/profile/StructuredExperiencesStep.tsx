import { useState, type ReactNode } from "react";

type TraceLike = {
  source?: string;
  confidence?: number;
};

type ToolLike = { label: string };
type LinkLike = {
  skill: { label: string };
  tools: ToolLike[];
  context?: string;
  autonomy_level?: string;
};
type ExperienceLike = {
  title?: string;
  company?: string;
  impact_signals?: string[];
  skill_links?: LinkLike[];
};

export function StructuredExperiencesStep({
  experiences,
  onNext,
  renderCorrectionPanel,
  selectedSkillLinkIndex,
  onSelectSkillLink,
  getLinkTrace,
  isFieldUserValidated,
}: {
  experiences: ExperienceLike[];
  onNext: () => void;
  renderCorrectionPanel: (index: number, skillLinkIndex: number) => ReactNode;
  selectedSkillLinkIndex: Record<number, number>;
  onSelectSkillLink: (experienceIndex: number, skillLinkIndex: number) => void;
  getLinkTrace: (experienceIndex: number, skillLinkIndex: number, field: "tools" | "context" | "autonomy_level") => TraceLike | undefined;
  isFieldUserValidated: (experienceIndex: number, skillLinkIndex: number, field: "tools" | "context" | "autonomy_level") => boolean;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  return (
    <section className="rounded-[1.5rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Vos expériences structurées</div>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        La vue par défaut reste une lecture structurée. Vous ouvrez un panneau ciblé uniquement pour corriger ce qui compte.
      </p>

      <div className="mt-5 space-y-4">
        {experiences.map((experience, index) => {
          const skillLinks = experience.skill_links || [];
          const activeLinkIndex =
            skillLinks.length > 0
              ? Math.min(Math.max(selectedSkillLinkIndex[index] ?? 0, 0), skillLinks.length - 1)
              : 0;

          function renderTraceBadge(skillLinkIndex: number, field: "tools" | "context" | "autonomy_level") {
            if (isFieldUserValidated(index, skillLinkIndex, field)) {
              return (
                <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                  user_validated
                </span>
              );
            }
            const trace = getLinkTrace(index, skillLinkIndex, field);
            if (trace?.source !== "enrichment") return null;
            return (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                Ajouté automatiquement{typeof trace.confidence === "number" ? ` (${trace.confidence.toFixed(2)})` : ""}
              </span>
            );
          }

          return (
            <article key={`${experience.title || "experience"}-${index}`} className="rounded-[1.25rem] border border-slate-200 bg-slate-50/70 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-base font-semibold text-slate-950">{experience.title || "Expérience"}</div>
                  <div className="text-sm text-slate-500">{experience.company || "Entreprise"}</div>
                </div>
                <button
                  type="button"
                  onClick={() => setEditingIndex((current) => (current === index ? null : index))}
                  className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  {editingIndex === index ? "Fermer la correction" : "Corriger"}
                </button>
              </div>

              {skillLinks.length > 0 ? (
                <div className="mt-4 grid gap-4">
                  <div className="flex flex-wrap gap-2">
                    {skillLinks.map((link, linkIndex) => (
                      <button
                        key={`${link.skill.label}-${linkIndex}`}
                        type="button"
                        onClick={() => onSelectSkillLink(index, linkIndex)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                          activeLinkIndex === linkIndex
                            ? "border-slate-900 bg-slate-900 text-white"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                        }`}
                      >
                        {link.skill.label || `Lien ${linkIndex + 1}`}
                      </button>
                    ))}
                  </div>

                  <div className="grid gap-3">
                    {skillLinks.map((link, linkIndex) => (
                      <div
                        key={`${link.skill.label}-${linkIndex}-card`}
                        className={`rounded-[1rem] border bg-white p-4 ${activeLinkIndex === linkIndex ? "border-slate-300 shadow-sm" : "border-slate-200"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Skill link {linkIndex + 1}</div>
                            <div className="mt-1 text-sm font-semibold text-slate-950">{link.skill.label || "À confirmer"}</div>
                          </div>
                          {activeLinkIndex === linkIndex && (
                            <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                              En cours d’édition
                            </span>
                          )}
                        </div>

                        <div className="mt-3 grid gap-3 lg:grid-cols-3">
                          <div className="rounded-[0.875rem] border border-slate-200 bg-slate-50 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Outils associés</div>
                              {renderTraceBadge(linkIndex, "tools")}
                            </div>
                            <div className="mt-2 flex flex-wrap gap-1.5">
                              {(link.tools || []).map((tool) => (
                                <span key={tool.label} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700">
                                  {tool.label}
                                </span>
                              ))}
                              {(link.tools || []).length === 0 && <span className="text-sm text-slate-400">À confirmer</span>}
                            </div>
                          </div>
                          <div className="rounded-[0.875rem] border border-slate-200 bg-slate-50 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Impact / contexte</div>
                              {renderTraceBadge(linkIndex, "context")}
                            </div>
                            <div className="mt-2 text-sm leading-6 text-slate-600">
                              {link.context || experience.impact_signals?.[0] || "À compléter"}
                            </div>
                          </div>
                          <div className="rounded-[0.875rem] border border-slate-200 bg-slate-50 p-3">
                            <div className="flex items-center justify-between gap-2">
                              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Autonomie</div>
                              {renderTraceBadge(linkIndex, "autonomy_level")}
                            </div>
                            <div className="mt-2 text-sm font-medium text-slate-700">
                              {link.autonomy_level || "À confirmer"}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="mt-4 grid gap-4 lg:grid-cols-3">
                  <div className="rounded-[1rem] border border-slate-200 bg-white p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Skill principal</div>
                    <div className="mt-2 text-sm font-semibold text-slate-950">À confirmer</div>
                  </div>
                  <div className="rounded-[1rem] border border-slate-200 bg-white p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Outils associés</div>
                    <div className="mt-2 text-sm text-slate-400">À confirmer</div>
                  </div>
                  <div className="rounded-[1rem] border border-slate-200 bg-white p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Impact / contexte</div>
                    <div className="mt-2 text-sm leading-6 text-slate-600">
                      {experience.impact_signals?.[0] || "À compléter"}
                    </div>
                  </div>
                </div>
              )}

              {editingIndex === index && (
                <div className="mt-4 rounded-[1rem] border border-slate-200 bg-white p-4">
                  <div className="text-sm font-semibold text-slate-900">Édition ciblée</div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    Les champs détaillés restent un secours. La correction doit rester courte et structurée.
                  </p>
                  <div className="mt-4">{renderCorrectionPanel(index, activeLinkIndex)}</div>
                </div>
              )}
            </article>
          );
        })}
      </div>

      <div className="mt-6">
        <button
          type="button"
          onClick={onNext}
          className="inline-flex items-center rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Continuer vers les questions
        </button>
      </div>
    </section>
  );
}
