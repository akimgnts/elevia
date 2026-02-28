import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  Bug,
  Check,
  ChevronDown,
  FileText,
  Filter,
  Inbox,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import {
  fetchInbox,
  fetchOfferSemantic,
  fetchOfferContext,
  fetchProfileContext,
  fetchContextFit,
  postDecision,
  applyPack,
  type ApplyPackResponse,
  type ExplainBlock,
  type SkillExplainItem,
  type OfferSemanticResponse,
  type OfferContext,
  type ProfileContext,
  type ContextFit,
  type InboxMeta,
} from "../lib/api";
import { buildMatchingProfile, type SkillsSource } from "../lib/profileMatching";
import { upsertApplication, listApplications } from "../api/applications";
import { useProfileStore } from "../store/profileStore";
import { SEED_PROFILE } from "../fixtures/seedProfile";
import { OfferDetailModal, type OfferDetail } from "../components/OfferDetailModal";
import { formatRelativeDate } from "../lib/dateUtils";
import { cleanOfferTitle, truncateOfferTitle } from "../lib/titleUtils";

// ============================================================================
// Constants
// ============================================================================

const STORAGE_PREFIX = "elevia_inbox";
const DEFAULT_THRESHOLD = import.meta.env.DEV ? 0 : 65;
const THRESHOLD_OPTIONS = [0, 40, 50, 65, 75, 85];

// Debug mode: localStorage.setItem("elevia_debug_inbox", "1")
const DEBUG_INBOX = import.meta.env.DEV && localStorage.getItem("elevia_debug_inbox") === "1";

type DecisionStatus = "SHORTLISTED" | "DISMISSED";

type DecisionRecord = {
  status: DecisionStatus;
  score: number;
  updated_at: string;
};

type NormalizedInboxItem = {
  offer_id: string;
  id?: string;
  source?: string;
  title: string;
  company: string | null;
  country: string | null;
  city: string | null;
  publication_date?: string | null;
  score: number;
  score_pct?: number;
  score_raw?: number;
  reasons: string[];
  matched_skills: string[];
  missing_skills: string[];
  matched_skills_display: string[];
  missing_skills_display: string[];
  unmapped_tokens: string[];
  offer_uri_count?: number;
  profile_uri_count?: number;
  intersection_count?: number;
  scoring_unit?: string;
  description?: string | null;
  display_description?: string | null;
  description_snippet?: string;
  skills_display?: string[];
  strategy_summary?: {
    mission_summary?: string;
    distance?: string;
    action_guidance?: string;
  } | null;
  skills_uri_count?: number;
  skills_uri_collapsed_dupes?: number;
  skills_unmapped_count?: number;
  rome: { rome_code: string; rome_label: string } | null;
  is_vie?: boolean;
  skills_source?: string;
  explain: ExplainBlock | null;
  offer_cluster?: string;
  signal_score?: number;
  coherence?: "ok" | "suspicious";
};

type LastApiCall = {
  timestamp: string;
  profile_id: string;
  min_score: number;
  limit: number;
  response_items: number;
  total_matched: number;
  total_decided: number;
};

// ============================================================================
// Helpers
// ============================================================================

function storageKey(profileId: string, suffix: string) {
  return `${STORAGE_PREFIX}_${profileId}_${suffix}`;
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value));
}

function normalizeScore(value: unknown): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  const scaled = value >= 0 && value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(scaled)));
}

function cleanDescriptionSnippet(value?: string | null, maxLen = 180): string {
  if (!value) return "";
  const stripped = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (stripped.length <= maxLen) return stripped;
  return `${stripped.slice(0, maxLen).trim()}…`;
}

function formatRoleType(role?: OfferContext["role_type"]) {
  switch (role) {
    case "BI_REPORTING":
      return "BI/Reporting";
    case "DATA_ANALYSIS":
      return "Data Analysis";
    case "DATA_ENGINEERING":
      return "Data Engineering";
    case "PRODUCT_ANALYTICS":
      return "Product Analytics";
    case "OPS_ANALYTICS":
      return "Ops Analytics";
    case "MIXED":
      return "Mixte";
    default:
      return null;
  }
}

function formatCluster(cluster?: string | null) {
  switch (cluster) {
    case "DATA_IT":
      return "Data/IT";
    case "FINANCE_LEGAL":
      return "Finance/Juridique";
    case "SUPPLY_OPS":
      return "Supply/Ops";
    case "MARKETING_SALES":
      return "Marketing/Vente";
    case "ENGINEERING_INDUSTRY":
      return "Ingénierie/Industrie";
    case "ADMIN_HR":
      return "Admin/RH";
    case "OTHER":
      return "Autre";
    default:
      return null;
  }
}

/**
 * Strict mapping from API response to UI model.
 * Uses offer_id (not id), safe nulls for all fields.
 */
