import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, Building2, ChevronDown, FileText, Loader2, MapPin, Sparkles, X } from "lucide-react";
import { prepareApplication, upsertApplication } from "../api/applications";
import { JustificationCard } from "./JustificationCard";
import { StructuredOfferSummaryCard } from "./StructuredOfferSummaryCard";
import type {
  ContextFit,
  CvHtmlResponse,
  DescriptionStructuredV1,
  ExplainBlock,
  ExplainPayloadV1Full,
  ForOfferLetterResponse,
  ForOfferResponse,
  InboxContextPayload,
  OfferContext,
  OfferExplanation,
  OfferIntelligence,
  ProfileContext,
  ProfileSemanticContext,
  ScoringV2,
  ScoringV3,
  SemanticExplainability,
} from "../lib/api";
import { fetchOfferDetail, generateCvForOffer, generateCvHtmlForOffer, generateCvV2ForOffer, generateLetterForOffer } from "../lib/api";
import { CvHtmlPreviewModal } from "./CvHtmlPreviewModal";
import { CvPreviewModal } from "./CvPreviewModal";
import { LetterPreviewModal } from "./LetterPreviewModal";
import { formatRelativeDate } from "../lib/dateUtils";
import { cleanOfferTitle } from "../lib/titleUtils";

export type OfferDetail = {
  offer_id?: string;
  id?: string;
  title: string;
  publication_date?: string | null;
  company?: string | null;
  country?: string | null;
  city?: string | null;
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
  scoring_v3?: ScoringV3 | null;
  description_structured_v1?: DescriptionStructuredV1 | null;
  explain_v1_full?: ExplainPayloadV1Full | null;
};

