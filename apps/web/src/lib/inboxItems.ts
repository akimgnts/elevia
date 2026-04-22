import type {
  CareerIntelligence,
  ExplainBlock,
  InboxItem,
  OfferExplanation,
  OfferIntelligence,
  ScoringV2,
  ScoringV3,
  SemanticExplainability,
} from "./api";

export type NormalizedInboxItem = {
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
  scoring_v3?: ScoringV3 | null;
  career_intelligence?: CareerIntelligence | null;
  offer_cluster?: string;
  domain_bucket?: "strict" | "neighbor" | "out";
  signal_score?: number;
  coherence?: "ok" | "suspicious";
  near_match_count?: number;
  core_matched_count?: number;
  core_total_count?: number;
  dominant_reason?: string;
};

function normalizeScore(value: unknown): number {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  const scaled = value > 0 && value < 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(scaled)));
}

function cleanDescriptionSnippet(value?: string | null, maxLen = 180): string {
  if (!value) return "";
  const stripped = value.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  if (stripped.length <= maxLen) return stripped;
  return `${stripped.slice(0, maxLen).trim()}…`;
}

function buildFallbackExplanation(rec: Record<string, unknown>, score: number): OfferExplanation {
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
  const reasons = Array.isArray(rec.reasons) ? (rec.reasons as string[]) : [];
  return {
    score,
    fit_label: score >= 75 ? "Alignement fort" : score >= 50 ? "Alignement moyen" : "Alignement faible",
    summary_reason: reasons[0] || "Offre disponible pour revue.",
    strengths: matchedDisplay.slice(0, 3),
    gaps: missingDisplay.slice(0, 3),
    blockers: [],
    next_actions: [],
  };
}

function resolvePrimaryScore(rec: Record<string, unknown>, explanation: OfferExplanation): number {
  const scoringV3 =
    rec.scoring_v3 && typeof rec.scoring_v3 === "object"
      ? (rec.scoring_v3 as ScoringV3)
      : null;
  if (typeof scoringV3?.score_pct === "number") {
    return normalizeScore(scoringV3.score_pct);
  }
  const scoringV2 =
    rec.scoring_v2 && typeof rec.scoring_v2 === "object"
      ? (rec.scoring_v2 as ScoringV2)
      : null;
  if (typeof scoringV2?.score_pct === "number") {
    return normalizeScore(scoringV2.score_pct);
  }
  return normalizeScore(
    typeof explanation.score === "number"
      ? explanation.score
      : typeof rec.score_pct === "number"
        ? rec.score_pct
        : typeof rec.score === "number"
          ? rec.score
          : rec.match_score
  );
}

export function primaryDisplayScore(
  item: Pick<NormalizedInboxItem, "score" | "explanation" | "scoring_v2" | "scoring_v3">
): number {
  if (typeof item.scoring_v3?.score === "number") {
    return item.scoring_v3.score * 100;
  }
  if (typeof item.scoring_v2?.score === "number") {
    return item.scoring_v2.score * 100;
  }
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

export function sortInboxItemsForDisplay(items: NormalizedInboxItem[]): NormalizedInboxItem[] {
  return [...items].sort((a, b) => {
    return (
      primaryDisplayScore(b) - primaryDisplayScore(a) ||
      blockersCount(a) - blockersCount(b) ||
      strengthsCount(b) - strengthsCount(a) ||
      recencyValue(b.publication_date) - recencyValue(a.publication_date) ||
      a.offer_id.localeCompare(b.offer_id)
    );
  });
}

export function normalizeInboxItems(raw: unknown): NormalizedInboxItem[] {
  if (!Array.isArray(raw)) {
    console.warn("[inbox] API items is not an array:", typeof raw);
    return [];
  }
  const results: NormalizedInboxItem[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const rec = item as Record<string, unknown>;
    const offerId = (rec.offer_id || rec.id) as string | undefined;
    if (!offerId) {
      console.warn("[inbox] Item missing offer_id:", rec);
      continue;
    }
    const baseExplanation =
      rec.explanation && typeof rec.explanation === "object"
        ? (rec.explanation as OfferExplanation)
        : null;
    const score = resolvePrimaryScore(rec, baseExplanation ?? buildFallbackExplanation(rec, 0));
    const explanation = baseExplanation ?? buildFallbackExplanation(rec, score);
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
      title_clean: typeof rec.title_clean === "string" ? rec.title_clean : null,
      company: typeof rec.company === "string" ? rec.company : null,
      country: typeof rec.country === "string" ? rec.country : null,
      city: typeof rec.city === "string" ? rec.city : null,
      publication_date: typeof rec.publication_date === "string" ? rec.publication_date : null,
      score,
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
      rome:
        rec.rome && typeof rec.rome === "object"
          ? (rec.rome as { rome_code: string; rome_label: string })
          : null,
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
      scoring_v3:
        rec.scoring_v3 && typeof rec.scoring_v3 === "object"
          ? (rec.scoring_v3 as ScoringV3)
          : null,
      career_intelligence:
        rec.career_intelligence && typeof rec.career_intelligence === "object"
          ? (rec.career_intelligence as CareerIntelligence)
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

export function normalizeAndSortInboxItems(raw: InboxItem[] | unknown): NormalizedInboxItem[] {
  return sortInboxItemsForDisplay(normalizeInboxItems(raw));
}