function normalizeInboxItems(raw: unknown): NormalizedInboxItem[] {
  if (!Array.isArray(raw)) {
    console.warn("[inbox] API items is not an array:", typeof raw);
    return [];
  }
  const results: NormalizedInboxItem[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    // CRITICAL: use offer_id, fallback to id
    const offerId = (rec.offer_id || rec.id) as string | undefined;
    if (!offerId) {
      console.warn("[inbox] Item missing offer_id:", rec);
      continue;
    }
    const matchedDisplay = Array.isArray(rec.matched_skills_display)
      ? (rec.matched_skills_display as string[])
      : Array.isArray(rec.matched_skills)
        ? (rec.matched_skills as string[])
        : [];
    const missingDisplay = Array.isArray(rec.missing_skills_display)
      ? (rec.missing_skills_display as string[])
      : Array.isArray(rec.missing_skills)
        ? (rec.missing_skills as string[])
        : [];

    results.push({
      offer_id: offerId,
      id: typeof rec.id === "string" ? rec.id : undefined,
      source: typeof rec.source === "string" ? rec.source : undefined,
      title: typeof rec.title === "string" ? rec.title : "Offre",
      company: typeof rec.company === "string" ? rec.company : null,
      country: typeof rec.country === "string" ? rec.country : null,
      city: typeof rec.city === "string" ? rec.city : null,
      publication_date: typeof rec.publication_date === "string" ? rec.publication_date : null,
      score: normalizeScore(
        typeof rec.score_pct === "number"
          ? rec.score_pct
          : typeof rec.score === "number"
            ? rec.score
            : rec.match_score
      ),
      score_pct: typeof rec.score_pct === "number" ? rec.score_pct : undefined,
      score_raw: typeof rec.score_raw === "number" ? rec.score_raw : undefined,
      reasons: Array.isArray(rec.reasons) ? (rec.reasons as string[]) : [],
      matched_skills: Array.isArray(rec.matched_skills) ? (rec.matched_skills as string[]) : [],
      missing_skills: Array.isArray(rec.missing_skills) ? (rec.missing_skills as string[]) : [],
      matched_skills_display: matchedDisplay,
      missing_skills_display: missingDisplay,
      unmapped_tokens: Array.isArray(rec.unmapped_tokens) ? (rec.unmapped_tokens as string[]) : [],
      offer_uri_count:
        typeof rec.offer_uri_count === "number"
          ? rec.offer_uri_count
          : typeof rec.skills_uri_count === "number"
            ? rec.skills_uri_count
            : undefined,
      profile_uri_count: typeof rec.profile_uri_count === "number" ? rec.profile_uri_count : undefined,
      intersection_count:
        typeof rec.intersection_count === "number" ? rec.intersection_count : matchedDisplay.length,
      scoring_unit: typeof rec.scoring_unit === "string" ? rec.scoring_unit : undefined,
      description: typeof rec.description === "string" ? rec.description : null,
      display_description: typeof rec.display_description === "string" ? rec.display_description : null,
      description_snippet:
        typeof rec.description_snippet === "string" && rec.description_snippet.trim()
          ? rec.description_snippet
          : cleanDescriptionSnippet(
              typeof rec.display_description === "string"
                ? rec.display_description
                : typeof rec.description === "string"
                  ? rec.description
                  : null
            ),
      skills_display: Array.isArray(rec.skills_display) ? (rec.skills_display as string[]) : undefined,
      strategy_summary:
        rec.strategy_summary && typeof rec.strategy_summary === "object"
          ? (rec.strategy_summary as {
              mission_summary?: string;
              distance?: string;
              action_guidance?: string;
            })
          : null,
      skills_uri_count: typeof rec.skills_uri_count === "number" ? rec.skills_uri_count : undefined,
      skills_uri_collapsed_dupes:
        typeof rec.skills_uri_collapsed_dupes === "number" ? rec.skills_uri_collapsed_dupes : undefined,
      skills_unmapped_count:
        typeof rec.skills_unmapped_count === "number" ? rec.skills_unmapped_count : undefined,
      rome: rec.rome && typeof rec.rome === "object" ? (rec.rome as { rome_code: string; rome_label: string }) : null,
      is_vie: typeof rec.is_vie === "boolean" ? rec.is_vie : undefined,
      skills_source: typeof rec.skills_source === "string" ? rec.skills_source : undefined,
      explain: rec.explain && typeof rec.explain === "object" ? (rec.explain as ExplainBlock) : null,
      offer_cluster: typeof rec.offer_cluster === "string" ? rec.offer_cluster : undefined,
      signal_score: typeof rec.signal_score === "number" ? rec.signal_score : undefined,
      coherence: rec.coherence === "ok" || rec.coherence === "suspicious" ? rec.coherence : undefined,
    });
  }
  return results;
}

// ============================================================================
// Components
// ============================================================================

function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
      <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-slate-400" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-500 max-w-md mb-6">{description}</p>
      {actions}
    </div>
  );
}

// ── WhyThisScore panel ─────────────────────────────────────────────────────────

function SkillPill({ item }: { item: SkillExplainItem }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-slate-100 text-slate-700">
      {item.label}
      {item.weighted && (
        <span className="rounded px-1 bg-amber-50 text-amber-700 ring-1 ring-amber-200 font-semibold text-[9px]">
          pondérée
        </span>
      )}
    </span>
  );
}

