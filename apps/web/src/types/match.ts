/**
 * Types pour le contrat /v1/match
 * Aligné sur backend SHA 8d64e59
 */

export type MatchReason = string;

export type MatchRequest = {
  profile: unknown;
  offers: unknown[];
};

export type MatchItem = {
  offer_id: string;
  score: number;
  reasons?: MatchReason[];
};

export type MatchResponse = {
  profile_id: string | null;
  threshold: number;
  received_offers: number;
  results: MatchItem[];
  message: string | null;
};
