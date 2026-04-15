import type { OfferExplanation, OfferIntelligence, ScoringV3, SemanticExplainability } from "../../lib/api";

export type OfferNarrative = {
  bullets: string[];
  reinforce: string[];
  summary: string;
  expectations: string[];
  gaps: string[];
};

const NOISE = new Set([
  "across",
  "advanced",
  "accuracy",
  "analyst",
  "business intelligence",
  "fit",
  "match",
  "signal",
  "signals",
  "matching",
  "strong fit",
  "partial fit",
  "weak fit",
  "lecture du match",
]);

const GENERIC = new Set([
  "communication",
  "collaboration",
  "organisation",
  "teamwork",
  "leadership",
  "problem solving",
]);

const FRENCH_MAP: Record<string, string> = {
  "data analysis": "analyse de données",
  "business analysis": "analyse business",
  "financial analysis": "analyse financière",
  "project management": "gestion de projet",
  "supply chain": "supply chain",
  "software / it": "informatique",
  "data / bi": "data et BI",
  reporting: "reporting",
  analytics: "analyse de données",
  analyst: "analyse",
  finance: "finance",
  marketing: "marketing",
  communication: "communication",
  "human resources": "ressources humaines",
  hr: "ressources humaines",
  sql: "SQL",
  python: "Python",
  excel: "Excel",
  "power bi": "Power BI",
  bi: "BI",
  etl: "ETL",
  dashboard: "tableaux de bord",
  "machine learning": "machine learning",
  anglais: "anglais professionnel",
  english: "anglais professionnel",
};

const ROLE_LABELS: Record<string, string> = {
  data_analytics: "data et BI",
  business_analysis: "analyse business",
  finance_ops: "finance",
  legal_compliance: "juridique et conformité",
  sales_business_dev: "business development",
  marketing_communication: "marketing et communication",
  hr_ops: "ressources humaines",
  supply_chain_ops: "supply chain et opérations",
  project_ops: "gestion de projet",
  software_it: "informatique",
  generalist_other: "environnement polyvalent",
};

function toKey(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

function titleCase(value: string): string {
  if (value === value.toUpperCase()) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function cleanSignal(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;
  const key = toKey(raw);
  if (!key || NOISE.has(key)) return null;
  const mapped = FRENCH_MAP[key] ?? raw;
  const finalKey = toKey(mapped);
  if (!finalKey || NOISE.has(finalKey)) return null;
  if (finalKey.length < 2) return null;
  return titleCase(mapped);
}

function uniqueClean(values: string[], limit: number, includeGeneric = true): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const cleaned = cleanSignal(value);
    if (!cleaned) continue;
    const key = toKey(cleaned);
    if (!includeGeneric && GENERIC.has(key)) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(cleaned);
    if (result.length >= limit) break;
  }
  return result;
}

function roleLabel(role?: string | null): string | null {
  if (!role) return null;
  return ROLE_LABELS[role] ?? null;
}

function domainLabel(domain?: string | null): string | null {
  if (!domain) return null;
  const cleaned = cleanSignal(domain);
  return cleaned ? cleaned.toLowerCase() : null;
}

function alignmentBullet(semantic: SemanticExplainability | null | undefined, scorePct: number | null): string {
  const alignment = semantic?.role_alignment?.alignment;
  if (alignment === "high" || (scorePct ?? 0) >= 75) {
    return "Ton profil est déjà aligné avec les missions principales du poste.";
  }
  if (alignment === "medium" || (scorePct ?? 0) >= 55) {
    return "Ton profil a déjà une base crédible pour ce type de poste.";
  }
  return "Le poste reste accessible, mais il demande encore un vrai ajustement de profil.";
}

function environmentBullet(intelligence: OfferIntelligence | null | undefined): string | null {
  const role = roleLabel(intelligence?.dominant_role_block);
  const domain = domainLabel(intelligence?.dominant_domains?.[0]);
  if (role && domain) {
    return `Le poste est surtout orienté ${role}, dans un contexte ${domain}.`;
  }
  if (role) {
    return `Le poste est surtout orienté ${role}.`;
  }
  if (domain) {
    return `Le poste évolue surtout dans un environnement ${domain}.`;
  }
  return null;
}

function strengthsBullet(explanation: OfferExplanation, intelligence: OfferIntelligence | null | undefined): string | null {
  const strengths = uniqueClean(
    [
      ...(explanation.strengths ?? []),
      ...((intelligence?.top_offer_signals ?? []).slice(0, 2)),
    ],
    2,
    false,
  );
  if (strengths.length === 0) return null;
  if (strengths.length === 1) {
    return `Tu as déjà une base solide en ${strengths[0]}.`;
  }
  return `Tu peux t'appuyer sur une base solide en ${strengths[0]} et ${strengths[1]}.`;
}

function buildSummary(bullets: string[]): string {
  return bullets.slice(0, 2).join(" ");
}

function buildExpectations(intelligence: OfferIntelligence | null | undefined): string[] {
  const values = uniqueClean(
    [
      ...(intelligence?.required_skills ?? []),
      ...(intelligence?.top_offer_signals ?? []),
      ...(intelligence?.optional_skills ?? []),
    ],
    3,
    false,
  );
  return values.map((value) => {
    const lower = toKey(value);
    if (lower === "reporting") return "suivi et reporting";
    if (lower === "analyse de donnees") return "capacité à analyser et structurer l'information";
    if (lower === "analyse business") return "interaction avec des équipes business";
    if (lower === "gestion de projet") return "coordination et suivi d'activités";
    if (lower === "tableaux de bord") return "pilotage par tableaux de bord";
    return value;
  });
}

export function buildOfferNarrative(input: {
  explanation: OfferExplanation;
  offerIntelligence?: OfferIntelligence | null;
  semanticExplainability?: SemanticExplainability | null;
  scoringV3?: ScoringV3 | null;
}): OfferNarrative {
  const { explanation, offerIntelligence, semanticExplainability, scoringV3 } = input;
  const scorePct =
    typeof scoringV3?.score_pct === "number"
      ? scoringV3.score_pct
      : typeof explanation.score === "number"
        ? explanation.score
        : null;

  const bullets = [
    alignmentBullet(semanticExplainability, scorePct),
    environmentBullet(offerIntelligence),
    strengthsBullet(explanation, offerIntelligence),
  ].filter((value): value is string => Boolean(value)).slice(0, 3);

  const reinforce = uniqueClean(
    [
      ...(explanation.blockers ?? []),
      ...(explanation.gaps ?? []),
      ...(semanticExplainability?.signal_alignment?.missing_core_signals ?? []),
    ],
    2,
    false,
  );

  const gaps = uniqueClean(
    [
      ...(explanation.blockers ?? []),
      ...(explanation.gaps ?? []),
      ...(semanticExplainability?.signal_alignment?.missing_core_signals ?? []),
    ],
    3,
    false,
  );

  return {
    bullets,
    reinforce,
    summary: buildSummary(bullets),
    expectations: buildExpectations(offerIntelligence),
    gaps,
  };
}
