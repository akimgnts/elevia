import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  Bug,
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
  fetchProfileSummary,
  postDecision,
  type ApplyPackResponse,
  type ExplainBlock,
  type OfferExplanation,
  type OfferIntelligence,
  type ScoringV2,
  type SemanticExplainability,
  type OfferSemanticResponse,
  type OfferContext,
  type ProfileContext,
  type ContextFit,
  type ProfileSummaryV1,
  type InboxFilters,
} from "../lib/api";
import { buildMatchingProfile, type SkillsSource, type ProfileMatchingV1 } from "../lib/profileMatching";
import { useProfileStore } from "../store/profileStore";
import { SEED_PROFILE } from "../fixtures/seedProfile";
import { OfferDetailModal, type OfferDetail } from "../components/OfferDetailModal";
import { cleanOfferTitle, truncateOfferTitle } from "../lib/titleUtils";
import { InboxCardV2 } from "../components/inbox/InboxCardV2";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";

// ============================================================================
// Constants
// ============================================================================

const STORAGE_PREFIX = "elevia_inbox";
const DEFAULT_THRESHOLD = 0;
const THRESHOLD_OPTIONS = [0, 55, 65, 75, 85];

type FiltersState = {
  q_company: string;
  country: string;
  city: string;
  contract_type: string;
  published_from: string;
  published_to: string;
  domain_bucket: "" | "strict" | "neighbor" | "out";
  confidence: "" | "LOW" | "MED" | "HIGH";
  rare_level: "" | "LOW" | "MED" | "HIGH";
  sector_level: "" | "LOW" | "MED" | "HIGH";
  has_tool_unspecified: boolean | null;
};

const DEFAULT_FILTERS: FiltersState = {
  q_company: "",
  country: "",
  city: "",
  contract_type: "",
  published_from: "",
  published_to: "",
  domain_bucket: "",
  confidence: "",
  rare_level: "",
  sector_level: "",
  has_tool_unspecified: null,
};

// Debug mode: localStorage.setItem("elevia_debug_inbox", "1")
const DEBUG_INBOX = import.meta.env.DEV && localStorage.getItem("elevia_debug_inbox") === "1";

// ── Domain signals (from AnalyzePage parse result, stored in localStorage) ──
type DomainSignals = {
  domain_skills_active: string[];
  resolved_to_esco: Array<{ token_normalized: string; esco_uri: string; esco_label?: string; provenance?: string }>;
  injected_esco_from_domain: number;
  total_esco_count: number;
};

type InboxProfileSnapshot = {
  profile_id: string;
  matching_profile: ProfileMatchingV1;
  skills_source: SkillsSource;
  created_at: string;
};

const INBOX_PROFILE_SNAPSHOT_KEY = "elevia_inbox_profile_snapshot";

function writeInboxProfileSnapshot(snapshot: InboxProfileSnapshot): void {
  try {
    localStorage.setItem(INBOX_PROFILE_SNAPSHOT_KEY, JSON.stringify(snapshot));
  } catch {
    // ignore storage errors
  }
}

function readDomainSignals(): DomainSignals | null {
  try {
    const raw = localStorage.getItem("elevia_domain_signals");
    if (!raw) return null;
    return JSON.parse(raw) as DomainSignals;
  } catch {
    return null;
  }
}

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
  title_clean?: string | null;
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
  explanation: OfferExplanation;
  offer_intelligence?: OfferIntelligence | null;
  semantic_explainability?: SemanticExplainability | null;
  scoring_v2?: ScoringV2 | null;
  offer_cluster?: string;
  domain_bucket?: "strict" | "neighbor" | "out";
  signal_score?: number;
  coherence?: "ok" | "suspicious";
  near_match_count?: number;
  core_matched_count?: number;
  core_total_count?: number;
  dominant_reason?: string;
};

type LastApiCall = {
  timestamp: string;
  profile_id: string;
  min_score: number;
  limit: number;
  page?: number;
  page_size?: number;
  total_estimate?: number | null;
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
  const scaled = value > 0 && value < 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(scaled)));
}

function explanationScore(item: Pick<NormalizedInboxItem, "score" | "explanation">): number {
  return typeof item.explanation.score === "number" ? item.explanation.score : item.score;
}

function blockersCount(item: Pick<NormalizedInboxItem, "explanation">): number {
  return Array.isArray(item.explanation.blockers) ? item.explanation.blockers.length : 0;
}

function strengthsCount(item: Pick<NormalizedInboxItem, "explanation">): number {
  return Array.isArray(item.explanation.strengths) ? item.explanation.strengths.length : 0;
}

