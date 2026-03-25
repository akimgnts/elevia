import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Loader2, X } from "lucide-react";
import type {
  ContextFit,
  DescriptionStructured,
  DescriptionStructuredV1,
  ExplainBlock,
  ExplainPayloadV1Full,
  CvHtmlResponse,
  ForOfferResponse,
  ForOfferLetterResponse,
  InboxContextPayload,
  OfferContext,
  OfferExplanation,
  OfferIntelligence,
  ProfileSemanticContext,
  ProfileContext,
  ScoringV2,
  SemanticExplainability,
} from "../lib/api";
import { fetchOfferDetail, generateCvForOffer, generateCvHtmlForOffer, generateLetterForOffer } from "../lib/api";
import { CvHtmlPreviewModal } from "./CvHtmlPreviewModal";
import { LetterPreviewModal } from "./LetterPreviewModal";
import { CvPreviewModal } from "./CvPreviewModal";
import { cleanOfferTitle } from "../lib/titleUtils";
import { formatRelativeDate } from "../lib/dateUtils";

export type OfferDetail = {
  offer_id?: string;
  id?: string;
  title: string;
  publication_date?: string | null;
  company?: string | null;
  country?: string | null;
  score?: number | null;
  offer_cluster?: string | null;
  signal_score?: number | null;
  coherence?: "ok" | "suspicious" | null;
  description?: string | null;
  display_description?: string | null;
  description_snippet?: string | null;
  matched_skills?: string[];
  missing_skills?: string[];
  matched_skills_display?: string[];
  missing_skills_display?: string[];
  unmapped_tokens?: string[];
  offer_uri_count?: number;
  intersection_count?: number;
  scoring_unit?: string;
  semantic_score?: number | null;
  semantic_model_version?: string | null;
  relevant_passages?: string[];
  ai_available?: boolean;
  ai_error?: string | null;
  explain?: ExplainBlock | null;
  explanation: OfferExplanation;
  offer_intelligence?: OfferIntelligence | null;
  semantic_explainability?: SemanticExplainability | null;
  scoring_v2?: ScoringV2 | null;
  description_structured?: DescriptionStructured | null;
  description_structured_v1?: DescriptionStructuredV1 | null;
  explain_v1_full?: ExplainPayloadV1Full | null;
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatRoleType(role?: OfferContext["role_type"] | OfferContext["primary_role_type"]) {
  switch (role) {
    case "BI_REPORTING":       return "BI / Reporting";
    case "DATA_ANALYSIS":      return "Data Analysis";
    case "DATA_ENGINEERING":   return "Data Engineering";
    case "PRODUCT_ANALYTICS":  return "Product Analytics";
    case "OPS_ANALYTICS":      return "Ops Analytics";
    case "MIXED":              return "Mixte";
    default:                   return "Inconnu";
  }
}

function stripHtml(input: string) {
  return input.replace(/<[^>]*>/g, " ");
}

function cleanWhitespace(input: string) {
  return input.replace(/\s+/g, " ").trim();
}

function cleanDescription(raw?: string | null) {
  if (!raw) return "";
  return cleanWhitespace(stripHtml(raw));
}

function scoreBadgeClass(score?: number | null) {
  if (score === null || score === undefined) return "bg-neutral-700 text-neutral-200";
  if (score >= 80) return "bg-emerald-500/20 text-emerald-300";
  if (score >= 50) return "bg-amber-500/20 text-amber-300";
  return "bg-rose-500/20 text-rose-300";
}

function fitLabelBadgeClass(label?: string | null) {
  const value = (label || "").toLowerCase();
  if (value.includes("strong") || value.includes("fort")) return "bg-emerald-500/20 text-emerald-300";
  if (value.includes("medium") || value.includes("partial") || value.includes("mod")) {
    return "bg-amber-500/20 text-amber-300";
  }
  if (value.includes("weak") || value.includes("low") || value.includes("faible")) {
    return "bg-rose-500/20 text-rose-300";
  }
  return "bg-neutral-700 text-neutral-200";
}

function formatClusterLabel(cluster?: string | null) {
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

function formatRoleBlockLabel(raw?: string | null) {
  switch (raw) {
    case "data_analytics":
      return "Data / BI";
    case "business_analysis":
      return "Business Analysis";
    case "finance_ops":
      return "Finance Ops";
    case "legal_compliance":
      return "Legal / Compliance";
    case "sales_business_dev":
      return "Sales / BizDev";
    case "marketing_communication":
      return "Marketing / Communication";
    case "hr_ops":
      return "RH";
    case "supply_chain_ops":
      return "Supply Chain";
    case "project_ops":
      return "Project Ops";
    case "software_it":
      return "Software / IT";
    case "generalist_other":
      return "Polyvalent";
    default:
      return null;
  }
}

function toLevel(value: number) {
  if (value >= 0.8) return "fort";
  if (value >= 0.5) return "moyen";
  return "faible";
}

function gapLabel(value: number) {
  if (value >= 0.6) return "gaps importants";
  if (value >= 0.3) return "gaps modérés";
  return "faibles gaps";
}

function uniqueVisible(items: string[], limit: number) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of items) {
    const item = raw.trim();
    if (!item) continue;
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
    if (result.length >= limit) break;
  }
  return result;
}

function SkillGroup({
  label,
  skills,
  className,
  limit = 12,
}: {
  label: string;
  skills: string[];
  className: string;
  limit?: number;
}) {
  if (skills.length === 0) return null;
  const visible = skills.slice(0, limit);
  const hidden = skills.length - visible.length;
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-400">
        {label}
      </div>
      <div className="flex flex-wrap gap-2">
        {visible.map((skill) => (
          <span
            key={`${label}-${skill}`}
            className={`rounded-full px-3 py-1 text-xs font-medium ${className}`}
          >
            {skill}
          </span>
        ))}
        {hidden > 0 && (
          <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-400">
            +{hidden} more
          </span>
        )}
      </div>
    </div>
  );
}

