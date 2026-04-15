import { ArrowRight, Building2, MapPin, Star } from "lucide-react";
import type { OfferExplanation, OfferIntelligence, ScoringV3, SemanticExplainability } from "../../lib/api";
import { buildOfferNarrative } from "./offerNarrative";

export interface InboxCardV2Props {
  offerId: string;
  company: string;
  title: string;
  location?: string;
  score: number;
  explanation: OfferExplanation;
  semanticExplainability?: SemanticExplainability | null;
  scoringV3?: ScoringV3 | null;
  offerIntelligence?: OfferIntelligence | null;
  onOpenDetails: (offerId: string) => void;
  onShortlist: (offerId: string) => void;
  secondaryActionLabel?: string;
}

function scoreTone(score: number): string {
  if (score >= 75) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (score >= 55) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function formatContractTag(offerId: string): string {
  return offerId.startsWith("BF-") ? "V.I.E" : "Offre";
}

export function InboxCardV2({
  offerId,
  company,
  title,
  location,
  score,
  explanation,
  semanticExplainability,
  scoringV3,
  offerIntelligence,
  onOpenDetails,
  onShortlist,
  secondaryActionLabel = "Shortlist",
}: InboxCardV2Props) {
  const displayScore =
    typeof scoringV3?.score_pct === "number"
      ? scoringV3.score_pct
      : typeof explanation.score === "number"
        ? explanation.score
        : score;
  const narrative = buildOfferNarrative({
    explanation,
    offerIntelligence,
    semanticExplainability,
    scoringV3,
  });

  return (
    <article className="group flex h-full flex-col rounded-[1.75rem] border border-slate-200/80 bg-white/95 p-5 shadow-[0_16px_40px_rgba(15,23,42,0.08)] transition-all hover:-translate-y-0.5 hover:shadow-[0_24px_55px_rgba(15,23,42,0.12)]">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap gap-1.5">
            <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-sky-700">
              {formatContractTag(offerId)}
            </span>
          </div>
          <h3 className="line-clamp-2 text-lg font-semibold leading-snug text-slate-950">{title}</h3>
          <div className="mt-2 flex items-center gap-2 text-sm text-slate-600">
            <Building2 className="h-4 w-4 text-slate-400" />
            <span className="line-clamp-1">{company || "Entreprise"}</span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            <MapPin className="h-4 w-4 text-slate-400" />
            <span className="line-clamp-1">{location || "Localisation à préciser"}</span>
          </div>
        </div>

        <div className={`shrink-0 rounded-2xl border px-3 py-3 text-center ${scoreTone(displayScore)}`}>
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em]">Score</div>
          <div className="mt-1 text-2xl font-semibold leading-none">{displayScore}</div>
        </div>
      </div>

      <div className="mt-4 rounded-[1.25rem] border border-sky-100 bg-sky-50/80 p-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">
          Ce qu'il faut retenir
        </div>
        <ul className="mt-3 space-y-2 text-sm leading-relaxed text-slate-700">
          {narrative.bullets.map((bullet) => (
            <li key={`${offerId}-${bullet}`} className="flex gap-2">
              <Star className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky-600" />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      </div>

      {narrative.reinforce.length > 0 && (
        <div className="mt-4 text-sm text-slate-600">
          <span className="font-semibold text-slate-900">À renforcer :</span>{" "}
          {narrative.reinforce.join(", ")}
        </div>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 pt-5">
        <button
          type="button"
          onClick={() => onOpenDetails(offerId)}
          className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
        >
          Voir l'offre
          <ArrowRight className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => onShortlist(offerId)}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
        >
          {secondaryActionLabel}
        </button>
      </div>
    </article>
  );
}
