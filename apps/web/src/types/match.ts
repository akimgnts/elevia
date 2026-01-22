export type MatchReason = string;

export type MatchItem = {
  offer_id?: string;
  score?: number;
  reasons?: MatchReason[];
  [k: string]: unknown;
};

export type MatchApiResponse =
  | { results?: MatchItem[]; items?: MatchItem[]; matches?: MatchItem[] }
  | MatchItem[];
import type { Offer } from "./offer";

export type MatchResult = {
  profile_id: string;
  generated_at: string; // ISO date
  matches: Offer[];
};

