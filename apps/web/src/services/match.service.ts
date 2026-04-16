/**
 * Service de matching
 * Contrat aligné sur backend SHA 8d64e59
 *
 * Stratégie: "Panic in Dev, Grace in Prod"
 * - DEV: throw si contrat cassé
 * - PROD: fallback objet sain + message
 */

import type { MatchRequest, MatchResponse, MatchItem } from "../types/match";
import MOCK from "./mocks/match_result.json";
import { apiFetch } from "../lib/api";

const IS_DEV = import.meta.env.DEV;
const FORCE_MOCK = false;

/**
 * Objet de réponse "sain" en cas d'erreur (PROD uniquement)
 */
function safeResponse(message: string): MatchResponse {
  return {
    profile_id: null,
    threshold: 80,
    received_offers: 0,
    results: [],
    message,
  };
}

/**
 * Normalise et valide la réponse API.
 *
 * DEV: throw si contrat cassé
 * PROD: retourne objet sain avec message d'erreur
 */
export function normalizeMatchResponse(data: unknown): MatchResponse {
  try {
    // Vérification: data est un objet
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new Error("Response is not an object");
    }

    const obj = data as Record<string, unknown>;

    // Vérification: results est un array
    if (!Array.isArray(obj.results)) {
      throw new Error("results is missing or not an array");
    }

    // Vérification: received_offers est un number
    if (typeof obj.received_offers !== "number") {
      throw new Error("received_offers is missing or not a number");
    }

    // Normaliser les results
    const results: MatchItem[] = obj.results.map((item: unknown, index: number) => {
      if (!item || typeof item !== "object") {
        throw new Error(`results[${index}] is not an object`);
      }

      const r = item as Record<string, unknown>;

      // Vérification: offer_id obligatoire
      if (typeof r.offer_id !== "string" || !r.offer_id) {
        throw new Error(`results[${index}].offer_id is missing or not a string`);
      }

      return {
        offer_id: r.offer_id,
        score: typeof r.score === "number" ? r.score : 0,
        reasons: Array.isArray(r.reasons) ? r.reasons.map(String) : [],
      };
    });

    // Normaliser profile_id et message
    const profile_id =
      typeof obj.profile_id === "string" && obj.profile_id !== ""
        ? obj.profile_id
        : null;

    const message =
      typeof obj.message === "string" && obj.message !== ""
        ? obj.message
        : null;

    const threshold =
      typeof obj.threshold === "number" ? obj.threshold : 80;

    return {
      profile_id,
      threshold,
      received_offers: obj.received_offers,
      results,
      message,
    };
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : "Unknown validation error";

    if (IS_DEV) {
      throw new Error(`[DEV] Contract violation: ${errorMsg}`);
    }

    console.error("[PROD] Match response validation failed:", errorMsg);
    return safeResponse(`API error: ${errorMsg}`);
  }
}

/**
 * Petit délai artificiel pour simuler une latence réseau.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retourne un résultat de match depuis un mock local.
 */
export async function getMatchResultMock(): Promise<MatchResponse> {
  await sleep(200);
  return normalizeMatchResponse(MOCK);
}

/**
 * Appel direct à l'API backend de matching.
 */
export async function runMatchApi(payload: MatchRequest): Promise<MatchResponse> {
  const res = await apiFetch("/v1/match", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API /v1/match (${res.status}) ${txt}`);
  }

  const data: unknown = await res.json();
  return normalizeMatchResponse(data);
}

/**
 * Fonction unique appelée par le front.
 *
 * - FORCE_MOCK = true → mock obligatoire
 * - sinon → tentative API
 * - si l'API échoue → fallback automatique sur le mock
 */
export async function runMatch(payload: MatchRequest): Promise<MatchResponse> {
  if (FORCE_MOCK) {
    return getMatchResultMock();
  }

  try {
    return await runMatchApi(payload);
  } catch (err) {
    console.warn("[runMatch] API failed, fallback to mock", err);
    return getMatchResultMock();
  }
}
