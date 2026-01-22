/**
 * Types pour le contrat /v1/match
 * Aligné sur backend Sprint 11
 */

export type MatchReason = string;

export type MatchRequest = {
  profile: unknown;
  offers: unknown[];
};

// Statuts possibles pour un critère diagnostic
export type DiagnosticStatus = "OK" | "PARTIAL" | "KO";

// Résultat diagnostic pour un critère
export type DiagnosticCriterion = {
  status: DiagnosticStatus;
  details?: string | null;
  missing: string[];
};

// Diagnostic complet pour une offre
export type DiagnosticResult = {
  global_verdict: DiagnosticStatus;
  top_blocking_reasons: string[];
  hard_skills: DiagnosticCriterion;
  soft_skills: DiagnosticCriterion;
  languages: DiagnosticCriterion;
  education: DiagnosticCriterion;
  vie_eligibility: DiagnosticCriterion;
};

export type MatchItem = {
  offer_id: string;
  score: number;
  reasons?: MatchReason[];
  diagnostic?: DiagnosticResult | null;
};

export type MatchResponse = {
  profile_id: string | null;
  threshold: number;
  received_offers: number;
  results: MatchItem[];
  message: string | null;
};