function WhyThisScore({ explain, score, matchedCount, missingCount }: {
  explain: ExplainBlock | null;
  score: number;
  matchedCount: number;
  missingCount: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showAllMatched, setShowAllMatched] = useState(false);
  const [showAllMissing, setShowAllMissing] = useState(false);

  if (!explain) {
    return (
      <div className="mt-3 text-[11px] text-slate-400">
        Explication non disponible.
      </div>
    );
  }

  const { breakdown, matched_display, missing_display, matched_full, missing_full } = explain;

  const matchedList = showAllMatched ? matched_full : matched_display;
  const missingList = showAllMissing ? missing_full : missing_display;

  return (
    <div className="mt-3 border-t border-slate-100 pt-3">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between text-left text-[11px] font-semibold text-slate-500 hover:text-slate-700 transition"
      >
        <span>Pourquoi ce score ?</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`} />
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 text-[11px]">

          {/* A: Résumé */}
          <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-slate-600">
            <span>Score <strong className="text-slate-900">{score}</strong></span>
            <span>Matchées <strong className="text-emerald-700">{matchedCount}</strong></span>
            <span>Manquantes <strong className="text-rose-600">{missingCount}</strong></span>
          </div>
          {score === 100 && missingCount === 0 && (
            <div className="text-[10px] text-emerald-700">
              100% = toutes les compétences ESCO alignées + critères langue/formation/pays OK.
            </div>
          )}
          {score === 100 && missingCount > 0 && (
            <div className="text-[10px] text-slate-500">
              Score arrondi (total {breakdown.total.toFixed(1)} / 100).
            </div>
          )}

          {/* B: Ce qui fait monter le score */}
          {matchedList.length > 0 && (
            <div>
              <div className="mb-1.5 font-semibold text-emerald-700">Ce qui fait monter le score</div>
              <div className="flex flex-wrap gap-1">
                {matchedList.map((s) => (
                  <SkillPill key={s.label} item={s} />
                ))}
              </div>
              {!showAllMatched && matched_full.length > matched_display.length && (
                <button
                  onClick={() => setShowAllMatched(true)}
                  className="mt-1 text-[10px] text-cyan-600 hover:underline"
                >
                  Voir tout ({matched_full.length})
                </button>
              )}
              {showAllMatched && matched_full.length > matched_display.length && (
                <button
                  onClick={() => setShowAllMatched(false)}
                  className="mt-1 text-[10px] text-slate-400 hover:underline"
                >
                  Réduire
                </button>
              )}
            </div>
          )}

          {/* C: Ce qui manque vraiment */}
          {missingList.length > 0 && (
            <div>
              <div className="mb-1.5 font-semibold text-rose-600">Ce qui manque vraiment</div>
              <div className="flex flex-wrap gap-1">
                {missingList.map((s) => (
                  <span
                    key={s.label}
                    className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium bg-rose-50 text-rose-700"
                  >
                    {s.label}
                    {s.weighted && (
                      <span className="rounded px-1 bg-amber-50 text-amber-700 ring-1 ring-amber-200 font-semibold text-[9px]">
                        pondérée
                      </span>
                    )}
                  </span>
                ))}
              </div>
              {!showAllMissing && missing_full.length > missing_display.length && (
                <button
                  onClick={() => setShowAllMissing(true)}
                  className="mt-1 text-[10px] text-cyan-600 hover:underline"
                >
                  Voir tout ({missing_full.length})
                </button>
              )}
              {showAllMissing && missing_full.length > missing_display.length && (
                <button
                  onClick={() => setShowAllMissing(false)}
                  className="mt-1 text-[10px] text-slate-400 hover:underline"
                >
                  Réduire
                </button>
              )}
            </div>
          )}

          {/* D: Transparence — breakdown */}
          <div className="rounded-lg bg-slate-50 px-3 py-2 space-y-1">
            <div className="font-semibold text-slate-500 mb-1">Détail du score</div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Compétences ({breakdown.skills_weight}%)</span>
              <span className="font-medium text-slate-800">{breakdown.skills_score.toFixed(1)} pts</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">
                Langues ({breakdown.language_weight}%)
                {breakdown.language_match && <span className="ml-1 text-emerald-600">✓</span>}
              </span>
              <span className="font-medium text-slate-800">{breakdown.language_score.toFixed(1)} pts</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">
                Formation ({breakdown.education_weight}%)
                {breakdown.education_match && <span className="ml-1 text-emerald-600">✓</span>}
              </span>
              <span className="font-medium text-slate-800">{breakdown.education_score.toFixed(1)} pts</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">
                Pays ({breakdown.country_weight}%)
                {breakdown.country_match && <span className="ml-1 text-emerald-600">✓</span>}
              </span>
              <span className="font-medium text-slate-800">{breakdown.country_score.toFixed(1)} pts</span>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}

function OfferCard({
  offer,
  onShortlist,
  onDismiss,
  onApply,
  onOpen,
  isShortlisted,
  isPending,
  roleTypeLabel,
}: {
  offer: NormalizedInboxItem;
  onShortlist: () => void;
  onDismiss: () => void;
  onApply: () => void;
  onOpen: () => void;
  isShortlisted: boolean;
  isPending: boolean;
  roleTypeLabel?: string | null;
}) {
  const matchedDisplay = offer.matched_skills_display;
  const missingDisplay = offer.missing_skills_display;
  const unmapped = offer.unmapped_tokens;
  const showFallback = offer.score === 15 && matchedDisplay.length === 0;
  const scoreBadgeClass =
    offer.score >= 75
      ? "bg-emerald-50 text-emerald-700 border-emerald-100"
      : offer.score >= 60
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-slate-100 text-slate-600 border-slate-200";
  const scoreLabel = `Score ${offer.score}%`;
  const relativeDate = offer.publication_date
    ? formatRelativeDate(offer.publication_date)
    : null;
  const showVie = offer.source === "business_france" || offer.is_vie;
  const clusterLabel = formatCluster(offer.offer_cluster);
  const signalLabel =
    typeof offer.signal_score === "number" ? `Signal ${offer.signal_score.toFixed(1)}` : null;
  const isSuspicious = offer.coherence === "suspicious";
  const titleInfo = useMemo(() => cleanOfferTitle(offer.title), [offer.title]);
  const displayTitle = truncateOfferTitle(titleInfo.display, 90);
  const freshnessBadge =
    relativeDate?.freshness === "new"
      ? "Nouveau"
      : relativeDate?.freshness === "recent"
        ? "Récent"
        : null;
  const uriSummary =
    typeof offer.intersection_count === "number" && typeof offer.offer_uri_count === "number"
      ? `${offer.intersection_count} compétences reconnues sur ${offer.offer_uri_count}`
      : null;

  return (
    <div
      className={`group bg-white border border-slate-100 rounded-[2rem] p-5 shadow-sm hover:shadow-lg transition-all flex flex-col h-full ${isPending ? "opacity-50 pointer-events-none" : ""}`}
      onClick={onOpen}
      onKeyDown={(e) => { if (e.key === "Enter") onOpen(); }}
      role="button"
      tabIndex={0}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 flex-1 text-base font-bold text-slate-900 leading-tight line-clamp-2">
          {displayTitle}
        </h3>
        <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${scoreBadgeClass}`}>
          {scoreLabel}
        </span>
      </div>

      {/* Badges */}
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
        {offer.country && (
          <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            {offer.country}
          </span>
        )}
        {offer.city && (
          <span className="px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
            {offer.city}
          </span>
        )}
        {showVie && (
          <span className="px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
            VIE
          </span>
        )}
        {offer.company && (
          <span className="px-2.5 py-1 rounded-full border border-slate-200 text-slate-600">
            {offer.company}
          </span>
        )}
        {clusterLabel && (
          <span className="px-2.5 py-1 rounded-full bg-slate-900 text-white border border-slate-800">
            {clusterLabel}
          </span>
        )}
        {signalLabel && (
          <span className="px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
            {signalLabel}
          </span>
        )}
        {isSuspicious && (
          <span className="px-2.5 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            Incohérent
          </span>
        )}
        {relativeDate && (
          <span className="px-2.5 py-1 rounded-full bg-slate-50 text-slate-500 border border-slate-100">
            {relativeDate.label}
          </span>
        )}
        {freshnessBadge && (
          <span
            className={`px-2 py-1 rounded-full text-[10px] font-semibold border ${
              relativeDate?.freshness === "new"
                ? "bg-rose-50 text-rose-700 border-rose-200"
                : "bg-amber-50 text-amber-700 border-amber-200"
            }`}
          >
            {freshnessBadge}
          </span>
        )}
        {showFallback && (
          <span className="px-2 py-1 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            Fallback score
          </span>
        )}
        {roleTypeLabel && (
          <span className="px-2 py-1 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            {roleTypeLabel}
          </span>
        )}
      </div>

      {offer.description_snippet && (
        <p className="mt-3 text-xs text-slate-500 leading-relaxed line-clamp-3">
          {offer.description_snippet}
        </p>
      )}

      {/* Matched Skills (top 3) */}
      {matchedDisplay.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {matchedDisplay.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100"
            >
              {skill}
            </span>
          ))}
          {matchedDisplay.length > 3 && (
            <span className="text-[10px] text-slate-400">+{matchedDisplay.length - 3}</span>
          )}
        </div>
      ) : (
        <div className="mt-4 text-[11px] text-slate-500">
          Aucune compétence détectée en commun
        </div>
      )}

      {missingDisplay.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {missingDisplay.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-100"
            >
              {skill}
            </span>
          ))}
          {missingDisplay.length > 3 && (
            <span className="text-[10px] text-slate-400">+{missingDisplay.length - 3}</span>
          )}
        </div>
      )}

      {DEBUG_INBOX && unmapped.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {unmapped.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200"
            >
              {skill}
            </span>
          ))}
          {unmapped.length > 3 && (
            <span className="text-[10px] text-slate-400">+{unmapped.length - 3}</span>
          )}
          <span className="text-[10px] text-slate-400">Non mappées ESCO</span>
        </div>
      )}

      {uriSummary && (
        <div className="mt-2 text-[11px] text-slate-500">
          {uriSummary}
        </div>
      )}

      {DEBUG_INBOX && (
        <div className="mt-2 text-[10px] text-slate-400">
          Compétences (URIs): {offer.skills_uri_count ?? "—"} | Doublons collapse:{" "}
          {offer.skills_uri_collapsed_dupes ?? "—"} | Non mappées: {offer.skills_unmapped_count ?? "—"}
        </div>
      )}

      {/* Reasons */}
      {offer.reasons.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {offer.reasons.slice(0, 2).map((reason, idx) => (
            <div key={idx} className="flex items-start gap-2 text-xs text-slate-600">
              <Check className="mt-0.5 w-3 h-3 text-emerald-500 shrink-0" />
              <span className="line-clamp-1">{reason}</span>
            </div>
          ))}
        </div>
      )}

      {/* Why this score — collapsible */}
      <WhyThisScore
        explain={offer.explain}
        score={offer.score}
        matchedCount={matchedDisplay.length}
        missingCount={missingDisplay.length}
      />

      {/* Actions */}
      <div className="mt-auto pt-4 flex flex-wrap items-center gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onApply(); }}
          className="px-4 py-2 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition"
        >
          Générer
        </button>

        <button
          onClick={(e) => { e.stopPropagation(); onShortlist(); }}
          disabled={isShortlisted}
          className={`px-4 py-2 rounded-xl text-sm font-semibold transition ${
            isShortlisted
              ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
              : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
          }`}
        >
          {isShortlisted ? "Shortlisté" : "Shortlist"}
        </button>

        <button
          onClick={(e) => { e.stopPropagation(); onDismiss(); }}
          className="ml-auto px-4 py-2 rounded-xl text-sm font-semibold bg-slate-50 border border-slate-100 text-slate-600 hover:bg-slate-100 transition"
        >
          Écarter
        </button>
      </div>
    </div>
  );
}

