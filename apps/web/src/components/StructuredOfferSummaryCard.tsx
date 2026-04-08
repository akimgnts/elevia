/**
 * StructuredOfferSummaryCard
 *
 * Mission-first structured rewrite of the job description.
 * Auto-loads POST /ai/structure-offer on mount.
 * Module-level cache: same offer_id → zero re-fetch.
 *
 * Block order (what the candidate needs to know):
 *   1. quick_read       — 1 sentence: what is the job
 *   2. mission_summary  — 2-4 sentences: what you will do
 *   3. responsibilities — concrete actions
 *   4. tools_environment — tools and tech stack
 *   5. role_context     — VIE, international, travel, etc.
 *   6. key_requirements — really required
 *   7. nice_to_have     — bonus
 *
 * Error contract:
 * - Never returns null / blank — always shows at least a fallback
 * - Each block is independently guarded
 */
import { useEffect, useRef, useState } from "react";
import {
  Briefcase,
  CheckSquare,
  Layers,
  Lightbulb,
  Sparkles,
  Star,
  Terminal,
} from "lucide-react";
import {
  structureOffer,
  type StructuredOfferSummary,
  type DescriptionStructuredV1,
} from "../lib/api";

// ---------------------------------------------------------------------------
// Module cache — offer structure is profile-independent
// ---------------------------------------------------------------------------
const _cache = new Map<string, StructuredOfferSummary>();

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function hasContent(s: StructuredOfferSummary): boolean {
  return !!(
    s.mission_summary ||
    s.responsibilities.length > 0 ||
    s.key_requirements.length > 0 ||
    s.quick_read
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
function Skeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-10 w-3/4 rounded-2xl bg-slate-100" />
      <div className="h-20 rounded-2xl bg-slate-100" />
      <div className="grid grid-cols-2 gap-3">
        <div className="h-28 rounded-2xl bg-slate-100" />
        <div className="h-28 rounded-2xl bg-slate-100" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Minimum fallback (shown when API fails or returns empty)
// ---------------------------------------------------------------------------
function MinimalFallback({
  missions,
  requirements,
}: {
  missions: string[];
  requirements: string[];
}) {
  if (missions.length === 0 && requirements.length === 0) {
    return (
      <p className="text-xs italic text-slate-400 py-2">
        Structuration du poste indisponible pour le moment.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {missions.length > 0 && (
        <div className="rounded-2xl border border-white/80 bg-white/90 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-indigo-700 mb-2">
            Missions
          </div>
          <ul className="space-y-1.5">
            {missions.slice(0, 4).map((m, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
                {m}
              </li>
            ))}
          </ul>
        </div>
      )}
      {requirements.length > 0 && (
        <div className="rounded-2xl border border-white/80 bg-white/90 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-700 mb-2">
            Prérequis détectés
          </div>
          <ul className="space-y-1.5">
            {requirements.slice(0, 4).map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-400" />
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Block + list helpers
// ---------------------------------------------------------------------------
function Block({
  icon,
  label,
  color,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-white/80 bg-white/90 p-4 shadow-[0_4px_16px_rgba(15,23,42,0.05)]">
      <div className={`flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] ${color} mb-3`}>
        <span className="shrink-0">{icon}</span>
        {label}
      </div>
      {children}
    </div>
  );
}

function BulletList({ items, color }: { items: string[]; color: string }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
          <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${color}`} />
          {item}
        </li>
      ))}
    </ul>
  );
}

function TagList({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item, i) => (
        <span
          key={i}
          className="rounded-full border border-slate-200 bg-slate-50 px-3 py-0.5 text-xs text-slate-600"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Full display — mission-first order
// ---------------------------------------------------------------------------
function SummaryDisplay({ summary }: { summary: StructuredOfferSummary }) {
  const hasResponsibilities = summary.responsibilities.length > 0;
  const hasTools = summary.tools_environment.length > 0;
  const hasContext = summary.role_context.length > 0;
  const hasRequirements = summary.key_requirements.length > 0;
  const hasNiceToHave = summary.nice_to_have.length > 0;

  return (
    <div className="space-y-3">

      {/* ── 1. Quick read ─────────────────────────────────────────────── */}
      {summary.quick_read && (
        <div className="flex items-start gap-3 rounded-2xl border border-sky-100 bg-sky-50/60 px-5 py-4">
          <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-sky-600" />
          <p className="text-sm font-medium leading-6 text-sky-900">{summary.quick_read}</p>
        </div>
      )}

      {/* ── 2. Mission summary ────────────────────────────────────────── */}
      {summary.mission_summary && (
        <Block
          icon={<Briefcase className="h-3.5 w-3.5" />}
          label="Ce que vous ferez"
          color="text-indigo-700"
        >
          <p className="text-sm leading-7 text-slate-700">{summary.mission_summary}</p>
        </Block>
      )}

      {/* ── 3. Responsibilities + Tools (side by side when both exist) ── */}
      {(hasResponsibilities || hasTools) && (
        <div className={hasResponsibilities && hasTools ? "grid gap-3 lg:grid-cols-2" : ""}>
          {hasResponsibilities && (
            <Block
              icon={<CheckSquare className="h-3.5 w-3.5" />}
              label="Responsabilités clés"
              color="text-emerald-700"
            >
              <BulletList items={summary.responsibilities} color="bg-emerald-400" />
            </Block>
          )}
          {hasTools && (
            <Block
              icon={<Terminal className="h-3.5 w-3.5" />}
              label="Outils &amp; environnement"
              color="text-cyan-700"
            >
              <TagList items={summary.tools_environment} />
            </Block>
          )}
        </div>
      )}

      {/* ── 4. Context + Requirements (side by side when both exist) ──── */}
      {(hasContext || hasRequirements) && (
        <div className={hasContext && hasRequirements ? "grid gap-3 lg:grid-cols-2" : ""}>
          {hasContext && (
            <Block
              icon={<Layers className="h-3.5 w-3.5" />}
              label="Contexte du poste"
              color="text-slate-600"
            >
              <TagList items={summary.role_context} />
            </Block>
          )}
          {hasRequirements && (
            <Block
              icon={<Star className="h-3.5 w-3.5" />}
              label="Compétences requises"
              color="text-violet-700"
            >
              <BulletList items={summary.key_requirements} color="bg-violet-400" />
            </Block>
          )}
        </div>
      )}

      {/* ── 5. Nice to have ───────────────────────────────────────────── */}
      {hasNiceToHave && (
        <Block
          icon={<Sparkles className="h-3.5 w-3.5" />}
          label="Appréciés mais non bloquants"
          color="text-amber-700"
        >
          <BulletList items={summary.nice_to_have} color="bg-amber-300" />
        </Block>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
interface Props {
  offerId: string;
  structuredV1?: DescriptionStructuredV1 | null;
}

export function StructuredOfferSummaryCard({ offerId, structuredV1 }: Props) {
  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const [summary, setSummary] = useState<StructuredOfferSummary | null>(null);
  const fetchedRef = useRef(false);

  // Stable fallback missions/requirements from structuredV1
  const fallbackMissions = structuredV1?.missions ?? [];
  const fallbackRequirements = structuredV1?.requirements ?? [];

  useEffect(() => {
    if (!offerId || fetchedRef.current) return;

    const cached = _cache.get(offerId);
    if (cached) {
      setSummary(cached);
      setState("done");
      return;
    }

    fetchedRef.current = true;

    structureOffer({
      offer_id: offerId,
      missions: structuredV1?.missions ?? [],
      requirements: structuredV1?.requirements ?? [],
      tools_stack: structuredV1?.tools_stack ?? [],
      context_tags: structuredV1?.context ?? [],
    })
      .then((resp) => {
        _cache.set(offerId, resp.summary);
        setSummary(resp.summary);
        setState("done");
      })
      .catch(() => setState("error"));
    // intentionally NOT listing structuredV1 as dep — it's context hints only;
    // the backend loads description from DB. fetchedRef prevents double-fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offerId]);

  if (state === "loading") return <Skeleton />;

  // Error state — show pre-extracted data if available, never blank
  if (state === "error") {
    return <MinimalFallback missions={fallbackMissions} requirements={fallbackRequirements} />;
  }

  // Done but empty content — same fallback
  if (!summary || !hasContent(summary)) {
    return <MinimalFallback missions={fallbackMissions} requirements={fallbackRequirements} />;
  }

  return <SummaryDisplay summary={summary} />;
}
