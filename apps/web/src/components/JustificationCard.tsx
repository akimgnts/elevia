/**
 * JustificationCard — Diagnostic de candidature.
 *
 * Hiérarchie lisible en 5 secondes :
 *   1. Verdict (décision tranchée + score + effort)
 *   2. Plan CV (ce que tu dois mettre en avant)
 *   3. Forces transférables
 *   4. Gaps avec actions
 *   5. Pseudo-exigences (ce qui n'est pas un vrai gap)
 *   6. Analyse textuelle (contexte)
 *
 * - Auto-charge au montage
 * - Cache module-level (même combo offre×profil → zéro re-fetch)
 * - Fallback silencieux sur erreur
 */
import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  Sparkles,
  XCircle,
} from "lucide-react";
import {
  justifyOffer,
  type JustificationPayload,
  type JustifyFitRequest,
  type TrueGap,
} from "../lib/api";

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------
const _cache = new Map<string, JustificationPayload>();

function _cacheKey(offerId: string, profileId: string | undefined, matchedSkills: string[]): string {
  return `${offerId}::${profileId ?? "anon"}::${matchedSkills.slice(0, 6).sort().join("+")}`;
}

// ---------------------------------------------------------------------------
// Verdict labels — specific, not generic
// ---------------------------------------------------------------------------
function verdictLabel(
  decision: "GO" | "MAYBE" | "NO_GO",
  blockingCount: number,
): string {
  if (decision === "GO") {
    return blockingCount > 0 ? "Bon fit avec un point à compenser" : "Candidature recommandée — postulez";
  }
  if (decision === "MAYBE") {
    return blockingCount > 0 ? "Fit moyen — gap critique à adresser" : "Fit moyen, rattrapable";
  }
  return "Hors cible principale pour ce poste";
}

function verdictCls(decision: "GO" | "MAYBE" | "NO_GO") {
  if (decision === "GO") return "bg-emerald-50 border-emerald-200 text-emerald-900";
  if (decision === "MAYBE") return "bg-amber-50 border-amber-200 text-amber-900";
  return "bg-rose-50 border-rose-200 text-rose-900";
}

function effortLabel(e: "LOW" | "MEDIUM" | "HIGH") {
  if (e === "LOW") return { text: "Effort faible", cls: "text-emerald-700" };
  if (e === "MEDIUM") return { text: "Effort moyen", cls: "text-amber-700" };
  return { text: "Effort élevé", cls: "text-rose-700" };
}

