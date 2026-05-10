import React from "react";

type SkillEntry = {
  label: string;
  type?: "hard" | "tool" | "domain";
  confidence?: number;
};

type SkillTypeGroupProps = {
  skills: SkillEntry[];
  maxPerGroup?: number;
};

const SKILL_TYPE_LABELS: Record<string, string> = {
  hard: "Compétences techniques",
  tool: "Outils & Technologies",
  domain: "Domaines d'expertise",
};

function isHighConfidence(confidence?: number): boolean {
  if (confidence === undefined) return true;
  return confidence >= 0.7;
}

export const SkillTypeGroup: React.FC<SkillTypeGroupProps> = ({
  skills,
  maxPerGroup,
}) => {
  if (!skills || skills.length === 0) {
    return null;
  }

  const grouped: Record<string, SkillEntry[]> = {
    hard: [],
    tool: [],
    domain: [],
  };

  skills.forEach((skill) => {
    const type = skill.type || "hard";
    grouped[type].push(skill);
  });

  const groups = Object.entries(grouped).filter(
    ([, items]) => items.length > 0
  );

  if (groups.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {groups.map(([type, items]) => {
        const displayItems = maxPerGroup
          ? items.slice(0, maxPerGroup)
          : items;

        return (
          <div key={type}>
            <p className="mb-2.5 text-xs font-semibold uppercase text-slate-500">
              {SKILL_TYPE_LABELS[type] || type}
            </p>
            <div className="flex flex-wrap gap-2">
              {displayItems.map((skill, idx) => {
                const highConfidence = isHighConfidence(skill.confidence);
                return (
                  <span
                    key={`${type}-${idx}`}
                    className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                      highConfidence
                        ? "border border-slate-200 bg-slate-100 text-slate-800"
                        : "border border-slate-200/60 bg-slate-50 text-slate-600"
                    }`}
                  >
                    {skill.label}
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default SkillTypeGroup;
