/**
 * InboxCardV2 — Signal-first offer card (Catalyst/Tailwind).
 *
 * Layout:
 *   Block A — Identity (title, company, location) + Score (dominant)
 *   Block B — Cluster badge
 *   Block C — Top 3 matched skill pills
 *   Block D — ONE priority insight (deterministic)
 *   Actions  — [Générer Lettre] [Voir détails]
 *
 * No debug data. No raw tokens. No large arrays.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

export interface InboxCardV2Props {
  offerId: string;
  company: string;
  title: string;
  location?: string;
  /** 0–100 */
  score: number;
  cluster: { label: string; percent?: number };
  /** Already capped to 3 upstream */
  topMatchedSkills: string[];
  injectedEscoFromDomain?: number;
  resolvedToEsco?: Array<{
    token_normalized: string;
    esco_label?: string;
    provenance?: string;
  }>;
  /** Already capped to 1 upstream */
  missingCriticalSkills?: string[];
  rareSignal?: { label: string } | null;
  onOpenDetails: (offerId: string) => void;
  onGenerateLetter: (offerId: string) => void;
}

// ── Score color utilities ─────────────────────────────────────────────────────

/** Tailwind text color class for score number */
export function getScoreColor(score: number): string {
  if (score > 75) return "text-emerald-600";
  if (score >= 50) return "text-amber-600";
  return "text-rose-500";
}

/** Tailwind ring/border color class for score badge */
export function getScoreRingColor(score: number): string {
  if (score > 75) return "ring-emerald-200 bg-emerald-50";
  if (score >= 50) return "ring-amber-200 bg-amber-50";
  return "ring-rose-200 bg-rose-50";
}

// ── Cluster label helpers ─────────────────────────────────────────────────────

const CLUSTER_LABELS: Record<string, string> = {
  DATA_IT:         "Data / IT",
  FINANCE:         "Finance",
  FINANCE_LEGAL:   "Finance",
  SUPPLY_OPS:      "Supply & Ops",
  MARKETING_SALES: "Marketing",
  PROJECT_MGT:     "Chef de projet",
  HR:              "RH",
  SECURITY:        "Sécurité",
};

function formatClusterLabel(raw: string): string {
  return CLUSTER_LABELS[raw.toUpperCase()] ?? raw;
}

// ── Priority signal ───────────────────────────────────────────────────────────

type InsightVariant = "mapping" | "missing" | "rare" | "default";

interface Insight {
  variant: InsightVariant;
  icon: string;
  text: string;
  subtitle?: string;
  bgClass: string;
  borderClass: string;
  textClass: string;
}