function FilterBar({
  threshold,
  onThresholdChange,
  searchQuery,
  onSearchChange,
  onReset,
  onShowAll,
  domainMode,
  onDomainModeChange,
  suggestOutOfDomain,
  sortMode,
  onSortChange,
  receivedCount,
  displayedCount,
  maskedCount,
  hasActiveFilters,
}: {
  threshold: number;
  onThresholdChange: (value: number) => void;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onReset: () => void;
  onShowAll: () => void;
  domainMode: "in_domain" | "all";
  onDomainModeChange: (value: "in_domain" | "all") => void;
  suggestOutOfDomain: boolean;
  sortMode: "score" | "recent" | "oldest";
  onSortChange: (value: "score" | "recent" | "oldest") => void;
  receivedCount: number;
  displayedCount: number;
  maskedCount: number;
  hasActiveFilters: boolean;
}) {
  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-4 shadow-sm space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Filtrer par ville, pays, titre..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-100 rounded-xl text-sm text-slate-700 placeholder-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500/30 outline-none transition"
          />
          {searchQuery && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Domain mode */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Domaine</span>
          <select
            value={domainMode}
            onChange={(e) => onDomainModeChange(e.target.value as "in_domain" | "all")}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
          >
            <option value="in_domain">Dans mon domaine</option>
            <option value="all">Voir hors domaine</option>
          </select>
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Trier par</span>
          <select
            value={sortMode}
            onChange={(e) => onSortChange(e.target.value as "score" | "recent" | "oldest")}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none"
          >
            <option value="score">Score (desc)</option>
            <option value="recent">Plus récent</option>
            <option value="oldest">Plus ancien</option>
          </select>
        </div>

        {/* Threshold Pills */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs text-slate-500 font-medium hidden sm:inline">Seuil:</span>
          <div className="flex bg-slate-100 p-1 rounded-xl">
            {THRESHOLD_OPTIONS.map((opt) => (
              <button
                key={opt}
                onClick={() => onThresholdChange(opt)}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition ${
                  threshold === opt
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                {opt === 0 ? "Tous" : `${opt}%`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Counters + Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-4">
          <span className="text-slate-500">
            Reçues: <strong className="text-slate-900">{receivedCount}</strong>
          </span>
          <span className="text-slate-500">
            Affichées: <strong className="text-emerald-700">{displayedCount}</strong>
          </span>
          {maskedCount > 0 && (
            <span className="text-slate-500">
              Masquées: <strong className="text-amber-600">{maskedCount}</strong>
            </span>
          )}
          {suggestOutOfDomain && (
            <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[10px] font-medium">
              Résultats limités — activer Hors domaine
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {hasActiveFilters && (
            <>
              <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-[10px] font-medium">
                Filtres actifs
              </span>
              <button
                onClick={onReset}
                className="text-xs text-rose-600 hover:text-rose-700 font-medium"
              >
                Réinitialiser
              </button>
              <button
                onClick={onShowAll}
                className="text-xs text-emerald-600 hover:text-emerald-700 font-medium"
              >
                Tout afficher
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function DebugDrawer({
  isOpen,
  onClose,
  items,
  displayedCount,
  threshold,
  searchQuery,
  lastApiCall,
  skillsSource,
}: {
  isOpen: boolean;
  onClose: () => void;
  items: NormalizedInboxItem[];
  displayedCount: number;
  threshold: number;
  searchQuery: string;
  lastApiCall: LastApiCall | null;
  skillsSource: SkillsSource;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed bottom-4 right-4 w-80 bg-slate-900 text-slate-100 rounded-xl shadow-2xl p-4 text-xs font-mono z-50">
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-emerald-400">Debug Inbox</span>
        <button onClick={onClose} className="text-slate-400 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-2">
        <div>
          <span className="text-slate-400">items.length:</span>{" "}
          <span className="text-white">{items.length}</span>
        </div>
        <div>
          <span className="text-slate-400">displayed:</span>{" "}
          <span className="text-white">{displayedCount}</span>
        </div>
        <div>
          <span className="text-slate-400">threshold:</span>{" "}
          <span className="text-white">{threshold}</span>
        </div>
        <div>
          <span className="text-slate-400">search:</span>{" "}
          <span className="text-white">{searchQuery || "(empty)"}</span>
        </div>
        <div>
          <span className="text-slate-400">skillsSource:</span>{" "}
          <span className="text-white">{skillsSource}</span>
        </div>

        {lastApiCall && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <div className="text-slate-400 mb-1">Last API call:</div>
            <div>profile_id: {lastApiCall.profile_id.slice(0, 12)}...</div>
            <div>min_score: {lastApiCall.min_score}</div>
            <div>limit: {lastApiCall.limit}</div>
            <div>response_items: {lastApiCall.response_items}</div>
            <div>total_matched: {lastApiCall.total_matched}</div>
            <div>total_decided: {lastApiCall.total_decided}</div>
          </div>
        )}

        {items.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <div className="text-slate-400 mb-1">First 3 items:</div>
            {items.slice(0, 3).map((item) => (
              <div key={item.offer_id} className="text-[10px] truncate">
                {item.offer_id.slice(0, 8)}... | score={item.score}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function InboxPage() {
  const { userProfile, profileHash, setUserProfile } = useProfileStore();
  const [items, setItems] = useState<NormalizedInboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skillsSource, setSkillsSource] = useState<SkillsSource>("none");
  const [profileIncomplete, setProfileIncomplete] = useState(false);
  const [domainMode, setDomainMode] = useState<"in_domain" | "all">("in_domain");
  const [inboxMeta, setInboxMeta] = useState<InboxMeta | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [threshold, setThreshold] = useState<number>(() => {
    const stored = readJson<number | null>(`${STORAGE_PREFIX}_threshold`, null);
    return typeof stored === "number" ? stored : DEFAULT_THRESHOLD;
  });
  const [sortMode, setSortMode] = useState<"score" | "recent" | "oldest">("score");
  const [decisions, setDecisions] = useState<Record<string, DecisionRecord>>({});
  const [pendingDecisions, setPendingDecisions] = useState<Set<string>>(new Set());
  const [trackerStatusMap, setTrackerStatusMap] = useState<Record<string, string>>({});
  const [lastApiCall, setLastApiCall] = useState<LastApiCall | null>(null);
  const [debugOpen, setDebugOpen] = useState(DEBUG_INBOX);
  const loadedRef = useRef(false);

  // Apply Pack modal state
  const [applyPackOffer, setApplyPackOffer] = useState<NormalizedInboxItem | null>(null);
  const [applyPackResult, setApplyPackResult] = useState<ApplyPackResponse | null>(null);
  const [applyPackLoading, setApplyPackLoading] = useState(false);
  const [applyPackError, setApplyPackError] = useState<string | null>(null);
  const [applyPackTab, setApplyPackTab] = useState<"cv" | "letter">("cv");
  const [selectedOffer, setSelectedOffer] = useState<OfferDetail | null>(null);
  const [semanticByOfferId, setSemanticByOfferId] = useState<Record<string, OfferSemanticResponse>>({});
  const [semanticLoadingIds, setSemanticLoadingIds] = useState<Set<string>>(new Set());
  const [offerContextById, setOfferContextById] = useState<Record<string, OfferContext>>({});
  const [profileContext, setProfileContext] = useState<ProfileContext | null>(null);
  const [profileContextLoading, setProfileContextLoading] = useState(false);
  const [contextFitByOfferId, setContextFitByOfferId] = useState<Record<string, ContextFit>>({});
  const [contextLoadingIds, setContextLoadingIds] = useState<Set<string>>(new Set());
  const [contextFitLoadingIds, setContextFitLoadingIds] = useState<Set<string>>(new Set());
  const [contextErrorByOfferId, setContextErrorByOfferId] = useState<Record<string, string>>({});

  const profileId = profileHash ?? "anonymous";
  const selectedOfferId = selectedOffer?.offer_id || selectedOffer?.id;
  const selectedSemantic = selectedOfferId ? semanticByOfferId[selectedOfferId] : undefined;
  const selectedOfferContext = selectedOfferId ? offerContextById[selectedOfferId] : undefined;
  const selectedContextFit = selectedOfferId ? contextFitByOfferId[selectedOfferId] : undefined;
  const contextLoading =
    profileContextLoading ||
    (selectedOfferId ? contextLoadingIds.has(selectedOfferId) || contextFitLoadingIds.has(selectedOfferId) : false);
  const contextError = selectedOfferId ? contextErrorByOfferId[selectedOfferId] : null;

  useEffect(() => {
    if (!selectedOffer) return;
    const offerId = selectedOffer.offer_id || selectedOffer.id;
    if (!offerId) return;
    if (semanticByOfferId[offerId] || semanticLoadingIds.has(offerId)) return;

    setSemanticLoadingIds((prev) => new Set(prev).add(offerId));
    fetchOfferSemantic(offerId, profileId)
      .then((data) => {
        setSemanticByOfferId((prev) => ({ ...prev, [offerId]: data }));
      })
      .catch((err) => {
        if (import.meta.env.DEV) {
          console.warn("[inbox] semantic fetch failed:", err);
        }
        setSemanticByOfferId((prev) => ({
          ...prev,
          [offerId]: {
            offer_id: offerId,
            semantic_score: null,
            semantic_model_version: null,
            relevant_passages: [],
            ai_available: false,
            ai_error: "embeddings_unavailable",
          },
        }));
      })
      .finally(() => {
        setSemanticLoadingIds((prev) => {
          const next = new Set(prev);
          next.delete(offerId);
          return next;
        });
      });
  }, [selectedOffer, profileId, semanticByOfferId, semanticLoadingIds]);

  useEffect(() => {
    if (!userProfile || !profileId) return;
    setProfileContextLoading(true);
    fetchProfileContext(profileId, userProfile)
      .then((data) => {
        setProfileContext(data);
      })
      .catch((err) => {
        if (import.meta.env.DEV) {
          console.warn("[inbox] profile context fetch failed:", err);
        }
        setProfileContext(null);
      })
      .finally(() => {
        setProfileContextLoading(false);
      });
  }, [userProfile, profileId]);

  useEffect(() => {
    if (!selectedOffer) return;
    const offerId = selectedOffer.offer_id || selectedOffer.id;
    if (!offerId) return;
    if (offerContextById[offerId] || contextLoadingIds.has(offerId)) return;

    const description =
      selectedOffer.description ||
      selectedOffer.display_description ||
      selectedOffer.description_snippet ||
      "";

    setContextLoadingIds((prev) => new Set(prev).add(offerId));
    fetchOfferContext(offerId, description)
      .then((data) => {
        setOfferContextById((prev) => ({ ...prev, [offerId]: data }));
      })
      .catch((err) => {
        if (import.meta.env.DEV) {
          console.warn("[inbox] offer context fetch failed:", err);
        }
        setContextErrorByOfferId((prev) => ({
          ...prev,
          [offerId]: "context_offer_failed",
        }));
      })
      .finally(() => {
        setContextLoadingIds((prev) => {
          const next = new Set(prev);
          next.delete(offerId);
          return next;
        });
      });
  }, [selectedOffer, offerContextById, contextLoadingIds]);

  useEffect(() => {
    if (!selectedOfferId || !profileContext) return;
    const offerContext = offerContextById[selectedOfferId];
    if (!offerContext) return;
    if (contextFitByOfferId[selectedOfferId] || contextFitLoadingIds.has(selectedOfferId)) return;

    const matched =
      selectedOffer?.matched_skills_display?.length
        ? selectedOffer.matched_skills_display
        : selectedOffer?.matched_skills || [];
    const missing =
      selectedOffer?.missing_skills_display?.length
        ? selectedOffer.missing_skills_display
        : selectedOffer?.missing_skills || [];

    setContextFitLoadingIds((prev) => new Set(prev).add(selectedOfferId));
    fetchContextFit(profileContext, offerContext, matched, missing)
      .then((data) => {
        setContextFitByOfferId((prev) => ({ ...prev, [selectedOfferId]: data }));
      })
      .catch((err) => {
        if (import.meta.env.DEV) {
          console.warn("[inbox] context fit fetch failed:", err);
        }
        setContextErrorByOfferId((prev) => ({
          ...prev,
          [selectedOfferId]: "context_fit_failed",
        }));
      })
      .finally(() => {
        setContextFitLoadingIds((prev) => {
          const next = new Set(prev);
          next.delete(selectedOfferId);
          return next;
        });
      });
  }, [
    selectedOfferId,
    selectedOffer,
    profileContext,
    offerContextById,
    contextFitByOfferId,
    contextFitLoadingIds,
  ]);

  // Persist threshold
  useEffect(() => {
    writeJson(`${STORAGE_PREFIX}_threshold`, threshold);
  }, [threshold]);

  // Load persisted decisions
  useEffect(() => {
    setDecisions(readJson<Record<string, DecisionRecord>>(storageKey(profileId, "decisions"), {}));
  }, [profileId]);

  // Persist decisions
  useEffect(() => {
    writeJson(storageKey(profileId, "decisions"), decisions);
  }, [decisions, profileId]);

  // Load inbox from API - APPROACH B: client filters, API min_score=0
  const load = useCallback(async () => {
    if (!userProfile) return;
    setLoading(true);
    setError(null);
    setProfileIncomplete(false);

    try {
      const { profile: matchingProfile, skillsSource: source, needsSeedHydration } = buildMatchingProfile(
        userProfile as Record<string, unknown>,
        profileId
      );

      setSkillsSource(source);

      // PROD: Block if no skills
      if (source === "none" && !import.meta.env.DEV) {
        setProfileIncomplete(true);
        setLoading(false);
        return;
      }

      // DEV: Hydrate with SEED_PROFILE if needed
      if (needsSeedHydration && import.meta.env.DEV) {
        console.warn("[inbox] Hydrating with SEED_PROFILE");
        await setUserProfile({ ...SEED_PROFILE, id: SEED_PROFILE.id });
        return;
      }

      // CRITICAL: Call API with min_score=0, let client filter
      const apiMinScore = 0;
      const apiLimit = 100;

      if (DEBUG_INBOX) {
        console.info("[inbox] Calling API with:", { profile_id: profileId, min_score: apiMinScore, limit: apiLimit });
      }

      const data = await fetchInbox(matchingProfile, profileId, apiMinScore, apiLimit, true, domainMode);

      setLastApiCall({
        timestamp: new Date().toISOString(),
        profile_id: profileId,
        min_score: apiMinScore,
        limit: apiLimit,
        response_items: Array.isArray(data.items) ? data.items.length : 0,
        total_matched: data.total_matched ?? 0,
        total_decided: data.total_decided ?? 0,
      });

      if (DEBUG_INBOX) {
        console.info("[inbox] API response:", {
          items_count: Array.isArray(data.items) ? data.items.length : "NOT_ARRAY",
          total_matched: data.total_matched,
          total_decided: data.total_decided,
          first_item: data.items?.[0],
        });
      }

      const normalized = normalizeInboxItems(data.items);
      setItems(normalized);
      setInboxMeta(data.meta ?? null);

      if (DEBUG_INBOX) {
        console.info("[inbox] Normalized items:", normalized.length);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur inconnue";
      setError(msg);
      console.error("[inbox] Load error:", e);
    } finally {
      setLoading(false);
    }
  }, [userProfile, profileId, setUserProfile, domainMode]);

  // Initial load
  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true;
      load();
    }
  }, [load]);

  useEffect(() => {
    if (loadedRef.current) {
      load();
    }
  }, [domainMode, load]);

  // Load tracker status
  useEffect(() => {
    const fetchTracker = async () => {
      try {
        const data = await listApplications();
        const nextMap: Record<string, string> = {};
        data.items.forEach((item) => {
          nextMap[item.offer_id] = item.status;
        });
        setTrackerStatusMap(nextMap);
      } catch (err) {
        console.warn("[inbox] tracker fetch failed:", err);
      }
    };
    fetchTracker();
  }, []);

  // ============================================================================
  // Filtering Logic - TRUTH FROM API ITEMS
  // ============================================================================

  // Received = what API returned
  const receivedCount = items.length;

  // Available = received minus already decided (local)
  const availableItems = useMemo(
    () => items.filter((item) => !decisions[item.offer_id]),
    [items, decisions]
  );

  // Displayed = available after threshold + search filters
  const displayedItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const getDateValue = (value?: string | null) => {
      if (!value) return 0;
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return 0;
      return parsed.getTime();
    };
    return availableItems
      .filter((item) => {
        // Threshold filter
        if (item.score < threshold) return false;
        // Search filter
        if (!query) return true;
        const searchable = [item.city, item.country, item.title, item.company]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return searchable.includes(query);
      })
      .sort((a, b) => {
        if (sortMode === "recent") {
          return getDateValue(b.publication_date) - getDateValue(a.publication_date);
        }
        if (sortMode === "oldest") {
          return getDateValue(a.publication_date) - getDateValue(b.publication_date);
        }
        if (b.score !== a.score) {
          return b.score - a.score;
        }
        const signalA = typeof a.signal_score === "number" ? a.signal_score : 0;
        const signalB = typeof b.signal_score === "number" ? b.signal_score : 0;
        if (signalB !== signalA) {
          return signalB - signalA;
        }
        const cohA = a.coherence === "suspicious" ? 0 : 1;
        const cohB = b.coherence === "suspicious" ? 0 : 1;
        return cohB - cohA;
      });
  }, [availableItems, threshold, searchQuery, sortMode]);

  const displayedCount = displayedItems.length;
  const maskedCount = receivedCount - displayedCount;
  const hasActiveFilters = threshold > 0 || searchQuery.trim() !== "";

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleDecision = async (offerId: string, status: DecisionStatus, score: number) => {
    // Optimistic update
    setPendingDecisions((prev) => new Set(prev).add(offerId));
    setDecisions((prev) => ({
      ...prev,
      [offerId]: { status, score, updated_at: new Date().toISOString() },
    }));

    try {
      await postDecision(offerId, profileId, status);
    } catch (err) {
      // Rollback on error
      console.error("[inbox] Decision failed, rolling back:", err);
      setDecisions((prev) => {
        const next = { ...prev };
        delete next[offerId];
        return next;
      });
    } finally {
      setPendingDecisions((prev) => {
        const next = new Set(prev);
        next.delete(offerId);
        return next;
      });
    }
  };

  const handleShortlist = async (offerId: string, score: number) => {
    await handleDecision(offerId, "SHORTLISTED", score);

    // Also persist to tracker
    if (!trackerStatusMap[offerId]) {
      try {
        await upsertApplication({
          offer_id: offerId,
          status: "shortlisted",
          note: null,
          next_follow_up_date: null,
        });
        setTrackerStatusMap((prev) => ({ ...prev, [offerId]: "shortlisted" }));
      } catch (err) {
        console.warn("[inbox] shortlist tracker failed:", err);
      }
    }
  };

  const handleApply = async (item: NormalizedInboxItem) => {
    setApplyPackOffer(item);
    setApplyPackResult(null);
    setApplyPackError(null);
    setApplyPackTab("cv");
    setApplyPackLoading(true);

    try {
      const profileSkills: string[] = Array.isArray((userProfile as Record<string, unknown>)?.skills)
        ? ((userProfile as Record<string, unknown>).skills as string[])
        : Array.isArray((userProfile as Record<string, unknown>)?.matching_skills)
        ? ((userProfile as Record<string, unknown>).matching_skills as string[])
        : [];

      const result = await applyPack({
        profile: { id: profileId, skills: profileSkills },
        offer: {
          id: item.offer_id,
          title: item.title,
          company: item.company,
          country: item.country,
          city: item.city,
          skills: [],
        },
        matched_core: item.matched_skills_display,
        missing_core: item.missing_skills_display,
        enrich_llm: 0,
      });
      setApplyPackResult(result);
    } catch (err) {
      setApplyPackError(err instanceof Error ? err.message : "Erreur lors de la génération");
    } finally {
      setApplyPackLoading(false);
    }
  };

  const handleResetFilters = () => {
    setThreshold(DEFAULT_THRESHOLD);
    setSearchQuery("");
  };

  const handleShowAll = () => {
    setThreshold(0);
    setSearchQuery("");
  };

  const handleCloseApplyPack = () => {
    setApplyPackOffer(null);
    setApplyPackResult(null);
    setApplyPackError(null);
  };

  // ============================================================================
  // Render States
  // ============================================================================

  // State A: No profile loaded
  if (!userProfile) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <EmptyState
          icon={FileText}
          title="Aucun profil chargé"
          description="Importez votre CV ou créez un profil pour voir les offres."
          actions={
            <div className="flex gap-3">
              <Link to="/analyze" className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition">
                Importer CV
              </Link>
              <Link to="/profile" className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                Créer profil
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  // State B: Profile incomplete (PROD only)
  if (profileIncomplete) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-8 max-w-md text-center">
          <AlertCircle className="w-10 h-10 text-amber-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-amber-900 mb-2">Profil incomplet</h3>
          <p className="text-sm text-amber-700 mb-6">
            Votre profil ne contient pas de compétences.
          </p>
          <div className="flex gap-3 justify-center">
            <Link to="/analyze" className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-amber-600 text-white hover:bg-amber-700 transition">
              Importer CV
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // State C: API error
  if (error && !loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <EmptyState
          icon={AlertCircle}
          title="Erreur de chargement"
          description={error}
          actions={
            <button onClick={load} className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />
              Réessayer
            </button>
          }
        />
      </div>
    );
  }

  // Main render
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <Inbox className="w-7 h-7 text-slate-900" />
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Inbox</h1>
              {import.meta.env.DEV && skillsSource === "seed" && (
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] font-medium rounded-full border border-emerald-200">
                  Seed
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {DEBUG_INBOX && (
                <button
                  onClick={() => setDebugOpen(!debugOpen)}
                  className={`p-2 rounded-lg transition ${debugOpen ? "bg-emerald-100 text-emerald-700" : "text-slate-400 hover:text-slate-600"}`}
                >
                  <Bug className="w-4 h-4" />
                </button>
              )}
              <Link to="/applications" className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 transition">
                <Sparkles className="w-4 h-4" />
                Candidatures
              </Link>
            </div>
          </div>
          <p className="text-sm text-slate-500">
            Offres correspondant à votre profil.
          </p>
          {import.meta.env.DEV && lastApiCall && (
            <div className="mt-3 text-[11px] text-slate-500">
              <span className="mr-3">profile_id: {lastApiCall.profile_id.slice(0, 10)}…</span>
              <span className="mr-3">total_matched: {lastApiCall.total_matched}</span>
              <span className="mr-3">total_decided: {lastApiCall.total_decided}</span>
              <span>first: {items[0]?.offer_id?.slice(0, 10) ?? "—"} / {items[0]?.score ?? "—"}</span>
            </div>
          )}
        </header>

        {/* Filters */}
        <div className="mb-6">
          <FilterBar
            threshold={threshold}
            onThresholdChange={setThreshold}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onReset={handleResetFilters}
            onShowAll={handleShowAll}
            domainMode={domainMode}
            onDomainModeChange={setDomainMode}
            suggestOutOfDomain={Boolean(inboxMeta?.suggest_out_of_domain && domainMode === "in_domain")}
            sortMode={sortMode}
            onSortChange={setSortMode}
            receivedCount={receivedCount}
            displayedCount={displayedCount}
            maskedCount={maskedCount}
            hasActiveFilters={hasActiveFilters}
          />
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
          </div>
        )}

        {/* Content */}
        {!loading && (
          <>
            {/* State D: No offers from API */}
            {receivedCount === 0 && (
              <EmptyState
                icon={Inbox}
                title="Aucune offre disponible"
                description="L'API n'a renvoyé aucune offre. Vérifiez votre connexion ou réessayez."
                actions={
                  <button onClick={load} className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition flex items-center gap-2">
                    <RefreshCw className="w-4 h-4" />
                    Actualiser
                  </button>
                }
              />
            )}

            {/* State E: Offers received but all filtered */}
            {receivedCount > 0 && displayedCount === 0 && (
              <EmptyState
                icon={Filter}
                title="Tes filtres masquent tout"
                description={`${maskedCount} offre${maskedCount > 1 ? "s" : ""} reçue${maskedCount > 1 ? "s" : ""} mais masquée${maskedCount > 1 ? "s" : ""} par tes filtres.`}
                actions={
                  <div className="flex gap-3">
                    <button onClick={handleResetFilters} className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition">
                      Réinitialiser filtres
                    </button>
                    <button onClick={handleShowAll} className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition">
                      Tout afficher
                    </button>
                  </div>
                }
              />
            )}

            {/* Offers Grid */}
            {displayedCount > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {displayedItems.map((offer) => (
                  <OfferCard
                    key={offer.offer_id}
                    offer={offer}
                    onShortlist={() => handleShortlist(offer.offer_id, offer.score)}
                    onDismiss={() => handleDecision(offer.offer_id, "DISMISSED", offer.score)}
                    onApply={() => handleApply(offer)}
                    onOpen={() => setSelectedOffer(offer)}
                    isShortlisted={trackerStatusMap[offer.offer_id] === "shortlisted"}
                    isPending={pendingDecisions.has(offer.offer_id)}
                    roleTypeLabel={formatRoleType(offerContextById[offer.offer_id]?.role_type)}
                  />
                ))}
              </div>
            )}

            {displayedCount > 0 && (
              <div className="mt-6 flex justify-center">
                <span className="flex items-center gap-2 text-xs text-slate-400">
                  <ChevronDown className="w-4 h-4" />
                  Triées par score décroissant
                </span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Debug Drawer */}
      {DEBUG_INBOX && (
        <DebugDrawer
          isOpen={debugOpen}
          onClose={() => setDebugOpen(false)}
          items={items}
          displayedCount={displayedCount}
          threshold={threshold}
          searchQuery={searchQuery}
          lastApiCall={lastApiCall}
          skillsSource={skillsSource}
        />
      )}

      {/* Apply Pack Modal */}
      {applyPackOffer && (
        <ApplyPackModal
          offer={applyPackOffer}
          result={applyPackResult}
          loading={applyPackLoading}
          error={applyPackError}
          tab={applyPackTab}
          onTabChange={setApplyPackTab}
          onClose={handleCloseApplyPack}
        />
      )}

      {selectedOffer && (
        <OfferDetailModal
          offer={selectedSemantic ? { ...selectedOffer, ...selectedSemantic } : selectedOffer}
          showDebug={DEBUG_INBOX}
          offerContext={selectedOfferContext}
          profileContext={profileContext}
          contextFit={selectedContextFit}
          contextLoading={contextLoading}
          contextError={contextError}
          onClose={() => setSelectedOffer(null)}
        />
      )}
    </div>
  );
}

// ============================================================================
// Apply Pack Modal Component
// ============================================================================

function ApplyPackModal({
  offer,
  result,
  loading,
  error,
  tab,
  onTabChange,
  onClose,
}: {
  offer: NormalizedInboxItem;
  result: ApplyPackResponse | null;
  loading: boolean;
  error: string | null;
  tab: "cv" | "letter";
  onTabChange: (t: "cv" | "letter") => void;
  onClose: () => void;
}) {
  const activeText = result ? (tab === "cv" ? result.cv_text : result.letter_text) : "";
  const activeFilename = tab === "cv" ? "cv_generated.md" : "lettre_motivation.md";

  const handleCopy = () => {
    if (activeText) {
      navigator.clipboard.writeText(activeText).catch(() => {});
    }
  };

  const handleDownload = () => {
    if (!activeText) return;
    const blob = new Blob([activeText], { type: "text/markdown; charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = activeFilename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative flex flex-col w-full max-w-2xl max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-6 pt-5 pb-4 border-b border-slate-100">
          <div className="min-w-0">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Apply Pack</div>
            <h2 className="text-base font-bold text-slate-900 truncate">{offer.title}</h2>
            {offer.company && (
              <div className="text-sm text-slate-500 truncate">{offer.company}</div>
            )}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        {result && (
          <div className="flex gap-0 px-6 border-b border-slate-100">
            {(["cv", "letter"] as const).map((t) => (
              <button
                key={t}
                onClick={() => onTabChange(t)}
                className={`px-4 py-2.5 text-sm font-semibold transition-colors ${
                  tab === t
                    ? "border-b-2 border-slate-900 text-slate-900"
                    : "text-slate-400 hover:text-slate-600"
                }`}
              >
                {t === "cv" ? "CV" : "Lettre de motivation"}
              </button>
            ))}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 min-h-0">
          {loading && (
            <div className="flex items-center justify-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-600">
              {error}
            </div>
          )}

          {result && (
            <>
              {result.warnings.length > 0 && (
                <div className="mb-3 rounded-xl border border-amber-100 bg-amber-50 p-3 text-sm text-amber-700">
                  {result.warnings.join(" · ")}
                </div>
              )}
              <pre className="whitespace-pre-wrap font-mono text-xs text-slate-700 bg-slate-50 rounded-xl p-4 border border-slate-100 leading-relaxed">
                {activeText}
              </pre>
              <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-400">
                <span className="px-2 py-0.5 bg-slate-100 rounded-full font-mono">{result.mode}</span>
                {result.meta.matched_core.length > 0 && (
                  <span>{result.meta.matched_core.length} compétences matchées</span>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer actions */}
        {result && (
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-100 bg-slate-50">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 transition"
            >
              Copier
            </button>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition"
            >
              Télécharger .md
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