// ---------------------------------------------------------------------------
// Severity badges
// ---------------------------------------------------------------------------
function SeverityBadge({ sev }: { sev: TrueGap["severity"] }) {
  if (sev === "blocking") {
    return (
      <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-rose-100 text-rose-700">
        Bloquant
      </span>
    );
  }
  if (sev === "semi_blocking") {
    return (
      <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-amber-100 text-amber-700">
        Compensable
      </span>
    );
  }
  return (
    <span className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide bg-slate-100 text-slate-500">
      Mineur
    </span>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function Skeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-16 rounded-2xl bg-slate-100" />
      <div className="h-28 rounded-2xl bg-slate-100" />
      <div className="h-24 rounded-2xl bg-slate-100" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fallback (API fail)
// ---------------------------------------------------------------------------
function FallbackDiagnostic({
  matchedSkills,
  missingSkills,
  score,
}: {
  matchedSkills: string[];
  missingSkills: string[];
  score?: number | null;
}) {
  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-slate-100 bg-white/80 px-5 py-3">
        <p className="text-xs italic text-slate-400">
          Analyse avancée indisponible
          {score != null ? ` — score inbox : ${score}` : ""}
        </p>
      </div>
      {matchedSkills.length > 0 && (
        <div className="rounded-2xl border border-white/80 bg-white/85 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700 mb-2">
            Compétences matchées
          </div>
          <div className="flex flex-wrap gap-1.5">
            {matchedSkills.slice(0, 8).map((s) => (
              <span key={s} className="rounded-full border border-emerald-100 bg-emerald-50 px-3 py-0.5 text-xs text-emerald-800">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
      {missingSkills.length > 0 && (
        <div className="rounded-2xl border border-white/80 bg-white/85 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700 mb-2">
            Écarts détectés
          </div>
          <div className="flex flex-wrap gap-1.5">
            {missingSkills.slice(0, 6).map((s) => (
              <span key={s} className="rounded-full border border-amber-100 bg-amber-50 px-3 py-0.5 text-xs text-amber-800">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main diagnostic display
// ---------------------------------------------------------------------------
function DiagnosticResult({ result }: { result: JustificationPayload }) {
  const blocking = result.true_gaps.filter((g) => g.severity === "blocking");
  const semi = result.true_gaps.filter((g) => g.severity === "semi_blocking");
  const minor = result.true_gaps.filter((g) => g.severity === "minor");
  const orderedGaps = [...blocking, ...semi, ...minor];
  const effort = effortLabel(result.application_effort);

  return (
    <div className="space-y-3">

      {/* ── 1. Verdict ────────────────────────────────────────────────── */}
      <div className={`flex items-center justify-between rounded-2xl border px-5 py-4 ${verdictCls(result.decision)}`}>
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-50 mb-0.5">
            Verdict
          </div>
          <div className="text-sm font-bold leading-tight">
            {verdictLabel(result.decision, blocking.length)}
          </div>
        </div>
        <div className="text-right shrink-0 ml-4">
          <div className={`text-xs font-semibold ${effort.cls}`}>{effort.text}</div>
        </div>
      </div>

      {/* ── 2. Plan CV — ce que tu dois mettre en avant ───────────────── */}
      <div className="rounded-2xl border border-violet-100 bg-violet-50/50 p-4">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-700 mb-3">
          <FileText className="h-3.5 w-3.5" />
          Ce que tu dois mettre en avant dans ton CV
        </div>

        {/* Angle */}
        <p className="text-sm font-semibold text-slate-900">{result.cv_strategy.angle}</p>

        {/* Focus items */}
        {result.cv_strategy.focus && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {result.cv_strategy.focus.split(/[,;]/).map((f, i) => {
              const label = f.trim();
              return label ? (
                <span key={i} className="rounded-full border border-violet-200 bg-white px-3 py-0.5 text-xs font-medium text-violet-800">
                  {label}
                </span>
              ) : null;
            })}
          </div>
        )}

        {/* Phrase d'accroche */}
        {result.cv_strategy.positioning_phrase && (
          <blockquote className="mt-3 border-l-2 border-violet-400 pl-3 text-sm italic text-slate-700 leading-6">
            "{result.cv_strategy.positioning_phrase}"
          </blockquote>
        )}

        {/* Strengths — linked to CV plan */}
        {result.transferable_strengths.length > 0 && (
          <ul className="mt-3 space-y-1.5 border-t border-violet-100 pt-3">
            {result.transferable_strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                <span>
                  <span className="font-medium text-slate-800">{s.strength}</span>
                  {s.relevance && (
                    <span className="ml-1.5 text-slate-500 text-xs">— {s.relevance}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── 3. Gaps avec actions ──────────────────────────────────────── */}
      {orderedGaps.length > 0 && (
        <div className="rounded-2xl border border-white/80 bg-white/90 p-4 shadow-[0_4px_16px_rgba(15,23,42,0.04)]">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700 mb-3">
            <AlertTriangle className="h-3.5 w-3.5" />
            Points à adresser
          </div>
          <ul className="space-y-3">
            {orderedGaps.map((g, i) => (
              <li key={i} className="space-y-1">
                <div className="flex items-center gap-2">
                  {g.severity === "blocking" ? (
                    <XCircle className="h-4 w-4 shrink-0 text-rose-500" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                  )}
                  <span className="text-sm font-semibold text-slate-800">{g.skill}</span>
                  <SeverityBadge sev={g.severity} />
                </div>
                {g.why && (
                  <p className="ml-6 text-xs text-slate-500 leading-5">{g.why}</p>
                )}
                {g.mitigation && (
                  <div className="ml-6 flex items-start gap-1.5 text-xs text-violet-700">
                    <ArrowRight className="mt-0.5 h-3 w-3 shrink-0" />
                    <span className="font-medium">{g.mitigation}</span>
                  </div>
                )}
              </li>
            ))}
          </ul>

          {/* Pseudo-gaps */}
          {result.non_skill_requirements.length > 0 && (
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400 mb-2">
                Pas de vrais gaps — ne t'inquiète pas pour ça
              </div>
              <div className="flex flex-wrap gap-1.5">
                {result.non_skill_requirements.map((r, i) => (
                  <span
                    key={i}
                    title={r.why_not_gap}
                    className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-500 cursor-help"
                  >
                    {r.text}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── 4. Analyse ────────────────────────────────────────────────── */}
      {result.fit_summary && (
        <div className="rounded-2xl border border-white/80 bg-white/90 p-4">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 mb-2">
            <Sparkles className="h-3.5 w-3.5" />
            Contexte
          </div>
          <p className="text-sm leading-7 text-slate-600">{result.fit_summary}</p>
          {result.archetype && !result.meta.fallback_used && (
            <p className="mt-1 text-xs italic text-slate-400">{result.archetype}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported component
// ---------------------------------------------------------------------------
export interface JustificationCardProps {
  offerId: string;
  profile: Record<string, unknown> | null | undefined;
  profileId?: string;
  score?: number | null;
  matchedSkills?: string[];
  missingSkills?: string[];
  canonicalSkills?: string[];
  enrichedSignals?: string[];
  profileIntelligence?: Record<string, unknown> | null;
  offerIntelligence?: Record<string, unknown> | null;
}

export function JustificationCard({
  offerId,
  profile,
  profileId,
  score,
  matchedSkills = [],
  missingSkills = [],
  canonicalSkills = [],
  enrichedSignals = [],
  profileIntelligence,
  offerIntelligence,
}: JustificationCardProps) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<JustificationPayload | null>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!offerId || !profile || fetchedRef.current) return;

    const key = _cacheKey(offerId, profileId, matchedSkills);
    const cached = _cache.get(key);
    if (cached) {
      setResult(cached);
      setState("done");
      return;
    }

    fetchedRef.current = true;
    setState("loading");

    const req: JustifyFitRequest = {
      offer_id: offerId,
      profile,
      profile_id: profileId,
      score: score ?? undefined,
      matched_skills: matchedSkills,
      missing_skills: missingSkills,
      canonical_skills: canonicalSkills,
      enriched_signals: enrichedSignals,
      profile_intelligence: profileIntelligence ?? undefined,
      offer_intelligence: offerIntelligence ?? undefined,
    };

    justifyOffer(req)
      .then((resp) => {
        _cache.set(key, resp.justification);
        setResult(resp.justification);
        setState("done");
      })
      .catch(() => setState("error"));
  }, [offerId, profile, profileId, score, matchedSkills, missingSkills, canonicalSkills, enrichedSignals, profileIntelligence, offerIntelligence]);

  if (!profile) return null;

  if (state === "idle" || state === "loading") return <Skeleton />;

  if (state === "error" || !result) {
    return (
      <FallbackDiagnostic
        matchedSkills={matchedSkills}
        missingSkills={missingSkills}
        score={score}
      />
    );
  }

  return <DiagnosticResult result={result} />;
}
