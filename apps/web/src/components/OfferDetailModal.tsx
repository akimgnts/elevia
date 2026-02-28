import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Loader2, X } from "lucide-react";
import type { ContextFit, ExplainBlock, ForOfferResponse, InboxContextPayload, OfferContext, ProfileContext } from "../lib/api";
import { generateCvForOffer } from "../lib/api";
import { CvPreviewModal } from "./CvPreviewModal";
import { cleanOfferTitle } from "../lib/titleUtils";
import { formatRelativeDate } from "../lib/dateUtils";

export type StrategySummary = {
  mission_summary?: string;
  distance?: string;
  action_guidance?: string;
};

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
  strategy_summary?: StrategySummary | null;
  semantic_score?: number | null;
  semantic_model_version?: string | null;
  relevant_passages?: string[];
  ai_available?: boolean;
  ai_error?: string | null;
  explain?: ExplainBlock | null;
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

function distanceBadgeClass(distance?: string) {
  const value = (distance || "").toLowerCase();
  if (value.includes("faible")) return "bg-emerald-500/20 text-emerald-300";
  if (value.includes("inter")) return "bg-amber-500/20 text-amber-300";
  if (value.includes("élev") || value.includes("ele")) return "bg-rose-500/20 text-rose-300";
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

function mapRoleTypeToCluster(role?: OfferContext["role_type"] | OfferContext["primary_role_type"]) {
  if (!role) return null;
  switch (role) {
    case "BI_REPORTING":
    case "DATA_ANALYSIS":
    case "DATA_ENGINEERING":
    case "PRODUCT_ANALYTICS":
    case "OPS_ANALYTICS":
    case "MIXED":
      return "DATA_IT";
    default:
      return null;
  }
}

function getVerdict(score?: number | null): "BON" | "MOYEN" | "STRETCH" {
  if (score === null || score === undefined) return "STRETCH";
  if (score >= 75) return "BON";
  if (score >= 60) return "MOYEN";
  return "STRETCH";
}

function verdictBadgeClass(verdict: "BON" | "MOYEN" | "STRETCH") {
  switch (verdict) {
    case "BON":
      return "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
    case "MOYEN":
      return "bg-amber-500/20 text-amber-300 border border-amber-500/30";
    default:
      return "bg-rose-500/20 text-rose-300 border border-rose-500/30";
  }
}

function derivePositionElevia({
  score,
  matchedCore,
  missingCore,
  clusterMismatch,
  isRecent,
}: {
  score?: number | null;
  matchedCore: number;
  missingCore: number;
  clusterMismatch: boolean;
  isRecent: boolean;
}) {
  const scoreDefined = score !== null && score !== undefined;
  const verdict = getVerdict(score);
  let signal = "Signal à confirmer";
  if (matchedCore >= 1) {
    signal = "Compétences cœur présentes";
  } else if (isRecent) {
    signal = "Opportunité récente dans ton périmètre";
  }

  let risk = "Risque modéré";
  if (missingCore >= 3) {
    risk = "Manque compétences clés";
  } else if (clusterMismatch) {
    risk = "Domaine différent";
  }

  let action = "À faire : clarifier les attentes avant d'avancer";
  if (isRecent && (verdict === "BON" || verdict === "MOYEN")) {
    action = "À faire : postuler maintenant";
  } else if (verdict === "STRETCH" && scoreDefined) {
    action = "À faire : postuler seulement si tu acceptes un pivot";
  }

  return { verdict, signal, risk, action };
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

  // CV generation state
  const [cvLoading, setCvLoading] = useState(false);
  const [cvPreview, setCvPreview] = useState<ForOfferResponse | null>(null);
  const [cvError, setCvError] = useState<string | null>(null);

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

  useEffect(() => {
    setVisible(true);
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = original; };
  }, []);

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
  const summary = offer.strategy_summary || undefined;
  const titleInfo = useMemo(() => cleanOfferTitle(offer.title), [offer.title]);
  const profileDominantCluster =
    profileContext && typeof (profileContext as { dominant_cluster?: string }).dominant_cluster === "string"
      ? (profileContext as { dominant_cluster?: string }).dominant_cluster
      : null;
  const offerCluster = mapRoleTypeToCluster(offerContext?.primary_role_type);
  const roleClusterMismatch = Boolean(profileDominantCluster && offerCluster && profileDominantCluster !== offerCluster);
  const matchedCoreCount = explain?.matched_full?.filter((item) => item.weighted).length ?? 0;
  const missingCoreCount = explain?.missing_full?.filter((item) => item.weighted).length ?? 0;
  const relativeDate = offer.publication_date
    ? formatRelativeDate(offer.publication_date)
    : null;
  const isRecent = relativeDate?.freshness === "new";
  const clusterLabel = formatClusterLabel(offer.offer_cluster);
  const signalLabel =
    typeof offer.signal_score === "number" ? `Signal ${offer.signal_score.toFixed(1)}` : null;
  const isSuspicious = offer.coherence === "suspicious";
  const positionElevia = derivePositionElevia({
    score: offer.score ?? undefined,
    matchedCore: matchedCoreCount,
    missingCore: missingCoreCount,
    clusterMismatch: roleClusterMismatch,
    isRecent,
  });

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
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreBadgeClass(offer.score)}`}>
                Score {offer.score ?? "—"}
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
              onClick={onClose}
              className="rounded-lg border border-neutral-700 p-2 text-neutral-300 hover:text-white hover:border-neutral-500"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* CV error notice */}
        {cvError && (
          <div className="mt-3 rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-2 text-xs text-rose-300">
            Génération échouée : {cvError}
          </div>
        )}

        {/* Position Elevia */}
        <section className="mt-6">
          <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-4 text-xs text-neutral-300 space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-100">Position Elevia</h3>
              <span className={`rounded-full px-3 py-1 text-[10px] font-semibold ${verdictBadgeClass(positionElevia.verdict)}`}>
                {positionElevia.verdict}
              </span>
            </div>
            <p className="text-[11px] text-neutral-300">
              Signal fort : {positionElevia.signal} · Risque : {positionElevia.risk}
            </p>
            <p className="text-[11px] text-neutral-400">{positionElevia.action}</p>
          </div>
        </section>

        {/* Description — always visible */}
        <section className="mt-6">
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
        </section>

        {/* ── ALIGNEMENT — always visible, trimmed in user mode ────────────────── */}
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
              {/* fit_summary — always shown */}
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

              {/* USER: 1 why + 1 friction + 1 question. DEV: all. */}
              {contextFit.why_it_fits.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Pourquoi ça colle</div>
                  <ul className="mt-1 list-disc list-inside space-y-1">
                    {(showDebug ? contextFit.why_it_fits : contextFit.why_it_fits.slice(0, 1)).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {contextFit.likely_frictions.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Points de friction</div>
                  <ul className="mt-1 list-disc list-inside space-y-1">
                    {(showDebug ? contextFit.likely_frictions : contextFit.likely_frictions.slice(0, 1)).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {contextFit.clarifying_questions.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Questions de clarification</div>
                  <ul className="mt-1 list-disc list-inside space-y-1">
                    {(showDebug ? contextFit.clarifying_questions : contextFit.clarifying_questions.slice(0, 1)).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* recommended_angle + evidence_spans: DEV only */}
              {showDebug && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                </>
              )}
            </div>
          )}
          {contextError && (
            <div className="text-xs text-rose-300">Erreur contexte: {contextError}</div>
          )}
        </section>

        {/* ── SCORE ESCO — always visible ───────────────────────────────────────── */}
        <section className="mt-6">
          <h3 className="text-sm font-semibold text-neutral-200">Score ESCO</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-neutral-300">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${scoreBadgeClass(offer.score)}`}>
              Score {offer.score ?? "—"}
            </span>
            <span className="text-xs text-neutral-500">
              Score déterministe basé sur les compétences ESCO et critères langue/formation/pays.
            </span>
          </div>
        </section>

        {/* ── COMPÉTENCES — always visible ─────────────────────────────────────── */}
        <section className="mt-6 space-y-5">
          <h3 className="text-sm font-semibold text-neutral-200">Compétences demandées</h3>
          {typeof offer.intersection_count === "number" && typeof offer.offer_uri_count === "number" && (
            <div className="text-xs text-neutral-500">
              {offer.intersection_count} compétences reconnues sur {offer.offer_uri_count}
            </div>
          )}
          <SkillGroup label="Compétences alignées" skills={matched} className="bg-green-600/20 text-green-400" />
          <SkillGroup label="Compétences manquantes" skills={missing} className="bg-red-600/20 text-red-400" />
          {showDebug && (
            <SkillGroup label="Non mappées ESCO (debug)" skills={unmapped} className="bg-neutral-700 text-neutral-300" />
          )}
          {matched.length === 0 && missing.length === 0 && unmapped.length === 0 && (
            <p className="text-sm text-neutral-500">Aucune compétence fournie.</p>
          )}
        </section>

        {/* ── DÉTAIL DU SCORE — always visible ─────────────────────────────────── */}
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

            {/* DEV: Strategic summary */}
            {summary && (
              <DebugSection title="Synthèse stratégique">
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Mission principale</div>
                  <div className="mt-1">{summary.mission_summary || "—"}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Distance</div>
                  <span className={`mt-1 inline-flex rounded-full px-3 py-1 text-[10px] ${distanceBadgeClass(summary.distance)}`}>
                    {summary.distance || "—"}
                  </span>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">Action recommandée</div>
                  <div className="mt-1">{summary.action_guidance || "—"}</div>
                </div>
              </DebugSection>
            )}

            {/* Actions placeholder */}
            <section className="mt-4 flex flex-wrap items-center gap-3">
              <button disabled className="rounded-xl bg-neutral-800 px-4 py-2 text-sm font-semibold text-neutral-500">
                Action principale (bientôt)
              </button>
              <button disabled className="rounded-xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-500">
                Action secondaire (bientôt)
              </button>
            </section>
          </div>
        )}

        {/* Actions placeholder (user mode) */}
        {!showDebug && (
          <section className="mt-8 flex flex-wrap items-center gap-3">
            <button disabled className="rounded-xl bg-neutral-800 px-4 py-2 text-sm font-semibold text-neutral-500">
              Action principale (bientôt)
            </button>
            <button disabled className="rounded-xl border border-neutral-700 px-4 py-2 text-sm font-semibold text-neutral-500">
              Action secondaire (bientôt)
            </button>
          </section>
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
    </>
  );
}
