/**
 * InboxCardV2 — decision-first inbox card.
 *
 * Layout:
 *   verdict -> role signal -> why it fits -> blockers -> next action
 */

// ── Types ─────────────────────────────────────────────────────────────────────

export interface InboxCardV2Props {
  offerId: string;
  company: string;
  title: string;
  location?: string;
  /** 0–100 */
  score: number;
  explanation: {
    score?: number | null;
    fit_label: string;
    summary_reason: string;
    strengths: string[];
    gaps: string[];
    blockers: string[];
    next_actions: string[];
  };
  semanticExplainability?: {
    role_alignment: {
      profile_role: string;
      offer_role: string;
      alignment: "high" | "medium" | "low";
    };
    domain_alignment: {
      shared_domains: string[];
      profile_only_domains: string[];
      offer_only_domains: string[];
    };
    signal_alignment: {
      matched_signals: string[];
      missing_core_signals: string[];
    };
    alignment_summary: string;
  } | null;
  scoringV2?: {
    score: number;
    score_pct: number;
    components: {
      role_alignment: number;
      domain_alignment: number;
      matching_base: number;
      gap_penalty: number;
    };
  } | null;
  offerIntelligence?: {
    dominant_role_block: string;
    dominant_domains: string[];
    top_offer_signals: string[];
    required_skills: string[];
    optional_skills: string[];
    offer_summary: string;
  } | null;
  /** strict | neighbor | out */
  domainBucket?: "strict" | "neighbor" | "out";
  cluster: { label: string; percent?: number };
  onOpenDetails: (offerId: string) => void;
  onShortlist: (offerId: string) => void;
  onPass: (offerId: string) => void;
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
  SUPPLY_OPS:      "Supply / Ops",
  MARKETING_SALES: "Marketing / Sales",
  PROJECT_MGT:     "Chef de projet",
  HR:              "RH",
  SECURITY:        "Sécurité",
};

const ROLE_BLOCK_LABELS: Record<string, string> = {
  data_analytics: "Data / BI",
  business_analysis: "Business Analysis",
  finance_ops: "Finance Ops",
  legal_compliance: "Legal / Compliance",
  sales_business_dev: "Sales / BizDev",
  marketing_communication: "Marketing / Comms",
  hr_ops: "RH",
  supply_chain_ops: "Supply Chain",
  project_ops: "Project Ops",
  software_it: "Software / IT",
  generalist_other: "Polyvalent",
};

const GENERIC_SIGNAL_LABELS = new Set([
  "communication",
  "collaboration",
  "leadership",
  "problem solving",
  "gestion de projet",
  "project management",
  "decision making",
  "teamwork",
  "organisation",
]);

function normalizeSignalLabel(value: string): string {
  return value.trim().toLowerCase();
}

function selectVisibleSignals(items: string[], limit: number): string[] {
  const unique: string[] = [];
  const seen = new Set<string>();

  for (const item of items) {
    const cleaned = item.trim();
    if (!cleaned) continue;
    const key = normalizeSignalLabel(cleaned);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(cleaned);
  }

  const specific = unique.filter((item) => !GENERIC_SIGNAL_LABELS.has(normalizeSignalLabel(item)));
  const generic = unique.filter((item) => GENERIC_SIGNAL_LABELS.has(normalizeSignalLabel(item)));
  return [...specific, ...generic].slice(0, limit);
}

function formatClusterLabel(raw: string): string {
  return CLUSTER_LABELS[raw.toUpperCase()] ?? raw;
}

function formatRoleBlockLabel(raw?: string | null): string | null {
  if (!raw) return null;
  return ROLE_BLOCK_LABELS[raw] ?? raw;
}

