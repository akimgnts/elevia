import React from "react";

type RoleBlockScore = { role_block: string; score: number; share: number };
type ProfileIntelligenceData = {
  dominant_role_block?: string;
  dominant_score?: number;
  secondary_role_blocks?: string[];
  role_block_scores?: RoleBlockScore[];
  top_profile_signals?: string[];
};

type ProfileIntelligenceHeroProps = {
  profileIntelligence: unknown;
  structuredCvMetadata?: unknown;
  variant?: "full" | "compact";
};

const ROLE_BLOCK_LABELS: Record<string, string> = {
  data_analytics: "Analyse de données",
  business_analysis: "Analyse métier",
  finance_ops: "Finance opérationnelle",
  legal_compliance: "Conformité / Juridique",
  sales_business_dev: "Développement commercial",
  marketing_communication: "Marketing / Communication",
  hr_ops: "RH opérationnelles",
  supply_chain_ops: "Supply Chain / Opérations",
  project_ops: "Coordination de projets",
  software_it: "Software / IT",
  generalist_other: "Profil polyvalent",
};

function extractExtractionSource(
  metadata: unknown
): "structured_ai" | "legacy_parser" | "structured_mock" | null {
  if (!metadata || typeof metadata !== "object") return null;
  const source = (metadata as Record<string, unknown>).extraction_source;
  if (
    source === "structured_ai" ||
    source === "legacy_parser" ||
    source === "structured_mock"
  ) {
    return source;
  }
  return null;
}

function getRoleLabel(roleBlock: string): string {
  return ROLE_BLOCK_LABELS[roleBlock] || roleBlock;
}

function getTopScore(scores?: RoleBlockScore[]): number {
  if (!scores || scores.length === 0) return 1;
  return Math.max(...scores.map((s) => s.score));
}

function getSourceBadge(source: string | null): string {
  if (source === "structured_ai") return "IA";
  return "Classique";
}

function getSourceColor(
  source: string | null
): "text-emerald-600" | "text-slate-600" {
  return source === "structured_ai" ? "text-emerald-600" : "text-slate-600";
}

export const ProfileIntelligenceHero: React.FC<ProfileIntelligenceHeroProps> = ({
  profileIntelligence,
  structuredCvMetadata,
  variant = "full",
}) => {
  if (!profileIntelligence || typeof profileIntelligence !== "object") {
    return null;
  }

  const pi = profileIntelligence as Record<string, unknown>;
  const data: ProfileIntelligenceData = {
    dominant_role_block: pi.dominant_role_block as string | undefined,
    dominant_score: pi.dominant_score as number | undefined,
    secondary_role_blocks: pi.secondary_role_blocks as string[] | undefined,
    role_block_scores: pi.role_block_scores as RoleBlockScore[] | undefined,
    top_profile_signals: pi.top_profile_signals as string[] | undefined,
  };

  if (!data.dominant_role_block) {
    return null;
  }

  const topScore = getTopScore(data.role_block_scores);
  const dominantScore = data.dominant_score || topScore;
  const confidencePercent = Math.round((dominantScore / topScore) * 100);
  const source = extractExtractionSource(structuredCvMetadata);

  if (variant === "compact") {
    return (
      <div className="rounded-[1.75rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <h3 className="text-xl font-semibold tracking-tight text-slate-950">
              {getRoleLabel(data.dominant_role_block)}
            </h3>
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1.5 w-24 rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                  style={{ width: `${Math.min(confidencePercent, 100)}%` }}
                />
              </div>
              <span className="text-xs font-semibold text-slate-600">
                {confidencePercent}%
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            {data.secondary_role_blocks && data.secondary_role_blocks.length > 0 && (
              <div className="flex flex-wrap gap-1 justify-end">
                {data.secondary_role_blocks.slice(0, 2).map((role) => (
                  <span
                    key={role}
                    className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-600"
                  >
                    {role}
                  </span>
                ))}
              </div>
            )}
            {source && (
              <span
                className={`text-[10px] font-semibold uppercase ${getSourceColor(source)}`}
              >
                {getSourceBadge(source)}
              </span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // full variant
  return (
    <div className="rounded-[1.75rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <h2 className="text-2xl font-semibold tracking-tight text-slate-950">
            {getRoleLabel(data.dominant_role_block)}
          </h2>
          <div className="mt-4">
            <div className="h-1.5 rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${Math.min(confidencePercent, 100)}%` }}
              />
            </div>
            <p className="mt-1 text-xs font-semibold text-slate-600">
              Confiance: {confidencePercent}%
            </p>
          </div>

          {data.secondary_role_blocks && data.secondary_role_blocks.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                Profils secondaires
              </p>
              <div className="flex flex-wrap gap-2">
                {data.secondary_role_blocks.map((role) => (
                  <span
                    key={role}
                    className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600"
                  >
                    {getRoleLabel(role)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.top_profile_signals && data.top_profile_signals.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                Signaux dominants
              </p>
              <div className="flex flex-wrap gap-2">
                {data.top_profile_signals.slice(0, 3).map((signal, idx) => (
                  <span
                    key={idx}
                    className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700"
                  >
                    {signal}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {source && (
          <span
            className={`text-[10px] font-semibold uppercase ${getSourceColor(source)}`}
          >
            {getSourceBadge(source)}
          </span>
        )}
      </div>
    </div>
  );
};

export default ProfileIntelligenceHero;