/** Deterministic: same input → same output. Exactly 1 insight. */
export function getPrioritySignal(data: {
  injectedEscoFromDomain?: number;
  resolvedToEsco?: InboxCardV2Props["resolvedToEsco"];
  missingCriticalSkills?: string[];
  rareSignal?: { label: string } | null;
}): Insight {
  // P1 — Mapping gain
  if ((data.injectedEscoFromDomain ?? 0) >= 1) {
    const count = data.injectedEscoFromDomain!;
    const first = data.resolvedToEsco?.[0];
    const subtitle =
      first
        ? `${first.token_normalized} → ${first.esco_label ?? first.token_normalized}`
        : undefined;
    return {
      variant: "mapping",
      icon: "↗",
      text: `+${count} compétence${count > 1 ? "s" : ""} via mapping métier`,
      subtitle,
      bgClass:     "bg-blue-50",
      borderClass: "border-blue-100",
      textClass:   "text-blue-800",
    };
  }

  // P2 — Missing critical skill
  if (data.missingCriticalSkills?.length) {
    return {
      variant: "missing",
      icon: "⚠",
      text: `Manque compétence clé : ${data.missingCriticalSkills[0]}`,
      bgClass:     "bg-amber-50",
      borderClass: "border-amber-100",
      textClass:   "text-amber-800",
    };
  }

  // P3 — Rare signal
  if (data.rareSignal) {
    return {
      variant: "rare",
      icon: "★",
      text: `Match rare : ${data.rareSignal.label}`,
      bgClass:     "bg-emerald-50",
      borderClass: "border-emerald-100",
      textClass:   "text-emerald-800",
    };
  }

  // P4 — Default
  return {
    variant: "default",
    icon: "i",
    text: "Voir détails pour l'explication complète",
    bgClass:     "bg-zinc-50",
    borderClass: "border-zinc-100",
    textClass:   "text-zinc-600",
  };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function InboxCardV2({
  offerId,
  company,
  title,
  location,
  score,
  cluster,
  topMatchedSkills,
  injectedEscoFromDomain,
  resolvedToEsco,
  missingCriticalSkills,
  rareSignal,
  onOpenDetails,
  onGenerateLetter,
}: InboxCardV2Props) {
  const insight = getPrioritySignal({
    injectedEscoFromDomain,
    resolvedToEsco,
    missingCriticalSkills,
    rareSignal,
  });

  const clusterDisplay = formatClusterLabel(cluster.label);
  const hasPercent = typeof cluster.percent === "number";

  return (
    <article
      className="group bg-white ring-1 ring-slate-200 rounded-2xl p-5 shadow-card
                 hover:shadow-md hover:ring-slate-300 transition-all flex flex-col h-full
                 focus-within:ring-2 focus-within:ring-slate-400 cursor-pointer"
      onClick={() => onOpenDetails(offerId)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onOpenDetails(offerId); }}
      tabIndex={0}
    >
      {/* ── Block A: Identity + Score ───────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-slate-900 leading-snug line-clamp-2">
            {title}
          </h3>
          <p className="mt-0.5 text-xs text-slate-500 line-clamp-1">
            {[company, location].filter(Boolean).join(" · ")}
          </p>
        </div>

        {/* Score badge */}
        <div
          className={`shrink-0 flex flex-col items-center justify-center
                      min-w-[3.5rem] h-14 rounded-xl ring-1 ${getScoreRingColor(score)}`}
        >
          <span className={`text-2xl font-bold leading-none tabular-nums ${getScoreColor(score)}`}>
            {score}
          </span>
          <span className="text-[9px] font-semibold uppercase tracking-wide text-slate-400 mt-0.5">
            %
          </span>
        </div>
      </div>

      {/* ── Block B: Cluster badge ──────────────────────────────────────────── */}
      {cluster.label && cluster.label !== "—" && (
        <div className="mt-3">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-badge
                           text-[10px] font-semibold uppercase tracking-wide
                           bg-slate-100 text-slate-600">
            {clusterDisplay}
            {hasPercent && (
              <span className="text-slate-400 font-normal">· {cluster.percent}%</span>
            )}
          </span>
        </div>
      )}

      {/* ── Block C: Top 3 skill pills ──────────────────────────────────────── */}
      {topMatchedSkills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {topMatchedSkills.map((skill) => (
            <span
              key={skill}
              className="px-2 py-0.5 rounded-badge text-[11px] font-medium
                         bg-emerald-50 text-emerald-700 border border-emerald-100
                         max-w-[12rem] truncate"
              title={skill}
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {/* ── Block D: Priority insight ───────────────────────────────────────── */}
      <div
        className={`mt-4 flex items-start gap-2 rounded-xl border px-3 py-2.5
                    ${insight.bgClass} ${insight.borderClass}`}
      >
        <span
          className={`shrink-0 text-sm font-bold leading-none mt-px ${insight.textClass}`}
          aria-hidden
        >
          {insight.icon}
        </span>
        <div className="min-w-0">
          <p className={`text-xs font-medium leading-snug ${insight.textClass}`}>
            {insight.text}
          </p>
          {insight.subtitle && (
            <p className={`mt-0.5 text-[10px] leading-snug opacity-70 ${insight.textClass} truncate`}>
              {insight.subtitle}
            </p>
          )}
        </div>
      </div>

      {/* ── Actions ─────────────────────────────────────────────────────────── */}
      <div className="mt-auto pt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onGenerateLetter(offerId); }}
          className="flex-1 sm:flex-none px-3 py-2 rounded-xl text-sm font-semibold
                     bg-slate-900 text-white hover:bg-slate-700 transition
                     focus:outline-none focus:ring-2 focus:ring-slate-500"
        >
          Générer lettre
        </button>
        <button
          type="button"
          onClick={() => onOpenDetails(offerId)}
          className="flex-1 sm:flex-none px-3 py-2 rounded-xl text-sm font-semibold
                     bg-white border border-slate-200 text-slate-700
                     hover:bg-slate-50 transition
                     focus:outline-none focus:ring-2 focus:ring-slate-300"
        >
          Détails
        </button>
      </div>
    </article>
  );
}