function domainBadge(bucket?: "strict" | "neighbor" | "out") {
  if (bucket === "strict") {
    return {
      label: "Domaine direct",
      className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    };
  }
  if (bucket === "neighbor") {
    return {
      label: "Domaine proche",
      className: "bg-amber-50 text-amber-700 border-amber-200",
    };
  }
  if (bucket === "out") {
    return {
      label: "Hors domaine",
      className: "bg-slate-100 text-slate-600 border-slate-200",
    };
  }
  return null;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function InboxCardV2({
  offerId,
  company,
  title,
  location,
  score,
  explanation,
  semanticExplainability,
  scoringV2,
  offerIntelligence,
  domainBucket,
  cluster,
  onOpenDetails,
  onShortlist,
  onPass,
}: InboxCardV2Props) {
  const clusterDisplay = formatClusterLabel(cluster.label);
  const hasPercent = typeof cluster.percent === "number";
  const domain = domainBadge(domainBucket);
  const scoreLabel = typeof explanation.score === "number" ? explanation.score : score;
  const fitLabel = explanation.fit_label;
  const semanticSummary = semanticExplainability?.alignment_summary;
  const summaryReason = semanticSummary ?? explanation.summary_reason;
  const visibleStrengths = selectVisibleSignals(explanation.strengths, 4);
  const visibleGaps = selectVisibleSignals(
    explanation.blockers.length > 0 ? explanation.blockers : explanation.gaps,
    3
  );
  const semanticMatchedSignals = selectVisibleSignals(
    semanticExplainability?.signal_alignment?.matched_signals ?? [],
    3
  );
  const semanticMissingSignals = selectVisibleSignals(
    semanticExplainability?.signal_alignment?.missing_core_signals ?? [],
    2
  );
  const primaryNextAction = explanation.next_actions[0];
  const roleSignal = offerIntelligence?.dominant_role_block
    ? formatRoleBlockLabel(offerIntelligence.dominant_role_block)
    : cluster.label && cluster.label !== "—"
      ? clusterDisplay
      : null;
  const roleDomains = offerIntelligence?.dominant_domains?.slice(0, 2) ?? [];
  const visibleOfferSignals = selectVisibleSignals(
    offerIntelligence?.top_offer_signals?.length
      ? offerIntelligence.top_offer_signals
      : offerIntelligence?.required_skills ?? [],
    3
  );
  const offerSummary = offerIntelligence?.offer_summary;
  const missingLabel = explanation.blockers.length > 0 ? "Blocages" : "À combler";
  const semanticAlignment = semanticExplainability?.role_alignment?.alignment;
  const roleAlignmentValue = scoringV2?.components?.role_alignment;
  const scoringV2Pct =
    typeof scoringV2?.score_pct === "number"
      ? scoringV2.score_pct
      : typeof scoringV2?.score === "number"
        ? Math.round(scoringV2.score * 100)
        : null;
  const scoringV2Label =
    typeof roleAlignmentValue === "number" && roleAlignmentValue >= 0.8
      ? "Alignement métier fort"
      : typeof roleAlignmentValue === "number" && roleAlignmentValue >= 0.5
        ? "Alignement métier moyen"
        : typeof roleAlignmentValue === "number"
          ? "Alignement métier faible"
          : null;
  const semanticAlignmentLabel =
    semanticAlignment === "high"
      ? "Alignement fort"
      : semanticAlignment === "medium"
        ? "Alignement moyen"
        : semanticAlignment === "low"
          ? "Alignement faible"
          : null;
  const semanticAlignmentTone =
    semanticAlignment === "high"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : semanticAlignment === "medium"
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-slate-100 text-slate-600 border-slate-200";
  const fitTone =
    score > 75
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : score >= 50
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-rose-50 text-rose-700 border-rose-200";

  return (
    <article
      className="group flex h-full cursor-pointer flex-col rounded-[1.75rem] border border-slate-200/80 bg-white/95 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.08)] transition-all hover:-translate-y-0.5 hover:shadow-[0_22px_55px_rgba(15,23,42,0.12)] hover:ring-1 hover:ring-slate-300 focus-within:ring-2 focus-within:ring-slate-400"
      onClick={() => onOpenDetails(offerId)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onOpenDetails(offerId); }}
      tabIndex={0}
    >
      {/* ── Block A: Identity + Score ───────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {domain && (
              <span
                className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${domain.className}`}
              >
                {domain.label}
              </span>
            )}
            {roleSignal && (
              <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-600">
                {roleSignal}
                {hasPercent && <span className="font-normal text-slate-400"> · {cluster.percent}%</span>}
              </span>
            )}
          </div>
          <h3 className="line-clamp-2 text-[1.02rem] font-semibold leading-snug text-slate-950">
            {title}
          </h3>
          <p className="mt-1 text-xs text-slate-500 line-clamp-1">
            {[company, location].filter(Boolean).join(" · ")}
          </p>
        </div>

        {/* Score badge */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          <div
            className={`flex h-16 min-w-[4.25rem] flex-col items-center justify-center rounded-2xl ring-1 ${getScoreRingColor(score)}`}
          >
            <span className={`text-2xl font-bold leading-none tabular-nums ${getScoreColor(score)}`}>
              {score}
            </span>
            <span className="mt-0.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Match
            </span>
          </div>
        </div>
      </div>

      {/* ── Block C: Explanation signals ─────────────────────────────────── */}
      <div className="mt-4 rounded-[1.25rem] border border-sky-100 bg-sky-50/80 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">
          Lecture du match
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {semanticAlignmentLabel && (
            <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${semanticAlignmentTone}`}>
              {semanticAlignmentLabel}
            </span>
          )}
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${fitTone}`}>
            Fit {scoreLabel} · {fitLabel}
          </span>
        </div>
        {summaryReason && (
          <div className="mt-3 line-clamp-3 text-sm leading-relaxed text-slate-700">
            {summaryReason}
          </div>
        )}
        {scoringV2Pct !== null && (
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
            <span>Score métier: {scoringV2Pct}%</span>
            {scoringV2Label && <span>{scoringV2Label}</span>}
          </div>
        )}
        {semanticMatchedSignals.length > 0 && (
          <div className="mt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Signaux communs
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {semanticMatchedSignals.map((item) => (
                <span
                  key={`semantic-match-${offerId}-${item}`}
                  className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-medium text-emerald-800"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        )}
        {semanticMissingSignals.length > 0 && (
          <div className="mt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Ecart structurel
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {semanticMissingSignals.map((item) => (
                <span
                  key={`semantic-gap-${offerId}-${item}`}
                  className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-medium text-amber-900"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>
        )}
        {offerSummary && (
          <div className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-500">
            {offerSummary}
          </div>
        )}
      </div>

      {(visibleOfferSignals.length > 0 || roleDomains.length > 0) && (
        <div className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Ce que le poste est
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {roleDomains.map((item) => (
              <span
                key={`domain-${offerId}-${item}`}
                className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-[11px] font-medium text-sky-800"
              >
                {item}
              </span>
            ))}
            {visibleOfferSignals.map((item) => (
              <span
                key={`offer-signal-${offerId}-${item}`}
                className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-700"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {visibleStrengths.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            Points forts
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {visibleStrengths.map((item) => (
              <span
                key={`strength-${offerId}-${item}`}
                className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-medium text-emerald-800"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {visibleGaps.length > 0 && (
        <div className="mt-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {missingLabel}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {visibleGaps.map((item) => (
              <span
                key={`gap-${offerId}-${item}`}
                className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-medium text-amber-900"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {primaryNextAction && (
        <div className="mt-4 rounded-[1.15rem] border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
          <span className="font-semibold text-slate-800">Prochaine action: </span>
          {primaryNextAction}
        </div>
      )}

      {/* ── Actions ─────────────────────────────────────────────────────────── */}
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-5">
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onOpenDetails(offerId); }}
          className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:flex-none"
        >
          Voir détails
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onShortlist(offerId); }}
          className="flex-1 rounded-xl bg-slate-900 px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 sm:flex-none"
        >
          Shortlist
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onPass(offerId); }}
          className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-300 sm:flex-none"
        >
          Pass
        </button>
      </div>
    </article>
  );
}
