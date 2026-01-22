import type { MatchResult } from "../types/match";
import MOCK from "./mocks/match_result.json";

/**
 * Active ce flag pour FORCER l'utilisation du mock,
 * même si le backend est disponible.
 */
const FORCE_MOCK = false;

/**
 * Petit délai artificiel pour simuler une latence réseau
 * (utile pour tester les loaders côté UI).
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retourne un résultat de match depuis un mock local.
 * Utilisé en fallback ou en mode front-only.
 */
export async function getMatchResultMock(): Promise<MatchResult> {
  await sleep(200);
  return MOCK as MatchResult;
}

/**
 * Appel direct à l'API backend de matching.
 */
export async function runMatchApi(payload: unknown): Promise<MatchResult> {
  const res = await fetch("/v1/match", {
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

  return (await res.json()) as MatchResult;
}

/**
 * Fonction unique appelée par le front.
 *
 * Règles :
 * - FORCE_MOCK = true → mock obligatoire
 * - sinon → tentative API
 * - si l'API échoue → fallback automatique sur le mock
 *
 * 👉 Le front ne sait JAMAIS si le backend est down ou non.
 */
export async function runMatch(payload: unknown): Promise<MatchResult> {
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