function recencyValue(publicationDate?: string | null): number {
  if (!publicationDate) return 0;
  const parsed = Date.parse(publicationDate);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sortInboxItemsForDisplay(items: NormalizedInboxItem[]): NormalizedInboxItem[] {
  return [...items].sort((a, b) => {
    return (
      explanationScore(b) - explanationScore(a) ||
      blockersCount(a) - blockersCount(b) ||
      strengthsCount(b) - strengthsCount(a) ||
      recencyValue(b.publication_date) - recencyValue(a.publication_date) ||
      a.offer_id.localeCompare(b.offer_id)
    );
  });
}

function cleanDescriptionSnippet(value?: string | null, maxLen = 180): string {
  if (!value) return "";
  const stripped = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (stripped.length <= maxLen) return stripped;
  return `${stripped.slice(0, maxLen).trim()}…`;
}

function formatLocation(city?: string | null, country?: string | null) {
  if (city && country) return `${city}, ${country}`;
  if (city) return city;
  if (country) return country;
  return null;
}

function bucketLabel(bucket?: "strict" | "neighbor" | "out" | "") {
  if (bucket === "strict") return "Bucket: Strict";
  if (bucket === "neighbor") return "Bucket: Voisin";
  if (bucket === "out") return "Bucket: Hors domaine";
  return null;
}

function levelLabel(level?: "LOW" | "MED" | "HIGH") {
  if (level === "HIGH") return "Haut";
  if (level === "MED") return "Moyen";
  if (level === "LOW") return "Bas";
  return null;
}

function normalizeFiltersState(filters: FiltersState): FiltersState {
  return {
    ...filters,
    q_company: filters.q_company.trim(),
    country: filters.country.trim(),
    city: filters.city.trim(),
    contract_type: filters.contract_type.trim(),
  };
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
    const explanation =
      rec.explanation && typeof rec.explanation === "object"
        ? (rec.explanation as OfferExplanation)
        : null;
    if (!explanation) {
      console.warn("[inbox] Item missing explanation contract:", rec);
      continue;
    }

    results.push({
      offer_id: offerId,
      id: typeof rec.id === "string" ? rec.id : undefined,
      source: typeof rec.source === "string" ? rec.source : undefined,
      title: typeof rec.title === "string" ? rec.title : "Offre",
      title_clean: typeof rec.title_clean === "string" ? rec.title_clean : null,
      company: typeof rec.company === "string" ? rec.company : null,
      country: typeof rec.country === "string" ? rec.country : null,
      city: typeof rec.city === "string" ? rec.city : null,
      publication_date: typeof rec.publication_date === "string" ? rec.publication_date : null,
      score: normalizeScore(
        typeof explanation.score === "number"
          ? explanation.score
          : typeof rec.score_pct === "number"
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
      explanation,
      offer_intelligence:
        rec.offer_intelligence && typeof rec.offer_intelligence === "object"
          ? (rec.offer_intelligence as OfferIntelligence)
          : null,
      semantic_explainability:
        rec.semantic_explainability && typeof rec.semantic_explainability === "object"
          ? (rec.semantic_explainability as SemanticExplainability)
          : null,
      scoring_v2:
        rec.scoring_v2 && typeof rec.scoring_v2 === "object"
          ? (rec.scoring_v2 as ScoringV2)
          : null,
      offer_cluster: typeof rec.offer_cluster === "string" ? rec.offer_cluster : undefined,
      domain_bucket:
        rec.domain_bucket === "strict" || rec.domain_bucket === "neighbor" || rec.domain_bucket === "out"
          ? (rec.domain_bucket as "strict" | "neighbor" | "out")
          : undefined,
      signal_score: typeof rec.signal_score === "number" ? rec.signal_score : undefined,
      coherence: rec.coherence === "ok" || rec.coherence === "suspicious" ? rec.coherence : undefined,
      near_match_count: typeof rec.near_match_count === "number" ? rec.near_match_count : undefined,
      core_matched_count: typeof rec.core_matched_count === "number" ? rec.core_matched_count : undefined,
      core_total_count: typeof rec.core_total_count === "number" ? rec.core_total_count : undefined,
      dominant_reason: typeof rec.dominant_reason === "string" ? rec.dominant_reason : undefined,
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

/** Adapts a NormalizedInboxItem to InboxCardV2 props and renders the card. */
function OfferCard({
  offer,
  onOpen,
  onShortlist,
  onPass,
}: {
  offer: NormalizedInboxItem;
  onOpen: () => void;
  onShortlist: () => void;
  onPass: () => void;
}) {
  const relativeTitle = offer.title_clean || offer.title;
  const titleInfo = cleanOfferTitle(relativeTitle);
  const displayTitle = truncateOfferTitle(titleInfo.display, 90);

  const location = formatLocation(offer.city, offer.country) ?? undefined;

  return (
    <InboxCardV2
      offerId={offer.offer_id}
      company={offer.company ?? ""}
      title={displayTitle}
      location={location}
      score={offer.score}
      explanation={offer.explanation}
      offerIntelligence={offer.offer_intelligence}
      semanticExplainability={offer.semantic_explainability}
      scoringV2={offer.scoring_v2}
      domainBucket={offer.domain_bucket}
      cluster={{ label: offer.offer_cluster ?? "" }}
      onOpenDetails={() => onOpen()}
      onShortlist={() => onShortlist()}
      onPass={() => onPass()}
    />
  );
}

function FiltersDrawer({
  isOpen,
  draft,
  onDraftChange,
  threshold,
  onThresholdChange,
  filtersDirty,
  onApply,
  onCancel,
}: {
  isOpen: boolean;
  draft: FiltersState;
  onDraftChange: (next: FiltersState) => void;
  threshold: number;
  onThresholdChange: (value: number) => void;
  filtersDirty: boolean;
  onApply: () => void;
  onCancel: () => void;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  if (!isOpen) return null;

  const update = (patch: Partial<FiltersState>) => {
    onDraftChange({ ...draft, ...patch });
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-stretch justify-end bg-slate-900/40 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-md bg-white shadow-2xl p-5 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Filtres</h3>
          </div>
          <button
            onClick={onCancel}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Pays</label>
              <input
                type="text"
                value={draft.country}
                onChange={(e) => update({ country: e.target.value })}
                placeholder="Ex: France"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Ville</label>
              <input
                type="text"
                value={draft.city}
                onChange={(e) => update({ city: e.target.value })}
                placeholder="Ex: Lyon"
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Contrat</label>
              <select
                value={draft.contract_type}
                onChange={(e) => update({ contract_type: e.target.value })}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
              >
                <option value="">Tous</option>
                <option value="VIE">VIE</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Bucket</label>
              <select
                value={draft.domain_bucket}
                onChange={(e) => update({ domain_bucket: e.target.value as FiltersState["domain_bucket"] })}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
              >
                <option value="">Tous</option>
                <option value="strict">Strict</option>
                <option value="neighbor">Voisin</option>
                <option value="out">Hors domaine</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Publié après</label>
              <input
                type="date"
                value={draft.published_from}
                onChange={(e) => update({ published_from: e.target.value })}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Publié avant</label>
              <input
                type="date"
                value={draft.published_to}
                onChange={(e) => update({ published_to: e.target.value })}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Seuil score</label>
            <div className="mt-2 flex bg-slate-100 p-1 rounded-xl flex-wrap">
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

          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Outil ambigu</label>
            <select
              value={draft.has_tool_unspecified === null ? "" : draft.has_tool_unspecified ? "yes" : "no"}
              onChange={(e) =>
                update({
                  has_tool_unspecified: e.target.value === "" ? null : e.target.value === "yes",
                })
              }
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
            >
              <option value="">Indifférent</option>
              <option value="yes">Oui</option>
              <option value="no">Non</option>
            </select>
          </div>

          <button
            onClick={() => setShowAdvanced((prev) => !prev)}
            className="flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-700 transition"
          >
            <ChevronDown className={`w-4 h-4 transition-transform ${showAdvanced ? "rotate-180" : ""}`} />
            Avancé
          </button>

          {showAdvanced && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Confiance</label>
                  <select
                    value={draft.confidence}
                    onChange={(e) => update({ confidence: e.target.value as FiltersState["confidence"] })}
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
                  >
                    <option value="">Toutes</option>
                    <option value="HIGH">Haute</option>
                    <option value="MED">Moyenne</option>
                    <option value="LOW">Basse</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Signal rare</label>
                  <select
                    value={draft.rare_level}
                    onChange={(e) => update({ rare_level: e.target.value as FiltersState["rare_level"] })}
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
                  >
                    <option value="">Tous</option>
                    <option value="HIGH">Haut</option>
                    <option value="MED">Moyen</option>
                    <option value="LOW">Bas</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Signal secteur</label>
                <select
                  value={draft.sector_level}
                  onChange={(e) => update({ sector_level: e.target.value as FiltersState["sector_level"] })}
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
                >
                  <option value="">Tous</option>
                  <option value="HIGH">Haut</option>
                  <option value="MED">Moyen</option>
                  <option value="LOW">Bas</option>
                </select>
              </div>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={onApply}
            disabled={!filtersDirty}
            className={`flex-1 px-3 py-2 rounded-xl text-sm font-semibold transition ${
              filtersDirty
                ? "bg-slate-900 text-white hover:bg-slate-800"
                : "bg-slate-100 text-slate-400 cursor-not-allowed"
            }`}
          >
            Appliquer
          </button>
          <button
            onClick={onCancel}
            className="px-3 py-2 rounded-xl text-sm font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition"
          >
            Annuler
          </button>
        </div>
      </div>
    </div>
  );
}

function ProfileSummarySidebar({
  summary,
  loading,
  missing,
  error,
  domainSignals,
}: {
  summary: ProfileSummaryV1 | null;
  loading: boolean;
  missing: boolean;
  error: string | null;
  domainSignals: DomainSignals | null;
}) {
  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-4 shadow-sm space-y-4">
      <div>
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400 font-semibold">Repères</div>
          <div className="text-sm font-semibold text-slate-900">Qualité et signaux utiles</div>
        </div>
      </div>

      {loading && (
        <div className="space-y-3 animate-pulse">
          <div className="h-4 bg-slate-100 rounded" />
          <div className="h-3 bg-slate-100 rounded" />
          <div className="h-3 bg-slate-100 rounded w-4/5" />
        </div>
      )}

      {!loading && missing && (
        <div className="text-sm text-slate-600">
          Aucun repere disponible pour l&apos;instant.
          <div className="mt-3">
            <Link to="/analyze" className="inline-flex px-3 py-2 rounded-xl text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition">
              Importer un CV
            </Link>
          </div>
        </div>
      )}

      {!loading && !missing && error && (
        <div className="text-sm text-rose-600">
          Résumé indisponible.
        </div>
      )}

      {!loading && !missing && !error && summary && (
        <div className="space-y-4 text-sm text-slate-700">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Qualité CV</div>
            <div className="mt-1 flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                summary.cv_quality_level === "HIGH"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : summary.cv_quality_level === "MED"
                    ? "bg-amber-50 text-amber-700 border-amber-200"
                    : "bg-rose-50 text-rose-700 border-rose-200"
              }`}>
                {summary.cv_quality_level}
              </span>
            </div>
            {summary.cv_quality_reasons.length > 0 && (
              <div className="mt-2 text-xs text-slate-500">
                {summary.cv_quality_reasons[0].replace(/_/g, " ").toLowerCase()}
              </div>
            )}
          </div>

          {summary.top_skills.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Skills clés</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {summary.top_skills.slice(0, 5).map((skill) => (
                  <span key={skill.label} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                    {skill.label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {summary.tools.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Outils</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {summary.tools.slice(0, 5).map((tool) => (
                  <span key={tool} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {summary.education.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Formation</div>
              <div className="mt-2 text-xs text-slate-600">
                {summary.education[0]}
              </div>
            </div>
          )}

          {summary.experiences.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Expériences</div>
              <div className="mt-2 space-y-3 text-xs text-slate-600">
                {summary.experiences.slice(0, 2).map((exp, idx) => (
                  <div key={`${exp.title}-${idx}`} className="space-y-1">
                    <div className="font-semibold text-slate-700">
                      {exp.title || "Expérience"} {exp.company ? `· ${exp.company}` : ""}
                    </div>
                    {exp.dates && <div className="text-[11px] text-slate-500">{exp.dates}</div>}
                    {exp.impact_one_liner && (
                      <div className="text-[11px] text-slate-500">“{exp.impact_one_liner}”</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary.cluster_hints.length > 0 && (
            <div>
              <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Cluster</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {summary.cluster_hints.slice(0, 2).map((hint) => (
                  <span key={hint} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                    {hint}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Domain skills (from Compass E mapping — shown if available) */}
      {domainSignals && domainSignals.domain_skills_active.length > 0 && (
        <div className="border-t border-slate-100 pt-4 space-y-2">
          <div className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">Compétences métier</div>
          <div className="flex flex-wrap gap-1.5">
            {domainSignals.domain_skills_active.slice(0, 3).map((skill) => (
              <span key={skill} className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                {skill}
              </span>
            ))}
          </div>
          {domainSignals.injected_esco_from_domain > 0 && (
            <div className="text-[10px] text-blue-600 font-medium">
              ↗ +{domainSignals.injected_esco_from_domain} compétence{domainSignals.injected_esco_from_domain > 1 ? "s" : ""} via mapping ESCO
              {domainSignals.resolved_to_esco[0] && (
                <span className="text-blue-400 font-normal">
                  {" "}· ex. {domainSignals.resolved_to_esco[0].token_normalized}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DebugDrawer({
  isOpen,
  onClose,
  items,
  displayedCount,
  threshold,
  lastApiCall,
  skillsSource,
}: {
  isOpen: boolean;
  onClose: () => void;
  items: NormalizedInboxItem[];
  displayedCount: number;
  threshold: number;
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
          <span className="text-slate-400">skillsSource:</span>{" "}
          <span className="text-white">{skillsSource}</span>
        </div>

        {lastApiCall && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <div className="text-slate-400 mb-1">Last API call:</div>
            <div>profile_id: {lastApiCall.profile_id.slice(0, 12)}...</div>
            <div>min_score: {lastApiCall.min_score}</div>
            <div>limit: {lastApiCall.limit}</div>
            {typeof lastApiCall.page === "number" && <div>page: {lastApiCall.page}</div>}
            {typeof lastApiCall.page_size === "number" && <div>page_size: {lastApiCall.page_size}</div>}
            {typeof lastApiCall.total_estimate === "number" && <div>total_estimate: {lastApiCall.total_estimate}</div>}
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
  const [filtersDraft, setFiltersDraft] = useState<FiltersState>(DEFAULT_FILTERS);
  const [filtersApplied, setFiltersApplied] = useState<FiltersState>(DEFAULT_FILTERS);
  const [threshold, setThreshold] = useState<number>(() => {
    const stored = readJson<number | null>(`${STORAGE_PREFIX}_threshold`, null);
    return typeof stored === "number" ? stored : DEFAULT_THRESHOLD;
  });
  const [thresholdDraft, setThresholdDraft] = useState<number>(() => {
    const stored = readJson<number | null>(`${STORAGE_PREFIX}_threshold`, null);
    return typeof stored === "number" ? stored : DEFAULT_THRESHOLD;
  });
  const [filtersDrawerOpen, setFiltersDrawerOpen] = useState(false);
  const sortMode = "score_desc" as const;
  const [page, setPage] = useState(1);
  const [pageSize] = useState(24);
  const [decisions, setDecisions] = useState<Record<string, DecisionRecord>>({});
  const [lastApiCall, setLastApiCall] = useState<LastApiCall | null>(null);
  const [debugOpen, setDebugOpen] = useState(DEBUG_INBOX);

  // Apply Pack modal state
  const [applyPackOffer, setApplyPackOffer] = useState<NormalizedInboxItem | null>(null);
  const [applyPackResult, setApplyPackResult] = useState<ApplyPackResponse | null>(null);
  const [applyPackLoading] = useState(false);
  const [applyPackError, setApplyPackError] = useState<string | null>(null);
  const [applyPackTab, setApplyPackTab] = useState<"cv" | "letter">("cv");
  const [selectedOffer, setSelectedOffer] = useState<OfferDetail | null>(null);
  const [semanticByOfferId, setSemanticByOfferId] = useState<Record<string, OfferSemanticResponse>>({});
  const [semanticLoadingIds, setSemanticLoadingIds] = useState<Set<string>>(new Set());
  const [offerContextById, setOfferContextById] = useState<Record<string, OfferContext>>({});
  const [profileContext, setProfileContext] = useState<ProfileContext | null>(null);
  const [profileContextLoading, setProfileContextLoading] = useState(false);
  const [profileSummary, setProfileSummary] = useState<ProfileSummaryV1 | null>(null);
  const [profileSummaryLoading, setProfileSummaryLoading] = useState(false);
  const [profileSummaryMissing, setProfileSummaryMissing] = useState(false);
  const [profileSummaryError, setProfileSummaryError] = useState<string | null>(null);
  const [contextFitByOfferId, setContextFitByOfferId] = useState<Record<string, ContextFit>>({});
  const [contextLoadingIds, setContextLoadingIds] = useState<Set<string>>(new Set());
  const [contextFitLoadingIds, setContextFitLoadingIds] = useState<Set<string>>(new Set());
  const [contextErrorByOfferId, setContextErrorByOfferId] = useState<Record<string, string>>({});
  const inboxLoadKeyRef = useRef<string | null>(null);

  // Domain signals: read once from localStorage (written by AnalyzePage after parse)
  const [domainSignals] = useState<DomainSignals | null>(() => readDomainSignals());

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

    const controller = new AbortController();
    setSemanticLoadingIds((prev) => new Set(prev).add(offerId));
    fetchOfferSemantic(offerId, profileId)
      .then((data) => {
        if (!controller.signal.aborted) {
          setSemanticByOfferId((prev) => ({ ...prev, [offerId]: data }));
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.warn("[inbox] semantic fetch failed:", err);
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
        if (!controller.signal.aborted) {
          setSemanticLoadingIds((prev) => {
            const next = new Set(prev);
            next.delete(offerId);
            return next;
          });
        }
      });
    return () => controller.abort();
  }, [selectedOffer, profileId, semanticByOfferId, semanticLoadingIds]);

  useEffect(() => {
    if (!userProfile || !profileId) return;
    const controller = new AbortController();
    setProfileContextLoading(true);
    fetchProfileContext(profileId, userProfile)
      .then((data) => {
        if (!controller.signal.aborted) setProfileContext(data);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.warn("[inbox] profile context fetch failed:", err);
        setProfileContext(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setProfileContextLoading(false);
      });
    return () => controller.abort();
  }, [userProfile, profileId]);

  useEffect(() => {
    if (!profileId) return;
    setProfileSummaryLoading(true);
    setProfileSummaryMissing(false);
    setProfileSummaryError(null);
    fetchProfileSummary(profileId)
      .then((data) => {
        setProfileSummary(data);
      })
      .catch((err: unknown) => {
        const status = (err as { status?: number }).status;
        if (status === 404) {
          setProfileSummary(null);
          setProfileSummaryMissing(true);
          return;
        }
        setProfileSummary(null);
        setProfileSummaryError(err instanceof Error ? err.message : "summary_failed");
      })
      .finally(() => {
        setProfileSummaryLoading(false);
      });
  }, [profileId]);

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

    const controller = new AbortController();
    setContextLoadingIds((prev) => new Set(prev).add(offerId));
    fetchOfferContext(offerId, description)
      .then((data) => {
        if (!controller.signal.aborted) {
          setOfferContextById((prev) => ({ ...prev, [offerId]: data }));
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.warn("[inbox] offer context fetch failed:", err);
        setContextErrorByOfferId((prev) => ({
          ...prev,
          [offerId]: "context_offer_failed",
        }));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setContextLoadingIds((prev) => {
            const next = new Set(prev);
            next.delete(offerId);
            return next;
          });
        }
      });
    return () => controller.abort();
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

    const controller = new AbortController();
    setContextFitLoadingIds((prev) => new Set(prev).add(selectedOfferId));
    fetchContextFit(profileContext, offerContext, matched, missing)
      .then((data) => {
        if (!controller.signal.aborted) {
          setContextFitByOfferId((prev) => ({ ...prev, [selectedOfferId]: data }));
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.warn("[inbox] context fit fetch failed:", err);
        setContextErrorByOfferId((prev) => ({
          ...prev,
          [selectedOfferId]: "context_fit_failed",
        }));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setContextFitLoadingIds((prev) => {
            const next = new Set(prev);
            next.delete(selectedOfferId);
            return next;
          });
        }
      });
    return () => controller.abort();
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
    let requestKey: string | null = null;
    setLoading(true);
    setError(null);
    setProfileIncomplete(false);

    try {
      const { profile: matchingProfile, skillsSource: source, needsSeedHydration } = buildMatchingProfile(
        userProfile as Record<string, unknown>,
        profileId
      );

      setSkillsSource(source);
      const snapshot: InboxProfileSnapshot = {
        profile_id: profileId,
        matching_profile: matchingProfile,
        skills_source: source,
        created_at: new Date().toISOString(),
      };
      writeInboxProfileSnapshot(snapshot);

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

      const apiMinScore = 0;
      const apiLimit = pageSize;
      const apiFilters: InboxFilters = {
        q_company: filtersApplied.q_company || undefined,
        country: filtersApplied.country || undefined,
        city: filtersApplied.city || undefined,
        contract_type: filtersApplied.contract_type || undefined,
        published_from: filtersApplied.published_from || undefined,
        published_to: filtersApplied.published_to || undefined,
        domain_bucket: filtersApplied.domain_bucket || undefined,
        min_score: threshold,
        confidence: filtersApplied.confidence || undefined,
        rare_level: filtersApplied.rare_level || undefined,
        sector_level: filtersApplied.sector_level || undefined,
        has_tool_unspecified: filtersApplied.has_tool_unspecified ?? undefined,
        page,
        page_size: pageSize,
        sort: sortMode,
      };
      requestKey = JSON.stringify({
        profileId,
        threshold,
        page,
        pageSize,
        sortMode,
        filters: apiFilters,
        skills: matchingProfile.matching_skills,
      });
      if (inboxLoadKeyRef.current === requestKey) {
        setLoading(false);
        return;
      }
      inboxLoadKeyRef.current = requestKey;

      if (DEBUG_INBOX) {
        console.info("[inbox] Calling API with:", {
          profile_id: profileId,
          min_score: apiMinScore,
          limit: apiLimit,
          filters: apiFilters,
        });
      }

      const data = await fetchInbox(matchingProfile, profileId, apiMinScore, apiLimit, true, "all", apiFilters);

      setLastApiCall({
        timestamp: new Date().toISOString(),
        profile_id: profileId,
        min_score: apiMinScore,
        limit: apiLimit,
        page,
        page_size: pageSize,
        total_estimate: data.total_estimate ?? null,
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

      const normalized = sortInboxItemsForDisplay(normalizeInboxItems(data.items));
      setItems(normalized);

      if (DEBUG_INBOX) {
        console.info("[inbox] Normalized items:", normalized.length);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur inconnue";
      setError(msg);
      console.error("[inbox] Load error:", e);
    } finally {
      if (requestKey && inboxLoadKeyRef.current === requestKey) {
        inboxLoadKeyRef.current = null;
      }
      setLoading(false);
    }
  }, [
    userProfile,
    profileId,
    setUserProfile,
    filtersApplied,
    threshold,
    sortMode,
    page,
    pageSize,
  ]);

  // Initial load
  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [threshold]);

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

  // Displayed = available after server-side filters
  const displayedItems = useMemo(() => sortInboxItemsForDisplay(availableItems), [availableItems]);

  const displayedCount = displayedItems.length;
  const maskedCount = receivedCount - displayedCount;
  const hasActiveFilters = useMemo(() => {
    if (threshold > 0) return true;
    const values = Object.values(filtersApplied);
    for (const value of values) {
      if (typeof value === "string" && value.trim()) return true;
      if (typeof value === "boolean") return true;
    }
    return false;
  }, [filtersApplied, threshold]);

  const activeFilterChips = useMemo(() => {
    const chips: { key: string; label: string }[] = [];
    if (filtersApplied.q_company) chips.push({ key: "q_company", label: `Entreprise: ${filtersApplied.q_company}` });
    if (filtersApplied.country) chips.push({ key: "country", label: filtersApplied.country });
    if (filtersApplied.city) chips.push({ key: "city", label: filtersApplied.city });
    if (filtersApplied.contract_type) chips.push({ key: "contract_type", label: filtersApplied.contract_type });
    if (filtersApplied.published_from || filtersApplied.published_to) {
      const from = filtersApplied.published_from ? filtersApplied.published_from : "…";
      const to = filtersApplied.published_to ? filtersApplied.published_to : "…";
      chips.push({ key: "published_range", label: `Publié: ${from} -> ${to}` });
    }
    const bucket = bucketLabel(filtersApplied.domain_bucket);
    if (bucket) chips.push({ key: "bucket", label: bucket });
    if (threshold > 0) chips.push({ key: "threshold", label: `Score ≥ ${threshold}` });
    if (filtersApplied.has_tool_unspecified !== null) {
      chips.push({
        key: "tool_unspecified",
        label: `Outil ambigu: ${filtersApplied.has_tool_unspecified ? "oui" : "non"}`,
      });
    }
    if (filtersApplied.confidence) {
      chips.push({
        key: "confidence",
        label: `Confiance: ${levelLabel(filtersApplied.confidence)}`,
      });
    }
    if (filtersApplied.rare_level) {
      chips.push({
        key: "rare_level",
        label: `Rare: ${levelLabel(filtersApplied.rare_level)}`,
      });
    }
    if (filtersApplied.sector_level) {
      chips.push({
        key: "sector_level",
        label: `Secteur: ${levelLabel(filtersApplied.sector_level)}`,
      });
    }
    return chips;
  }, [filtersApplied, threshold]);

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleDecision = useCallback(
    async (item: NormalizedInboxItem, status: DecisionStatus) => {
      try {
        await postDecision(item.offer_id, profileId, status);
      } catch (err) {
        console.warn("[inbox] decision API failed:", err);
      } finally {
        setDecisions((prev) => ({
          ...prev,
          [item.offer_id]: {
            status,
            score: item.score,
            updated_at: new Date().toISOString(),
          },
        }));
      }
    },
    [profileId]
  );

  const filtersDirty = useMemo(
    () => JSON.stringify(filtersDraft) !== JSON.stringify(filtersApplied) || thresholdDraft !== threshold,
    [filtersDraft, filtersApplied, thresholdDraft, threshold]
  );

  const handleApplyFilters = () => {
    const normalized = normalizeFiltersState(filtersDraft);
    setFiltersApplied(normalized);
    setFiltersDraft(normalized);
    setThreshold(thresholdDraft);
    setFiltersDrawerOpen(false);
    setPage(1);
  };

  const handleCancelFilters = () => {
    setFiltersDraft(filtersApplied);
    setThresholdDraft(threshold);
    setFiltersDrawerOpen(false);
  };

  const handleResetFilters = () => {
    setThreshold(DEFAULT_THRESHOLD);
    setThresholdDraft(DEFAULT_THRESHOLD);
    setFiltersDraft(DEFAULT_FILTERS);
    setFiltersApplied(DEFAULT_FILTERS);
    setPage(1);
  };

  const handleShowAll = () => {
    setThreshold(0);
    setThresholdDraft(0);
    setFiltersDraft(DEFAULT_FILTERS);
    setFiltersApplied(DEFAULT_FILTERS);
    setPage(1);
  };

  const handleOpenFilters = () => {
    setFiltersDrawerOpen(true);
  };

  const handleSearchSubmit = () => {
    const normalized = normalizeFiltersState(filtersDraft);
    if (normalized.q_company !== filtersApplied.q_company) {
      setFiltersDraft(normalized);
      setFiltersApplied(normalized);
      setThreshold(thresholdDraft);
      setFiltersDrawerOpen(false);
      setPage(1);
    }
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
    <PremiumAppShell
      eyebrow="Inbox"
      title="Inbox de matching"
      description="Les offres sont triees a partir du profil, puis relues avec filtres, contexte et decisions. Le but ici est la lisibilite."
      actions={
        <>
          {DEBUG_INBOX && (
            <button
              onClick={() => setDebugOpen(!debugOpen)}
              className={`inline-flex items-center gap-2 rounded-full px-4 py-3 text-sm font-semibold transition ${
                debugOpen
                  ? "bg-emerald-100 text-emerald-700"
                  : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Bug className="h-4 w-4" />
              Debug
            </button>
          )}
          <Link
            to="/applications"
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            <Sparkles className="h-4 w-4" />
            Candidatures
          </Link>
        </>
      }
      contentClassName="max-w-7xl"
    >
      <div className="py-2">
        {DEBUG_INBOX && lastApiCall && (
          <div className="mb-5 rounded-[1.25rem] border border-white/80 bg-white/70 px-4 py-3 text-[11px] text-slate-500 shadow-sm backdrop-blur">
            <span className="mr-3">profile_id: {lastApiCall.profile_id.slice(0, 10)}…</span>
            <span className="mr-3">total_matched: {lastApiCall.total_matched}</span>
            <span className="mr-3">total_decided: {lastApiCall.total_decided}</span>
            <span>first: {items[0]?.offer_id?.slice(0, 10) ?? "—"} / {items[0]?.score ?? "—"}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] gap-6">
          {/* Main content */}
          <main>
            <div className="sticky top-[88px] z-20 mb-5 rounded-[1.5rem] border border-white/80 bg-white/75 px-3 py-3 shadow-sm backdrop-blur-xl">
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative flex-1 min-w-[220px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    value={filtersDraft.q_company}
                    onChange={(e) => setFiltersDraft({ ...filtersDraft, q_company: e.target.value })}
                    onKeyDown={(e) => { if (e.key === "Enter") handleSearchSubmit(); }}
                    onBlur={handleSearchSubmit}
                    placeholder="Entreprise…"
                    className="w-full rounded-xl border border-slate-200 bg-white/90 pl-9 pr-3 py-2 text-sm text-slate-700 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10 outline-none"
                  />
                </div>
                <button
                  onClick={handleOpenFilters}
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  <Filter className="w-4 h-4" />
                  Filtres
                </button>
                {hasActiveFilters && (
                  <button
                    onClick={handleResetFilters}
                    className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    Reset
                  </button>
                )}
                <div className="ml-auto text-xs text-slate-500">
                  Affichées: <strong className="text-slate-900">{displayedCount}</strong>
                </div>
              </div>
              {activeFilterChips.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {activeFilterChips.map((chip) => (
                    <span
                      key={chip.key}
                      className="px-2.5 py-1 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600 border border-slate-200"
                    >
                      {chip.label}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {loading && (
              <div className="flex items-center justify-center py-20">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
              </div>
            )}

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
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                    {displayedItems.map((offer) => (
                      <OfferCard
                        key={offer.offer_id}
                        offer={offer}
                        onOpen={() => setSelectedOffer(offer)}
                        onShortlist={() => handleDecision(offer, "SHORTLISTED")}
                        onPass={() => handleDecision(offer, "DISMISSED")}
                      />
                    ))}
                  </div>
                )}

                {displayedCount > 0 && (
                  <div className="mt-6 flex items-center justify-between">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className={`px-3 py-2 rounded-xl text-sm font-semibold border ${
                        page <= 1
                          ? "border-slate-200 text-slate-300 cursor-not-allowed"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      Précédent
                    </button>
                    <div className="text-xs text-slate-500">
                      Page <strong className="text-slate-900">{page}</strong>
                    </div>
                    <button
                      onClick={() => setPage((p) => p + 1)}
                      disabled={displayedCount < pageSize}
                      className={`px-3 py-2 rounded-xl text-sm font-semibold border ${
                        displayedCount < pageSize
                          ? "border-slate-200 text-slate-300 cursor-not-allowed"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      Suivant
                    </button>
                  </div>
                )}
              </>
            )}
          </main>

          {/* Profile summary */}
          <aside className="lg:sticky top-6 self-start">
            <ProfileSummarySidebar
              summary={profileSummary}
              loading={profileSummaryLoading}
              missing={profileSummaryMissing}
              error={profileSummaryError}
              domainSignals={domainSignals}
            />
          </aside>
        </div>
      </div>

      {/* Debug Drawer */}
      {DEBUG_INBOX && (
        <DebugDrawer
          isOpen={debugOpen}
          onClose={() => setDebugOpen(false)}
          items={items}
          displayedCount={displayedCount}
          threshold={threshold}
          lastApiCall={lastApiCall}
          skillsSource={skillsSource}
        />
      )}

      <FiltersDrawer
        isOpen={filtersDrawerOpen}
        draft={filtersDraft}
        onDraftChange={setFiltersDraft}
        threshold={thresholdDraft}
        onThresholdChange={setThresholdDraft}
        filtersDirty={filtersDirty}
        onApply={handleApplyFilters}
        onCancel={handleCancelFilters}
      />

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
          profile={userProfile as Record<string, unknown> ?? undefined}
        />
      )}
    </PremiumAppShell>
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