function scoreTone(score?: number | null): string {
  if ((score ?? 0) >= 75) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if ((score ?? 0) >= 55) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function uniqueValues(values: string[], limit: number): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const cleaned = value.trim();
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(cleaned);
    if (result.length >= limit) break;
  }
  return result;
}


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
  void offerContext;
  void profileContext;
  void contextFit;
  void contextLoading;
  void contextError;
  const [visible, setVisible] = useState(false);
  const [structuredV1, setStructuredV1] = useState<DescriptionStructuredV1 | null>(offer.description_structured_v1 ?? null);
  const [explainV1Full, setExplainV1Full] = useState<ExplainPayloadV1Full | null>(offer.explain_v1_full ?? null);
  const [offerIntelligence, setOfferIntelligence] = useState<OfferIntelligence | null>(offer.offer_intelligence ?? null);
  const [semanticExplainability, setSemanticExplainability] = useState<SemanticExplainability | null>(offer.semantic_explainability ?? null);
  const [scoringV2, setScoringV2] = useState<ScoringV2 | null>(offer.scoring_v2 ?? null);
  const [scoringV3, setScoringV3] = useState<ScoringV3 | null>(offer.scoring_v3 ?? null);
  const [structuredLoading, setStructuredLoading] = useState(false);
  const [cvLoading, setCvLoading] = useState(false);
  const [cvPreview, setCvPreview] = useState<ForOfferResponse | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);
  const [cvHtmlLoading, setCvHtmlLoading] = useState(false);
  const [cvHtmlPreview, setCvHtmlPreview] = useState<CvHtmlResponse | null>(null);
  const [cvHtmlError, setCvHtmlError] = useState<string | null>(null);
  const [cvV2Loading, setCvV2Loading] = useState(false);
  const [cvV2Preview, setCvV2Preview] = useState<CvHtmlResponse | null>(null);
  const [cvV2Error, setCvV2Error] = useState<string | null>(null);
  const [letterLoading, setLetterLoading] = useState(false);
  const [letterPreview, setLetterPreview] = useState<ForOfferLetterResponse | null>(null);
  const [letterError, setLetterError] = useState<string | null>(null);
  const [trackerLoading, setTrackerLoading] = useState(false);
  const [trackerError, setTrackerError] = useState<string | null>(null);
  const [trackerSaved, setTrackerSaved] = useState(false);
  const [prepareFlowLoading, setPrepareFlowLoading] = useState(false);
  const [prepareFlowError, setPrepareFlowError] = useState<string | null>(null);
  const [prepareFlowStatus, setPrepareFlowStatus] = useState<string | null>(null);
  const detailFetchKeyRef = useRef<string | null>(null);

  useEffect(() => {
    setVisible(true);
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = original;
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const profileIntelligence = useMemo(
    () =>
      profile && typeof profile === "object"
        ? ((profile as { profile_intelligence?: ProfileSemanticContext }).profile_intelligence ?? null)
        : null,
    [profile],
  );

  useEffect(() => {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    const requestKey = JSON.stringify({
      offerId,
      score: offer.score ?? offer.explanation.score ?? null,
      profileRole: profileIntelligence?.dominant_role_block ?? null,
    });
    if (detailFetchKeyRef.current === requestKey) return;
    detailFetchKeyRef.current = requestKey;
    setStructuredLoading(true);
    fetchOfferDetail(offerId, profileIntelligence, offer.score ?? null)
      .then((detail) => {
        if (detail.description_structured_v1) setStructuredV1(detail.description_structured_v1);
        if (detail.explain_v1_full) setExplainV1Full(detail.explain_v1_full);
        if (detail.offer_intelligence) setOfferIntelligence(detail.offer_intelligence);
        if (detail.semantic_explainability) setSemanticExplainability(detail.semantic_explainability);
        if (detail.scoring_v2) setScoringV2(detail.scoring_v2);
        if (detail.scoring_v3) setScoringV3(detail.scoring_v3);
      })
      .catch((error: unknown) => {
        console.error("[offer-detail] enrichment fetch failed:", error);
      })
      .finally(() => {
        detailFetchKeyRef.current = null;
        setStructuredLoading(false);
      });
  }, [offer.explanation.score, offer.id, offer.offer_id, offer.score, profileIntelligence]);

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
      setCvPreview(await generateCvForOffer(offerId, profile ?? {}, ctx));
    } catch (error) {
      setCvError(error instanceof Error ? error.message : "Erreur inconnue");
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
      setCvHtmlPreview(await generateCvHtmlForOffer(offerId, profile ?? {}, ctx));
    } catch (error) {
      setCvHtmlError(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setCvHtmlLoading(false);
    }
  }

  const hasCareerProfile = Boolean((profile as Record<string, unknown> | null | undefined)?.career_profile);

  async function handleGenerateCvV2() {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    setCvV2Loading(true);
    setCvV2Error(null);
    try {
      const ctx: InboxContextPayload | undefined =
        offer.matched_skills_display?.length || offer.matched_skills?.length
          ? {
              matched_skills: offer.matched_skills_display ?? offer.matched_skills ?? [],
              missing_skills: offer.missing_skills_display ?? offer.missing_skills ?? [],
            }
          : undefined;
      setCvV2Preview(await generateCvV2ForOffer(offerId, profile ?? {}, ctx));
    } catch (error) {
      setCvV2Error(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setCvV2Loading(false);
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
      setLetterPreview(await generateLetterForOffer(offerId, profile ?? {}, ctx));
    } catch (error) {
      setLetterError(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setLetterLoading(false);
    }
  }

  async function handleSendToTracker() {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    setTrackerLoading(true);
    setTrackerError(null);
    try {
      await upsertApplication({
        offer_id: offerId,
        status: "saved",
        source: "assisted",
      });
      setTrackerSaved(true);
    } catch (error) {
      setTrackerError(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setTrackerLoading(false);
    }
  }

  async function handlePrepareInTracker() {
    const offerId = offer.offer_id || offer.id;
    if (!offerId) return;
    setPrepareFlowLoading(true);
    setPrepareFlowError(null);
    try {
      await upsertApplication({
        offer_id: offerId,
        status: "saved",
        source: "assisted",
      });
      const result = await prepareApplication(
        offerId,
        profile && typeof profile === "object"
          ? { profile: profile as Record<string, unknown> }
          : {},
      );
      setTrackerSaved(true);
      setPrepareFlowStatus(result.status);
    } catch (error) {
      setPrepareFlowError(error instanceof Error ? error.message : "Erreur inconnue");
    } finally {
      setPrepareFlowLoading(false);
    }
  }

  const intelligence = offerIntelligence ?? offer.offer_intelligence ?? null;
  const semantic = semanticExplainability ?? offer.semantic_explainability ?? null;
  const scoreV2 = scoringV2 ?? offer.scoring_v2 ?? null;
  const scoreV3 = scoringV3 ?? offer.scoring_v3 ?? null;

  // SINGLE SOURCE OF TRUTH: inbox score only.
  // scoring_v3.score_pct is a composite overlay (role/domain modifiers applied to matching_score)
  // and MUST NOT replace the authoritative inbox score.
  const primaryScore: number | null = offer.score ?? offer.explanation.score ?? null;

  if (import.meta.env.DEV && typeof scoreV3?.score_pct === "number" && primaryScore !== null) {
    const delta = Math.abs(scoreV3.score_pct - primaryScore);
    if (delta > 1) {
      console.warn(
        `[score-ssot] inbox=${primaryScore} scoring_v3=${scoreV3.score_pct} delta=${delta} offer=${offer.offer_id ?? offer.id}`,
      );
    }
  }
  const titleInfo = useMemo(() => cleanOfferTitle(offer.title), [offer.title]);
  const location = [offer.company ? null : null, offer.city, offer.country].filter(Boolean).join(", ");
  const relativeDate = offer.publication_date ? formatRelativeDate(offer.publication_date) : null;
  const detailSignals = uniqueValues(
    [
      ...(intelligence?.top_offer_signals ?? []),
      ...(intelligence?.required_skills ?? []),
      ...(semantic?.signal_alignment?.matched_signals ?? []),
    ],
    6,
  );

  return (
    <>
      <div
        className={`fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm transition-opacity duration-200 ${
          visible ? "opacity-100" : "opacity-0"
        }`}
        onClick={onClose}
        role="dialog"
        aria-modal="true"
      >
        <div
          className={`relative w-full max-w-4xl overflow-y-auto rounded-[2rem] border border-white/80 bg-[#f8fafc] p-6 text-slate-900 shadow-[0_32px_90px_rgba(15,23,42,0.18)] transition-transform duration-200 sm:p-8 ${
            visible ? "scale-100" : "scale-95"
          } max-h-[90vh]`}
          onClick={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            onClick={onClose}
            className="absolute right-4 top-4 rounded-full border border-slate-200 bg-white p-2 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
            aria-label="Fermer"
          >
            <X className="h-4 w-4" />
          </button>

          <section className="rounded-[1.75rem] border border-white/80 bg-white/85 p-6 shadow-[0_18px_55px_rgba(15,23,42,0.08)]">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">{titleInfo.display}</h2>
                <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-600">
                  <span className="inline-flex items-center gap-2"><Building2 className="h-4 w-4 text-slate-400" />{offer.company || "Entreprise"}</span>
                  <span className="inline-flex items-center gap-2"><MapPin className="h-4 w-4 text-slate-400" />{location || offer.country || "Localisation à préciser"}</span>
                  {relativeDate && <span className="text-slate-500">{relativeDate.label}</span>}
                </div>
              </div>
              <div className={`shrink-0 rounded-[1.5rem] border px-5 py-4 text-center ${scoreTone(primaryScore)}`}>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em]">Score</div>
                <div className="mt-2 text-4xl font-semibold leading-none">{primaryScore ?? "—"}</div>
              </div>
            </div>
          </section>

          {/* ── Fiche structurée : comprendre le poste ──────────────────── */}
          <section className="mt-6">
            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Fiche de poste structurée
            </div>
            <StructuredOfferSummaryCard
              offerId={offer.offer_id || offer.id || ""}
              structuredV1={structuredV1}
            />
          </section>

          {/* ── Diagnostic IA : suis-je compatible ? ────────────────────── */}
          <section className="mt-6">
            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Diagnostic de candidature
            </div>
            <JustificationCard
              offerId={offer.offer_id || offer.id || ""}
              profile={profile ?? null}
              profileId={typeof profile?.id === "string" ? profile.id : undefined}
              score={offer.score ?? offer.explanation?.score ?? undefined}
              matchedSkills={offer.matched_skills ?? []}
              missingSkills={offer.missing_skills ?? []}
              profileIntelligence={
                profile
                  ? ((profile as Record<string, unknown>).profile_intelligence as Record<string, unknown> | undefined)
                  : undefined
              }
              offerIntelligence={(offerIntelligence as Record<string, unknown> | null | undefined) ?? undefined}
            />
          </section>

          {(cvError || cvHtmlError || cvV2Error || letterError || trackerError || prepareFlowError) && (
            <div className="mt-6 space-y-2 text-sm text-rose-700">
              {cvError && <div>{cvError}</div>}
              {cvHtmlError && <div>{cvHtmlError}</div>}
              {cvV2Error && <div>{cvV2Error}</div>}
              {letterError && <div>{letterError}</div>}
              {trackerError && <div>{trackerError}</div>}
              {prepareFlowError && <div>{prepareFlowError}</div>}
            </div>
          )}

          {(trackerSaved || prepareFlowStatus) && (
            <div className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              <div className="font-semibold text-emerald-900">Offre envoyée dans Candidatures.</div>
              <div className="mt-1">
                {prepareFlowStatus
                  ? `Statut actuel : ${prepareFlowStatus}. Vous pouvez maintenant suivre la candidature et ouvrir les documents préparés.`
                  : "Le suivi est prêt. Vous pouvez maintenant préparer le CV et la lettre depuis la page Candidatures."}
              </div>
            </div>
          )}

          {!hasCareerProfile && (
            <div className="mt-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
              <span>Complétez votre profil CareerProfile pour générer un CV adapté à cette offre.</span>
            </div>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleSendToTracker}
              disabled={trackerLoading}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {trackerLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {trackerLoading ? "Ajout…" : trackerSaved ? "Déjà dans le suivi" : "Envoyer vers Candidatures"}
            </button>
            <button
              type="button"
              onClick={handlePrepareInTracker}
              disabled={prepareFlowLoading}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {prepareFlowLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {prepareFlowLoading ? "Préparation…" : "Préparer dans Candidatures"}
            </button>
            <Link
              to="/applications"
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Ouvrir le suivi
            </Link>
            <button
              type="button"
              onClick={handleGenerateCvV2}
              disabled={cvV2Loading || !hasCareerProfile}
              className="inline-flex items-center gap-2 rounded-full bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {cvV2Loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {cvV2Loading ? "Adaptation en cours…" : "Préparer mon CV pour cette offre"}
            </button>
            <button
              type="button"
              onClick={handleGenerateCv}
              disabled={cvLoading}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {cvLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {cvLoading ? "Génération…" : "Générer CV"}
            </button>
            <button
              type="button"
              onClick={handleGenerateCvHtml}
              disabled={cvHtmlLoading}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {cvHtmlLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {cvHtmlLoading ? "Génération…" : "Voir CV (HTML)"}
            </button>
            <button
              type="button"
              onClick={handleGenerateLetter}
              disabled={letterLoading}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {letterLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {letterLoading ? "Génération…" : "Générer lettre"}
            </button>
          </div>

          <details className="mt-6 rounded-[1.5rem] border border-slate-200 bg-white/85 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.06)]">
            <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-slate-900">
              <span>Détail du diagnostic</span>
              <ChevronDown className="h-4 w-4 text-slate-400" />
            </summary>
            <div className="mt-4 grid gap-5 lg:grid-cols-2">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Score (source : inbox)</div>
                <div className="mt-2 text-sm text-slate-700">{primaryScore ?? "—"}%</div>
                {scoreV3?.summary && <p className="mt-2 text-sm leading-6 text-slate-600">{scoreV3.summary}</p>}
                {scoreV3 && typeof scoreV3.score_pct === "number" && (
                  <div className="mt-2 text-xs text-slate-400">Overlay analytique v3 : {scoreV3.score_pct}%</div>
                )}
                {scoreV2 && typeof scoreV2.score_pct === "number" && (
                  <div className="mt-1 text-xs text-slate-400">Overlay analytique v2 : {scoreV2.score_pct}%</div>
                )}
              </div>
              {detailSignals.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Signaux visibles</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {detailSignals.map((item) => (
                      <span key={item} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {showDebug && explainV1Full && (
                <div className="lg:col-span-2 rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-xs text-slate-700">
                  <div className="font-semibold text-amber-900">Mode debug</div>
                  <div className="mt-2">Confiance : {explainV1Full.confidence}</div>
                  <div>Signal rare : {explainV1Full.rare_signal_level}</div>
                </div>
              )}
              {structuredLoading && <div className="text-sm text-slate-500">Chargement du détail…</div>}
            </div>
          </details>
        </div>
      </div>

      {cvPreview && (
        <CvPreviewModal
          offerTitle={titleInfo.display}
          offerCompany={offer.company}
          preview={cvPreview}
          onClose={() => setCvPreview(null)}
        />
      )}
      {cvHtmlPreview && (
        <CvHtmlPreviewModal
          offerTitle={titleInfo.display}
          offerCompany={offer.company}
          preview={cvHtmlPreview}
          onClose={() => setCvHtmlPreview(null)}
        />
      )}
      {cvV2Preview && (
        <CvHtmlPreviewModal
          offerTitle={titleInfo.display}
          offerCompany={offer.company}
          preview={cvV2Preview}
          onClose={() => setCvV2Preview(null)}
        />
      )}
      {letterPreview && (
        <LetterPreviewModal
          offerTitle={titleInfo.display}
          offerCompany={offer.company}
          preview={letterPreview}
          onClose={() => setLetterPreview(null)}
        />
      )}
    </>
  );
}
