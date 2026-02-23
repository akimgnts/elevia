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
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { fetchInbox, postDecision, applyPack, type ApplyPackResponse } from "../lib/api";
import { buildMatchingProfile, type SkillsSource } from "../lib/profileMatching";
import { upsertApplication, listApplications } from "../api/applications";
import { useProfileStore } from "../store/profileStore";
import { SEED_PROFILE } from "../fixtures/seedProfile";

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
  title: string;
  company: string | null;
  country: string | null;
  city: string | null;
  score: number;
  reasons: string[];
  matched_skills: string[];
  missing_skills: string[];
  rome: { rome_code: string; rome_label: string } | null;
  is_vie?: boolean;
  skills_source?: string;
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
    results.push({
      offer_id: offerId,
      title: typeof rec.title === "string" ? rec.title : "Offre",
      company: typeof rec.company === "string" ? rec.company : null,
      country: typeof rec.country === "string" ? rec.country : null,
      city: typeof rec.city === "string" ? rec.city : null,
      score: normalizeScore(rec.score ?? rec.match_score),
      reasons: Array.isArray(rec.reasons) ? (rec.reasons as string[]) : [],
      matched_skills: Array.isArray(rec.matched_skills) ? (rec.matched_skills as string[]) : [],
      missing_skills: Array.isArray(rec.missing_skills) ? (rec.missing_skills as string[]) : [],
      rome: rec.rome && typeof rec.rome === "object" ? (rec.rome as { rome_code: string; rome_label: string }) : null,
      is_vie: typeof rec.is_vie === "boolean" ? rec.is_vie : undefined,
      skills_source: typeof rec.skills_source === "string" ? rec.skills_source : undefined,
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

function OfferCard({
  offer,
  onShortlist,
  onDismiss,
  onApply,
  isShortlisted,
  isPending,
}: {
  offer: NormalizedInboxItem;
  onShortlist: () => void;
  onDismiss: () => void;
  onApply: () => void;
  isShortlisted: boolean;
  isPending: boolean;
}) {
  const location = [offer.city, offer.country].filter(Boolean).join(", ");
  const showFallback = offer.score === 15 && offer.matched_skills.length === 0;

  return (
    <div className={`group bg-white border border-slate-100 rounded-[2rem] p-5 shadow-sm hover:shadow-lg transition-all flex flex-col h-full ${isPending ? "opacity-50 pointer-events-none" : ""}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {offer.is_vie && (
              <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-slate-50 text-slate-600 border border-slate-100">
                V.I.E
              </span>
            )}
            <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
              Score · {offer.score}%
            </span>
            {showFallback && (
              <span className="text-[10px] font-semibold px-2 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                Fallback score (no skill match)
              </span>
            )}
          </div>

          <h3 className="mt-3 text-base font-bold text-slate-900 leading-tight line-clamp-2">
            {offer.title}
          </h3>

          <div className="mt-1 text-xs text-slate-500 flex items-center gap-1 flex-wrap">
            {offer.company && <span className="font-medium text-slate-700">{offer.company}</span>}
            {offer.company && location && <span>·</span>}
            {location && (
              <span className="flex items-center gap-0.5">
                <MapPin className="w-3 h-3" />
                {location}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Matched Skills (top 3) */}
      {offer.matched_skills.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {offer.matched_skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100"
            >
              {skill}
            </span>
          ))}
          {offer.matched_skills.length > 3 && (
            <span className="text-[10px] text-slate-400">+{offer.matched_skills.length - 3}</span>
          )}
        </div>
      ) : (
        <div className="mt-4 text-[11px] text-slate-500">
          Aucune compétence détectée en commun
        </div>
      )}

      {offer.missing_skills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {offer.missing_skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-100"
            >
              {skill}
            </span>
          ))}
          {offer.missing_skills.length > 3 && (
            <span className="text-[10px] text-slate-400">+{offer.missing_skills.length - 3}</span>
          )}
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

      {/* Actions */}
      <div className="mt-auto pt-4 flex flex-wrap items-center gap-2">
        <button
          onClick={onApply}
          className="px-4 py-2 rounded-xl text-sm font-semibold bg-slate-900 text-white hover:bg-slate-800 transition"
        >
          Générer
        </button>

        <button
          onClick={onShortlist}
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
          onClick={onDismiss}
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
  const [searchQuery, setSearchQuery] = useState("");
  const [threshold, setThreshold] = useState<number>(() => {
    const stored = readJson<number | null>(`${STORAGE_PREFIX}_threshold`, null);
    return typeof stored === "number" ? stored : DEFAULT_THRESHOLD;
  });
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

  const profileId = profileHash ?? "anonymous";

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

      const data = await fetchInbox(matchingProfile, profileId, apiMinScore, apiLimit);

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
  }, [userProfile, profileId, setUserProfile]);

  // Initial load
  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true;
      load();
    }
  }, [load]);

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
      .sort((a, b) => b.score - a.score); // Sort by score desc
  }, [availableItems, threshold, searchQuery]);

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
        matched_core: item.matched_skills,
        missing_core: item.missing_skills,
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
                    isShortlisted={trackerStatusMap[offer.offer_id] === "shortlisted"}
                    isPending={pendingDecisions.has(offer.offer_id)}
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