// Collapsible section wrapper for DEV mode
function DebugSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-amber-900/40 bg-amber-950/10">
      <button
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-xs font-semibold text-amber-400 hover:text-amber-300"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
        <span className="uppercase tracking-wide">[DEV] {title}</span>
      </button>
      {open && (
        <div className="border-t border-amber-900/30 px-4 pb-4 pt-3 text-xs text-neutral-300 space-y-3">
          {children}
        </div>
      )}
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function OfferDetailModal({
  offer,
  onClose,
  showDebug = false,
  offerContext,
  profileContext,
  contextFit,
  contextLoading = false,
  contextError = null,
  profile,
}: {
  offer: OfferDetail;
  onClose: () => void;
  showDebug?: boolean;
  offerContext?: OfferContext | null;
  profileContext?: ProfileContext | null;
  contextFit?: ContextFit | null;
  contextLoading?: boolean;
  contextError?: string | null;
  profile?: Record<string, unknown> | null;
}) {
  const [visible, setVisible] = useState(false);
  const [showFullDescription, setShowFullDescription] = useState(false);

  // Structured description state (v0)
  const [structured, setStructured] = useState<DescriptionStructured | null>(
    offer.description_structured ?? null
  );
  const [structuredLoading, setStructuredLoading] = useState(false);

  // Compass v1 data state
  const [structuredV1, setStructuredV1] = useState<DescriptionStructuredV1 | null>(
    offer.description_structured_v1 ?? null
  );
  const [explainV1Full, setExplainV1Full] = useState<ExplainPayloadV1Full | null>(
    offer.explain_v1_full ?? null
  );
  const [offerIntelligence, setOfferIntelligence] = useState<OfferIntelligence | null>(
    offer.offer_intelligence ?? null
  );
  const [semanticExplainability, setSemanticExplainability] = useState<SemanticExplainability | null>(
    offer.semantic_explainability ?? null
  );
  const [scoringV2, setScoringV2] = useState<ScoringV2 | null>(
    offer.scoring_v2 ?? null
  );

  // CV generation state
  const [cvLoading, setCvLoading] = useState(false);
  const [cvPreview, setCvPreview] = useState<ForOfferResponse | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);
  const [cvHtmlLoading, setCvHtmlLoading] = useState(false);
  const [cvHtmlPreview, setCvHtmlPreview] = useState<CvHtmlResponse | null>(null);
  const [cvHtmlError, setCvHtmlError] = useState<string | null>(null);

  // Letter generation state
  const [letterLoading, setLetterLoading] = useState(false);
  const [letterPreview, setLetterPreview] = useState<ForOfferLetterResponse | null>(null);
  const [letterError, setLetterError] = useState<string | null>(null);
  const detailFetchKeyRef = useRef<string | null>(null);

  async function handleGenerateCv() {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    setCvLoading(true);
    setCvError(null);
    try {
      const ctx: InboxContextPayload | undefined =
        offer.matched_skills_display?.length || offer.matched_skills?.length
          ? {
              matched_skills: offer.matched_skills_display ?? offer.matched_skills ?? [],
              missing_skills: offer.missing_skills_display ?? offer.missing_skills ?? [],
            }
          : undefined;
      const result = await generateCvForOffer(offerId, profile ?? {}, ctx);
      setCvPreview(result);
    } catch (err) {
      setCvError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setCvLoading(false);
    }
  }

  async function handleGenerateCvHtml() {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    setCvHtmlLoading(true);
    setCvHtmlError(null);
    try {
      const ctx: InboxContextPayload | undefined =
        offer.matched_skills_display?.length || offer.matched_skills?.length
          ? {
              matched_skills: offer.matched_skills_display ?? offer.matched_skills ?? [],
              missing_skills: offer.missing_skills_display ?? offer.missing_skills ?? [],
            }
          : undefined;
      const result = await generateCvHtmlForOffer(offerId, profile ?? {}, ctx);
      setCvHtmlPreview(result);
    } catch (err) {
      setCvHtmlError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setCvHtmlLoading(false);
    }
  }

  async function handleGenerateLetter() {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    setLetterLoading(true);
    setLetterError(null);
    try {
      const ctx: InboxContextPayload | undefined =
        offer.matched_skills_display?.length || offer.matched_skills?.length
          ? {
              matched_skills: offer.matched_skills_display ?? offer.matched_skills ?? [],
              missing_skills: offer.missing_skills_display ?? offer.missing_skills ?? [],
            }
          : undefined;
      const result = await generateLetterForOffer(offerId, profile ?? {}, ctx);
      setLetterPreview(result);
    } catch (err) {
      setLetterError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLetterLoading(false);
    }
  }

  useEffect(() => {
    setVisible(true);
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = original; };
  }, []);

  const profileIntelligence = useMemo(
    () =>
      profile && typeof profile === "object" && profile !== null
        ? ((profile as { profile_intelligence?: ProfileSemanticContext }).profile_intelligence ?? null)
        : null,
    [profile]
  );

  // Fetch structured description on mount if not already provided
  useEffect(() => {
    if (structured) return; // already have it
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    const requestKey = JSON.stringify({
      offerId,
      matchingScore: offer.score ?? null,
      profileRole: profileIntelligence?.dominant_role_block ?? null,
      profileDomains: profileIntelligence?.dominant_domains ?? [],
    });
    if (detailFetchKeyRef.current === requestKey) return;
    detailFetchKeyRef.current = requestKey;
    setStructuredLoading(true);
    fetchOfferDetail(offerId, profileIntelligence, offer.score ?? null)
      .then((detail) => {
        if (detail.description_structured) {
          setStructured(detail.description_structured);
        }
        if (detail.description_structured_v1) {
          setStructuredV1(detail.description_structured_v1);
        }
        if (detail.explain_v1_full) {
          setExplainV1Full(detail.explain_v1_full);
        }
        if (detail.offer_intelligence) {
          setOfferIntelligence(detail.offer_intelligence);
        }
        if (detail.semantic_explainability) {
          setSemanticExplainability(detail.semantic_explainability);
        }
        if (detail.scoring_v2) {
          setScoringV2(detail.scoring_v2);
        }
      })
      .catch((err: unknown) => {
        console.error("[offer-detail] enrichment fetch failed:", err);
        setStructuredLoading(false);
      })
      .finally(() => {
        if (detailFetchKeyRef.current === requestKey) {
          detailFetchKeyRef.current = null;
        }
        setStructuredLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offer.offer_id, offer.id, offer.score, profileIntelligence, structured]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const description = useMemo(
    () => cleanDescription(offer.display_description || offer.description || ""),
    [offer.display_description, offer.description]
  );

  const matched = offer.matched_skills_display ?? offer.matched_skills ?? [];
  const missing = offer.missing_skills_display ?? offer.missing_skills ?? [];
  const unmapped = offer.unmapped_tokens ?? [];
  const explain = offer.explain ?? null;
  const explanation = offer.explanation;
  const intelligence = offerIntelligence ?? offer.offer_intelligence ?? null;
  const semantic = semanticExplainability ?? offer.semantic_explainability ?? null;
  const scoreV2 = scoringV2 ?? offer.scoring_v2 ?? null;
  const nearMatches = explain?.near_matches ?? [];
  const nearSummary = explain?.near_match_summary ?? null;
  const titleInfo = useMemo(() => cleanOfferTitle(offer.title), [offer.title]);
  const relativeDate = offer.publication_date
    ? formatRelativeDate(offer.publication_date)
    : null;
  const clusterLabel = formatClusterLabel(offer.offer_cluster);
  const signalLabel =
    typeof offer.signal_score === "number" ? `Signal ${offer.signal_score.toFixed(1)}` : null;
  const isSuspicious = offer.coherence === "suspicious";
  const visibleStrengths = uniqueVisible(explanation.strengths, 5);
  const visibleBlockers = uniqueVisible(explanation.blockers, 3);
  const visibleGaps = uniqueVisible(
    explanation.gaps.filter(
      (gap) => !visibleBlockers.some((blocker) => blocker.toLowerCase() === gap.toLowerCase())
    ),
    visibleBlockers.length > 0 ? 2 : 3
  );
  const visibleMissing = [...visibleBlockers, ...visibleGaps];
  const visibleNextActions = uniqueVisible(explanation.next_actions, 3);
  const primaryNextAction = visibleNextActions[0] ?? null;
  const secondaryNextActions = visibleNextActions.slice(1);
  const roleBlockLabel = formatRoleBlockLabel(intelligence?.dominant_role_block);
  const visibleOfferSignals = uniqueVisible(
    intelligence?.top_offer_signals?.length
      ? intelligence.top_offer_signals
      : intelligence?.required_skills ?? [],
    5
  );
  const visibleRequiredSkills = uniqueVisible(intelligence?.required_skills ?? [], 5);
  const visibleOptionalSkills = uniqueVisible(intelligence?.optional_skills ?? [], 3);
  const semanticMatchedSignals = uniqueVisible(semantic?.signal_alignment?.matched_signals ?? [], 5);
  const semanticMissingSignals = uniqueVisible(semantic?.signal_alignment?.missing_core_signals ?? [], 3);
  const semanticSharedDomains = uniqueVisible(semantic?.domain_alignment?.shared_domains ?? [], 3);
  const profileRoleLabel = formatRoleBlockLabel(semantic?.role_alignment?.profile_role);
  const offerRoleLabel = formatRoleBlockLabel(semantic?.role_alignment?.offer_role);
  const semanticSummary = semantic?.alignment_summary ?? explanation.summary_reason;
  const semanticAlignment = semantic?.role_alignment?.alignment;
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
      ? "bg-emerald-500/20 text-emerald-300"
      : semanticAlignment === "medium"
        ? "bg-amber-500/20 text-amber-300"
        : "bg-neutral-800 text-neutral-200";
  const scoreV2Pct =
    typeof scoreV2?.score_pct === "number"
      ? scoreV2.score_pct
      : typeof scoreV2?.score === "number"
        ? Math.round(scoreV2.score * 100)
        : null;

  const descriptionPreview = useMemo(() => {
    if (!description) return "";
    if (showFullDescription || description.length <= 600) return description;
    return `${description.slice(0, 600).trim()}…`;
  }, [description, showFullDescription]);

  return (
    <>
    <div
      className={`fixed inset-0 z-50 flex items-start justify-center bg-black/50 backdrop-blur-sm transition-opacity duration-200 ${
        visible ? "opacity-100" : "opacity-0"
      }`}
      onClick={onClose}
      aria-modal="true"
      role="dialog"
    >
      <div
        className={`w-full h-full sm:h-auto sm:max-h-[85vh] sm:max-w-4xl sm:mt-12 sm:mx-auto bg-neutral-900 text-neutral-100 shadow-2xl overflow-y-auto transition-transform duration-200 ${
          visible ? "scale-100" : "scale-95"
        } rounded-none sm:rounded-2xl p-4 sm:p-8`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-xl font-semibold text-white">{titleInfo.display}</h2>
            {titleInfo.changes.length > 0 && titleInfo.original && (
              <p className="mt-1 text-xs text-neutral-500">Titre original : {titleInfo.original}</p>
            )}
            {offer.company && (
              <p className="mt-1 text-sm text-neutral-400">{offer.company}</p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {offer.country && (
                <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-300">
                  {offer.country}
                </span>
              )}
              {clusterLabel && (
                <span className="rounded-full bg-neutral-100 px-3 py-1 text-xs text-neutral-900">
                  {clusterLabel}
                </span>
              )}
              {roleBlockLabel && (
                <span className="rounded-full bg-cyan-500/15 px-3 py-1 text-xs text-cyan-200">
                  {roleBlockLabel}
                </span>
              )}
              {relativeDate && (
                <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-300">
                  {relativeDate.label}
                </span>
              )}
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreBadgeClass(offer.score)}`}>
                Score {offer.score ?? "—"}
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${fitLabelBadgeClass(explanation.fit_label)}`}>
                {explanation.fit_label}
              </span>
              {signalLabel && (
                <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-300">
                  {signalLabel}
                </span>
              )}
              {isSuspicious && (
                <span className="rounded-full bg-rose-500/20 px-3 py-1 text-xs text-rose-300">
                  Incohérent
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Generate CV CTA */}
            <button
              onClick={handleGenerateCv}
              disabled={cvLoading}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 text-xs font-medium text-white transition-colors"
              title="Générer un CV ciblé pour cette offre"
            >
              {cvLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <FileText className="h-3 w-3" />
              )}
              {cvLoading ? "Génération…" : "Générer CV"}
            </button>
            <button
              onClick={handleGenerateCvHtml}
              disabled={cvHtmlLoading}
              className="flex items-center gap-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 text-xs font-medium text-white transition-colors"
              title="Voir le CV en HTML"
            >
              {cvHtmlLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <FileText className="h-3 w-3" />
              )}
              {cvHtmlLoading ? "Génération…" : "Voir CV (HTML)"}
            </button>
            {/* Generate Letter CTA */}
            <button
              onClick={handleGenerateLetter}
              disabled={letterLoading}
              className="flex items-center gap-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 text-xs font-medium text-white transition-colors"
              title="Générer une lettre ciblée pour cette offre"
            >
              {letterLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <FileText className="h-3 w-3" />
              )}
              {letterLoading ? "Génération…" : "Générer lettre"}
            </button>
            <button
              onClick={onClose}
              className="rounded-lg border border-neutral-700 p-2 text-neutral-300 hover:text-white hover:border-neutral-500"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <section className="mt-6">
          <div className="rounded-2xl border border-neutral-800 bg-neutral-950/40 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-neutral-500">
                  Verdict
                </div>
                <p className="max-w-2xl text-sm leading-relaxed text-neutral-200">
                  {semanticSummary}
                </p>
                {intelligence?.offer_summary && (
                  <p className="max-w-2xl text-xs leading-relaxed text-neutral-400">
                    {intelligence.offer_summary}
                  </p>
                )}
              </div>
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/70 px-4 py-3 text-right">
                <div className="text-[11px] uppercase tracking-wide text-neutral-500">Fit</div>
                <div className="mt-1 text-2xl font-semibold text-white">{explanation.score ?? offer.score ?? "—"}</div>
                <div className="mt-1 text-xs text-neutral-400">{explanation.fit_label}</div>
              </div>
            </div>
          </div>
        </section>

        {/* CV error notice */}
        {cvError && (
          <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-2 text-xs text-rose-300">
            Génération échouée : {cvError}
          </div>
        )}
        {cvHtmlError && (
          <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-2 text-xs text-rose-300">
            Génération CV HTML échouée : {cvHtmlError}
          </div>
        )}
        {letterError && (
          <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-2 text-xs text-rose-300">
            Génération lettre échouée : {letterError}
          </div>
        )}

        <section className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          {semantic && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 lg:col-span-2">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-100">Lecture du match</h3>
                  <p className="mt-2 max-w-3xl text-sm leading-relaxed text-neutral-300">
                    {semantic.alignment_summary}
                  </p>
                </div>
                {semanticAlignmentLabel && (
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${semanticAlignmentTone}`}>
                    {semanticAlignmentLabel}
                  </span>
                )}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {profileRoleLabel && (
                  <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-200">
                    Profil: {profileRoleLabel}
                  </span>
                )}
                {offerRoleLabel && (
                  <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-200">
                    Poste: {offerRoleLabel}
                  </span>
                )}
                {semanticSharedDomains.map((domain) => (
                  <span
                    key={`semantic-shared-domain-${domain}`}
                    className="rounded-full bg-sky-500/15 px-3 py-1 text-xs font-medium text-sky-200"
                  >
                    Domaine commun: {domain}
                  </span>
                ))}
              </div>
              {(semanticMatchedSignals.length > 0 || semanticMissingSignals.length > 0) && (
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  {semanticMatchedSignals.length > 0 && (
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-neutral-500">
                        Signaux communs
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {semanticMatchedSignals.map((signal) => (
                          <span
                            key={`semantic-match-${signal}`}
                            className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-300"
                          >
                            {signal}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {semanticMissingSignals.length > 0 && (
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-neutral-500">
                        Signaux manquants
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {semanticMissingSignals.map((signal) => (
                          <span
                            key={`semantic-missing-${signal}`}
                            className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-300"
                          >
                            {signal}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              {scoreV2 && scoreV2Pct !== null && (
                <div className="mt-4 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-neutral-500">
                    Lecture du score
                  </div>
                  <div className="mt-2 text-sm font-semibold text-white">
                    Score métier: {scoreV2Pct}%
                  </div>
                  <div className="mt-3 grid gap-2 text-xs text-neutral-300 sm:grid-cols-2">
                    <div>Métier: {toLevel(scoreV2.components.role_alignment)}</div>
                    <div>Domaines: {toLevel(scoreV2.components.domain_alignment)}</div>
                    <div>Matching: {toLevel(scoreV2.components.matching_base)}</div>
                    <div>Gaps: {gapLabel(scoreV2.components.gap_penalty)}</div>
                  </div>
                </div>
              )}
            </div>
          )}
          {(visibleOfferSignals.length > 0 || (intelligence?.dominant_domains?.length ?? 0) > 0) && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 lg:col-span-2">
              <h3 className="text-sm font-semibold text-neutral-100">Ce que le poste demande vraiment</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {(intelligence?.dominant_domains ?? []).slice(0, 3).map((domain) => (
                  <span
                    key={`offer-domain-${domain}`}
                    className="rounded-full bg-sky-500/15 px-3 py-1 text-xs font-medium text-sky-200"
                  >
                    {domain}
                  </span>
                ))}
                {visibleOfferSignals.map((signal) => (
                  <span
                    key={`offer-signal-${signal}`}
                    className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-200"
                  >
                    {signal}
                  </span>
                ))}
              </div>
            </div>
          )}

          {visibleStrengths.length > 0 && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4">
              <h3 className="text-sm font-semibold text-neutral-100">Pourquoi ça colle</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {visibleStrengths.map((strength) => (
                  <span
                    key={strength}
                    className="rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-300"
                  >
                    {strength}
                  </span>
                ))}
              </div>
            </div>
          )}
          {(visibleMissing.length > 0 || primaryNextAction) && (
            <div className="space-y-4">
              {visibleMissing.length > 0 && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4">
                  <h3 className="text-sm font-semibold text-neutral-100">Ce qui manque</h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {visibleMissing.map((item, index) => (
                      <span
                        key={`${item}-${index}`}
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          index < visibleBlockers.length
                            ? "bg-rose-500/15 text-rose-300"
                            : "bg-amber-500/15 text-amber-300"
                        }`}
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {primaryNextAction && (
                <div className="rounded-xl border border-cyan-900/50 bg-cyan-950/20 p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-400">
                    Prochaine action
                  </div>
                  <p className="mt-2 text-sm text-cyan-50">{primaryNextAction}</p>
                  {secondaryNextActions.length > 0 && (
                    <ul className="mt-3 space-y-1 text-xs text-cyan-100/80">
                      {secondaryNextActions.map((action) => (
                        <li key={action} className="flex gap-2">
                          <span className="text-cyan-400">•</span>
                          <span>{action}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
          {(visibleRequiredSkills.length > 0 || visibleOptionalSkills.length > 0) && (
            <div className="space-y-4">
              {visibleRequiredSkills.length > 0 && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4">
                  <h3 className="text-sm font-semibold text-neutral-100">Compétences requises</h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {visibleRequiredSkills.map((item) => (
                      <span
                        key={`required-${item}`}
                        className="rounded-full bg-slate-100/10 px-3 py-1 text-xs font-medium text-slate-100"
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {visibleOptionalSkills.length > 0 && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4">
                  <h3 className="text-sm font-semibold text-neutral-100">Compétences bonus</h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {visibleOptionalSkills.map((item) => (
                      <span
                        key={`optional-${item}`}
                        className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-200"
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Description — structured sections (with raw fallback) */}
        <section className="mt-6 space-y-4">
          {structuredLoading && !structured && (
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              Chargement de la description…
            </div>
          )}

          {structured ? (
            <>
              {/* Résumé */}
              {structured.summary && (
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200">Résumé</h3>
                  <p className="mt-2 text-sm leading-relaxed text-neutral-300">{structured.summary}</p>
                </div>
              )}

              {/* Missions */}
              {structured.missions.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200">Missions</h3>
                  <ul className="mt-2 space-y-1">
                    {structured.missions.map((m, i) => (
                      <li key={`mission-${i}`} className="flex gap-2 text-sm text-neutral-300">
                        <span className="mt-0.5 shrink-0 text-neutral-500">•</span>
                        <span>{m}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Profil */}
              {structured.profile.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200">Profil recherché</h3>
                  <ul className="mt-2 space-y-1">
                    {structured.profile.map((p, i) => (
                      <li key={`profile-${i}`} className="flex gap-2 text-sm text-neutral-300">
                        <span className="mt-0.5 shrink-0 text-neutral-500">•</span>
                        <span>{p}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Compétences — chips */}
              {structured.competences.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200">Compétences demandées</h3>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {structured.competences.map((c) => (
                      <span
                        key={`comp-${c}`}
                        className="rounded-full bg-neutral-800 px-3 py-1 text-xs text-neutral-200"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Contexte */}
              {structured.context && (
                <div>
                  <h3 className="text-sm font-semibold text-neutral-200">Contexte</h3>
                  <p className="mt-2 text-sm leading-relaxed text-neutral-300">{structured.context}</p>
                </div>
              )}

              {/* Voir original — debug only */}
              {showDebug && (
                <DebugSection title="Description originale">
                  <p className="text-xs text-neutral-400 whitespace-pre-wrap leading-relaxed">
                    {descriptionPreview || "Description indisponible."}
                  </p>
                  {description.length > 600 && (
                    <button
                      className="mt-2 text-xs font-semibold text-neutral-400 hover:text-neutral-200"
                      onClick={() => setShowFullDescription((prev) => !prev)}
                    >
                      {showFullDescription ? "Réduire" : "Voir complète"}
                    </button>
                  )}
                </DebugSection>
              )}
            </>
          ) : (
            /* Fallback: raw description */
            !structuredLoading && (
              <div>
                <h3 className="text-sm font-semibold text-neutral-200">Description</h3>
                <p className="mt-2 text-sm leading-relaxed text-neutral-300">
                  {descriptionPreview || "Description indisponible."}
                </p>
                {description.length > 600 && (
                  <button
                    className="mt-2 text-xs font-semibold text-neutral-400 hover:text-neutral-200"
                    onClick={() => setShowFullDescription((prev) => !prev)}
                  >
                    {showFullDescription ? "Réduire la description" : "Voir description complète"}
                  </button>
                )}
              </div>
            )
          )}
        </section>

        {showDebug && (
          <>
            <section className="mt-6 space-y-3">
              <h3 className="text-sm font-semibold text-neutral-200">Alignement</h3>
              {contextLoading && !contextFit && (
                <div className="text-xs text-neutral-500">Calcul de l'alignement…</div>
              )}
              {!contextLoading && !contextFit && (
                <div className="text-xs text-neutral-500">Alignement indisponible pour le moment.</div>
              )}
              {contextFit && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 text-xs text-neutral-300 space-y-3">
                  {contextFit.fit_summary && (
                    <div className="text-sm font-medium text-neutral-100 leading-relaxed">
                      {contextFit.fit_summary}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <span className="rounded-full bg-neutral-800 px-3 py-1 text-[10px] text-neutral-300">
                      Confiance · {Math.round((contextFit.confidence || 0) * 100)}%
                    </span>
                  </div>
                  {contextFit.why_it_fits.length > 0 && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-neutral-500">Pourquoi ça colle</div>
                      <ul className="mt-1 list-disc list-inside space-y-1">
                        {contextFit.why_it_fits.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {contextFit.likely_frictions.length > 0 && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-neutral-500">Points de friction</div>
                      <ul className="mt-1 list-disc list-inside space-y-1">
                        {contextFit.likely_frictions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {contextFit.clarifying_questions.length > 0 && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-neutral-500">Questions de clarification</div>
                      <ul className="mt-1 list-disc list-inside space-y-1">
                        {contextFit.clarifying_questions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-neutral-500">Angle CV</div>
                      <ul className="mt-1 list-disc list-inside space-y-1">
                        {contextFit.recommended_angle.cv_focus.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-neutral-500">Accroches lettre</div>
                      <ul className="mt-1 list-disc list-inside space-y-1">
                        {contextFit.recommended_angle.cover_letter_hooks.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  {contextFit.evidence_spans.length > 0 && (
                    <div className="rounded-lg border border-neutral-800 p-3 text-[10px] text-neutral-400">
                      <div className="font-semibold text-neutral-300 mb-1">Preuves fit</div>
                      <ul className="space-y-1">
                        {contextFit.evidence_spans.map((span, idx) => (
                          <li key={`fit-span-${idx}`}>
                            <span className="text-neutral-500">{span.field}:</span> {span.span}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {contextError && (
                <div className="text-xs text-rose-300">Erreur contexte: {contextError}</div>
              )}
            </section>

            <section className="mt-6 space-y-5">
              <h3 className="text-sm font-semibold text-neutral-200">Compétences demandées</h3>
              {typeof offer.intersection_count === "number" && typeof offer.offer_uri_count === "number" && (
                <div className="text-xs text-neutral-500">
                  {offer.intersection_count} compétences reconnues sur {offer.offer_uri_count}
                </div>
              )}
              <SkillGroup label="Compétences alignées" skills={matched} className="bg-green-600/20 text-green-400" />
              <SkillGroup label="Compétences manquantes" skills={missing} className="bg-red-600/20 text-red-400" />
              {nearMatches.length > 0 && (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-neutral-200">Compétences proches</h4>
                    {nearSummary && (
                      <span className="text-[10px] text-neutral-500">
                        {nearSummary.count} signaux · max {nearSummary.max_strength.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[10px] text-neutral-500">
                    Signal proche, non compté comme match exact.
                  </p>
                  <ul className="mt-2 space-y-1">
                    {nearMatches.slice(0, 6).map((item, idx) => (
                      <li key={`near-${idx}`} className="text-xs text-neutral-300">
                        {item.profile_label} → {item.offer_label}
                        <span className="text-[10px] text-neutral-500">
                          {" "}· {item.relation} · {item.strength.toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <SkillGroup label="Non mappées ESCO (debug)" skills={unmapped} className="bg-neutral-700 text-neutral-300" />
              {matched.length === 0 && missing.length === 0 && unmapped.length === 0 && (
                <p className="text-sm text-neutral-500">Aucune compétence fournie.</p>
              )}
            </section>

            {explain && (
              <section className="mt-6 space-y-3">
                <h3 className="text-sm font-semibold text-neutral-200">Détail du score</h3>
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 text-xs text-neutral-300">
                  <div className="flex items-center justify-between">
                    <span>Compétences ({explain.breakdown.skills_weight}%)</span>
                    <span>{explain.breakdown.skills_score.toFixed(1)} pts</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Langues ({explain.breakdown.language_weight}%)</span>
                    <span>{explain.breakdown.language_score.toFixed(1)} pts</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Formation ({explain.breakdown.education_weight}%)</span>
                    <span>{explain.breakdown.education_score.toFixed(1)} pts</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Pays ({explain.breakdown.country_weight}%)</span>
                    <span>{explain.breakdown.country_score.toFixed(1)} pts</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between font-semibold text-neutral-100">
                    <span>Total</span>
                    <span>{explain.breakdown.total.toFixed(1)} / 100</span>
                  </div>
                </div>
              </section>
            )}

            {explainV1Full && (
              <section className="mt-6 space-y-3">
                <h3 className="text-sm font-semibold text-neutral-200">Preuve du match</h3>
                <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 text-xs text-neutral-300 space-y-3">

                  <div className="flex flex-wrap gap-2">
                    <span className={`rounded-full px-3 py-1 text-[10px] font-semibold ${
                      explainV1Full.confidence === "HIGH"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : explainV1Full.confidence === "MED"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-rose-500/20 text-rose-300"
                    }`}>
                      Confiance {explainV1Full.confidence}
                    </span>
                    <span className={`rounded-full px-3 py-1 text-[10px] font-semibold ${
                      explainV1Full.rare_signal_level === "HIGH"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : explainV1Full.rare_signal_level === "MED"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-rose-500/20 text-rose-300"
                    }`}>
                      Signal rare {explainV1Full.rare_signal_level}
                    </span>
                    {explainV1Full.sector_signal_level && (
                      <span className={`rounded-full px-3 py-1 text-[10px] font-semibold ${
                        explainV1Full.sector_signal_level === "HIGH"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : explainV1Full.sector_signal_level === "MED"
                            ? "bg-amber-500/20 text-amber-300"
                            : "bg-rose-500/20 text-rose-300"
                      }`}>
                        Secteur {explainV1Full.sector_signal_level}
                        {explainV1Full.sector_signal_note && ` · ${explainV1Full.sector_signal_note}`}
                      </span>
                    )}
                  </div>

                  {explainV1Full.incoherence_reasons.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {explainV1Full.incoherence_reasons.map((reason) => (
                        <span key={reason} className="rounded-full bg-neutral-800 px-2.5 py-0.5 text-[10px] text-neutral-400">
                          {reason.replace("TOOL_UNSPECIFIED:", "Outil non précisé : ").replace(/_/g, " ").toLowerCase()}
                        </span>
                      ))}
                    </div>
                  )}

                  {explainV1Full.missing_offer_skills.length > 0 && (
                    <div>
                      <div className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-500">
                        Compétences de l'offre ({explainV1Full.missing_offer_skills.length})
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {explainV1Full.missing_offer_skills.map((s, i) => (
                          <span key={`ms-${i}`} className="rounded-full bg-neutral-800 px-2.5 py-0.5 text-[10px] text-neutral-300">
                            {s.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {explainV1Full.tool_notes.length > 0 && (
                    <div>
                      <div className="mb-1.5 text-[10px] uppercase tracking-wide text-neutral-500">Outils détectés</div>
                      <div className="space-y-1">
                        {explainV1Full.tool_notes.map((note) => (
                          <div key={note.tool_key} className="flex items-center gap-2 text-[10px]">
                            <span className="font-semibold text-neutral-200 uppercase">{note.tool_key}</span>
                            <span className={`rounded-full px-2 py-0.5 ${
                              note.status === "SPECIFIED"
                                ? "bg-emerald-500/20 text-emerald-300"
                                : note.status === "UNSPECIFIED"
                                  ? "bg-amber-500/20 text-amber-300"
                                  : "bg-neutral-700 text-neutral-400"
                            }`}>
                              {note.status === "SPECIFIED" && note.sense
                                ? `précisé · ${note.sense}`
                                : note.status === "UNSPECIFIED"
                                  ? "outil non précisé"
                                  : note.status.toLowerCase()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </section>
            )}
          </>
        )}

        {/* ── DESCRIPTION STRUCTURÉE v1 (Compass text structurer) ──────────────── */}
        {structuredV1 && (structuredV1.missions.length > 0 || structuredV1.requirements.length > 0 || structuredV1.tools_stack.length > 0) && (
          <section className="mt-6 space-y-3">
            <h3 className="text-sm font-semibold text-neutral-200">Description structurée</h3>
            <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 space-y-4">

              {structuredV1.missions.length > 0 && (
                <div>
                  <div className="mb-2 text-[10px] uppercase tracking-wide text-neutral-500">Missions</div>
                  <ul className="space-y-1">
                    {structuredV1.missions.map((m, i) => (
                      <li key={`sv1m-${i}`} className="flex gap-2 text-xs text-neutral-300">
                        <span className="mt-0.5 shrink-0 text-neutral-600">•</span>
                        <span>{m}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {structuredV1.requirements.length > 0 && (
                <div>
                  <div className="mb-2 text-[10px] uppercase tracking-wide text-neutral-500">Profil recherché</div>
                  <ul className="space-y-1">
                    {structuredV1.requirements.map((r, i) => (
                      <li key={`sv1r-${i}`} className="flex gap-2 text-xs text-neutral-300">
                        <span className="mt-0.5 shrink-0 text-neutral-600">•</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {structuredV1.tools_stack.length > 0 && (
                <div>
                  <div className="mb-2 text-[10px] uppercase tracking-wide text-neutral-500">Stack technique</div>
                  <div className="flex flex-wrap gap-1.5">
                    {structuredV1.tools_stack.map((t) => (
                      <span key={`sv1t-${t}`} className="rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-200">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {structuredV1.context.length > 0 && (
                <div>
                  <div className="mb-2 text-[10px] uppercase tracking-wide text-neutral-500">Contexte</div>
                  <div className="flex flex-wrap gap-1.5">
                    {structuredV1.context.map((tag) => (
                      <span key={`sv1c-${tag}`} className="rounded-full bg-blue-500/20 px-2.5 py-0.5 text-[10px] text-blue-300">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {structuredV1.red_flags.length > 0 && (
                <div>
                  <div className="mb-2 text-[10px] uppercase tracking-wide text-neutral-500">Points d'attention</div>
                  <div className="flex flex-wrap gap-1.5">
                    {structuredV1.red_flags.map((flag) => (
                      <span key={`sv1f-${flag}`} className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] text-amber-300">
                        {flag.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ── DEV SECTIONS — collapsible, hidden in user mode ──────────────────── */}
        {showDebug && (
          <div className="mt-8 space-y-3">
            <div className="text-[10px] uppercase tracking-wide text-amber-500 font-semibold">
              Mode debug activé (localStorage: elevia_debug_inbox=1)
            </div>

            {/* DEV: Contexte de l'offre */}
            {offerContext && (
              <DebugSection title="Contexte de l'offre">
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Mission</div>
                  <div className="mt-1">{offerContext.mission_summary || "—"}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full bg-neutral-800 px-3 py-1 text-[10px] text-neutral-300">
                    role_type · {formatRoleType(offerContext.role_type)}
                  </span>
                  <span className="rounded-full bg-amber-900/40 px-3 py-1 text-[10px] text-amber-300">
                    primary_role · {formatRoleType(offerContext.primary_role_type)}
                  </span>
                  <span className="rounded-full bg-neutral-800 px-3 py-1 text-[10px] text-neutral-300">
                    Confiance · {Math.round((offerContext.confidence || 0) * 100)}%
                  </span>
                </div>
                {offerContext.role_type_reason && (
                  <div className="text-[10px] text-amber-400 italic">{offerContext.role_type_reason}</div>
                )}
                {offerContext.responsibilities.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Responsabilités</div>
                    <ul className="mt-1 list-disc list-inside space-y-1">
                      {offerContext.responsibilities.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {offerContext.tools_stack_signals.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Outils</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {offerContext.tools_stack_signals.map((tool) => (
                        <span key={tool} className="rounded-full bg-neutral-800 px-3 py-1 text-[10px] text-neutral-200">
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Style de travail</div>
                    <div className="mt-1">Autonomie: {offerContext.work_style_signals.autonomy_level}</div>
                    <div className="mt-1">Parties prenantes: {offerContext.work_style_signals.stakeholder_exposure}</div>
                    <div className="mt-1">Cadence: {offerContext.work_style_signals.cadence}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Environnement</div>
                    <div className="mt-1">Organisation: {offerContext.environment_signals.org_type}</div>
                    <div className="mt-1">Domaine: {offerContext.environment_signals.domain || "—"}</div>
                    <div className="mt-1">Maturité data: {offerContext.environment_signals.data_maturity}</div>
                  </div>
                </div>
                {offerContext.needs_clarification.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">À clarifier</div>
                    <ul className="mt-1 list-disc list-inside space-y-1">
                      {offerContext.needs_clarification.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {offerContext.evidence_spans.length > 0 && (
                  <div className="rounded-lg border border-neutral-800 p-3 text-[10px] text-neutral-400">
                    <div className="font-semibold text-neutral-300 mb-1">Preuves offre</div>
                    <ul className="space-y-1">
                      {offerContext.evidence_spans.map((span, idx) => (
                        <li key={`offer-span-${idx}`}>
                          <span className="text-neutral-500">{span.field}:</span> {span.span}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </DebugSection>
            )}

            {/* DEV: Contexte du profil */}
            {profileContext && (
              <DebugSection title="Contexte du profil">
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Trajectoire</div>
                  <div className="mt-1">{profileContext.trajectory_summary || "—"}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full bg-neutral-800 px-3 py-1 text-[10px] text-neutral-300">
                    Confiance · {Math.round((profileContext.confidence || 0) * 100)}%
                  </span>
                </div>
                {profileContext.dominant_strengths.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Forces dominantes</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {profileContext.dominant_strengths.map((item) => (
                        <span key={item} className="rounded-full bg-neutral-800 px-3 py-1 text-[10px] text-neutral-200">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {profileContext.profile_tools_signals.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Outils détectés (profil)</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {profileContext.profile_tools_signals.map((tool) => (
                        <span key={tool} className="rounded-full bg-amber-900/30 px-3 py-1 text-[10px] text-amber-200">
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Signaux d'expérience</div>
                    <div className="mt-1">Analyse vs exécution: {profileContext.experience_signals.analysis_vs_execution}</div>
                    <div className="mt-1">Autonomie: {profileContext.experience_signals.autonomy_signal}</div>
                    <div className="mt-1">Stakeholders: {profileContext.experience_signals.stakeholder_signal}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Préférences</div>
                    <div className="mt-1">Cadence: {profileContext.preferred_work_signals.cadence_preference}</div>
                    <div className="mt-1">Environnement: {profileContext.preferred_work_signals.environment_preference}</div>
                  </div>
                </div>
                {profileContext.gaps_or_unknowns.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-wide text-neutral-500">Zones d'ombre</div>
                    <ul className="mt-1 list-disc list-inside space-y-1">
                      {profileContext.gaps_or_unknowns.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {profileContext.evidence_spans.length > 0 && (
                  <div className="rounded-lg border border-neutral-800 p-3 text-[10px] text-neutral-400">
                    <div className="font-semibold text-neutral-300 mb-1">Preuves profil</div>
                    <ul className="space-y-1">
                      {profileContext.evidence_spans.map((span, idx) => (
                        <li key={`prof-span-${idx}`}>
                          <span className="text-neutral-500">{span.field}:</span> {span.span}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </DebugSection>
            )}
          </div>
        )}
      </div>
    </div>

    {/* CV Preview Modal — rendered on top of offer modal (z-[60]) */}
    {cvPreview && (
      <CvPreviewModal
        offerTitle={offer.title}
        offerCompany={offer.company}
        preview={cvPreview}
        onClose={() => setCvPreview(null)}
      />
    )}
    {cvHtmlPreview && (
      <CvHtmlPreviewModal
        offerTitle={offer.title}
        offerCompany={offer.company}
        preview={cvHtmlPreview}
        onClose={() => setCvHtmlPreview(null)}
      />
    )}
    {letterPreview && (
      <LetterPreviewModal
        offerTitle={offer.title}
        offerCompany={offer.company}
        preview={letterPreview}
        onClose={() => setLetterPreview(null)}
      />
    )}
    </>
  );
}
