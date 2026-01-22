import { useMemo, useState } from "react";
import { runMatch } from "../services/match.service";

/* ======================
   Types
====================== */

type MatchReason = string;

type MatchItem = {
  offer_id?: string;
  score?: number;
  reasons?: MatchReason[];
  [k: string]: unknown;
};

type ApiResponse =
  | { results?: MatchItem[]; items?: MatchItem[]; matches?: MatchItem[] }
  | MatchItem[];

/* ======================
   Helpers data
====================== */

async function loadJson<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    headers: { "Cache-Control": "no-cache" },
  });
  if (!res.ok) {
    throw new Error(`Impossible de charger ${path} (${res.status})`);
  }
  return res.json() as Promise<T>;
}

function normalizeResults(data: ApiResponse): MatchItem[] {
  if (Array.isArray(data)) return data;
  return data.results ?? data.items ?? data.matches ?? [];
}

function normalizeScore(score: unknown): number {
  if (typeof score !== "number") return 0;
  return score > 1.01 ? score : score * 100;
}

function formatScore(score: unknown): string {
  if (typeof score !== "number") return "—";
  return score > 1.01
    ? `${Math.round(score)}%`
    : `${Math.round(score * 100)}%`;
}

const SCORE_THRESHOLD = 80;

function getField(obj: unknown, key: string): unknown {
  if (obj && typeof obj === "object" && key in obj) {
    return (obj as Record<string, unknown>)[key];
  }
  return undefined;
}

function formatList(val: unknown, max = 5): string {
  if (!Array.isArray(val) || val.length === 0) return "Non renseigné";
  const items = val.slice(0, max).map(String);
  return items.join(", ") + (val.length > max ? "…" : "");
}

function formatValue(val: unknown): string {
  if (val === undefined || val === null || val === "") return "Non renseigné";
  if (Array.isArray(val)) return formatList(val);
  return String(val);
}

/* ======================
   Page
====================== */

export default function MatchPage() {
  const [profile, setProfile] = useState<unknown>(null);
  const [offers, setOffers] = useState<unknown>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<MatchItem[] | null>(null);

  const canRun = useMemo(() => Boolean(profile && offers), [profile, offers]);

  const filteredResults = useMemo(() => {
    if (!results) return null;
    return results
      .filter((r) => normalizeScore(r.score) >= SCORE_THRESHOLD)
      .sort((a, b) => normalizeScore(b.score) - normalizeScore(a.score));
  }, [results]);

  const nearMatches = useMemo(() => {
    if (!results) return null;
    return results
      .filter((r) => {
        const s = normalizeScore(r.score);
        return s >= 70 && s < SCORE_THRESHOLD;
      })
      .sort((a, b) => normalizeScore(b.score) - normalizeScore(a.score))
      .slice(0, 3);
  }, [results]);

  const offersMap = useMemo(() => {
    if (!Array.isArray(offers)) return new Map<string, unknown>();
    const map = new Map<string, unknown>();
    for (const o of offers) {
      const id = getField(o, "id") ?? getField(o, "offer_id");
      if (id) map.set(String(id), o);
    }
    return map;
  }, [offers]);

  /* ======================
     Actions
  ====================== */

  async function handleLoadFixtures() {
    setError(null);
    setResults(null);
    try {
      const p = await loadJson("/fixtures/profile_demo.json");
      const o = await loadJson("/fixtures/offers_demo.json");
      setProfile(p);
      setOffers(o);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    }
  }

  async function handleRunMatch() {
    if (!canRun) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = (await runMatch({ profile, offers })) as ApiResponse;
      setResults(normalizeResults(data));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  /* ======================
     Render
  ====================== */

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Match Runner (MVP)</h1>

      <p style={{ opacity: 0.8 }}>
        Charge les fixtures, puis lance le match.
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        <button onClick={handleLoadFixtures}>Charger fixtures</button>
        <button onClick={handleRunMatch} disabled={!canRun || loading}>
          {loading ? "Match en cours…" : "Lancer le match"}
        </button>
      </div>

      <div style={{ marginTop: 16 }}>
        <div>Fixtures profil: {profile ? "✅" : "—"}</div>
        <div>Fixtures offres: {offers ? "✅" : "—"}</div>
      </div>

      {error && (
        <div style={{ marginTop: 16, color: "#e11d48" }}>{error}</div>
      )}

      {filteredResults && (
        <div style={{ marginTop: 24 }}>
          <h2>Résultats</h2>

          {filteredResults.length === 0 && (
            <div>Aucun match ≥ {SCORE_THRESHOLD}%</div>
          )}

          <div style={{ display: "grid", gap: 12 }}>
            {filteredResults.map((r, i) => {
              const offer = offersMap.get(r.offer_id ?? "");
              return (
                <div
                  key={r.offer_id ?? i}
                  style={{ padding: 12, border: "1px solid #ddd" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                    }}
                  >
                    <strong>
                      {formatValue(getField(offer, "title"))}
                    </strong>
                    <strong>{formatScore(r.score)}</strong>
                  </div>

                  <div style={{ fontSize: 13, opacity: 0.8 }}>
                    {formatValue(getField(offer, "company"))} —{" "}
                    {formatValue(getField(offer, "country"))}
                  </div>

                  {Array.isArray(r.reasons) && r.reasons.length > 0 && (
                    <ul style={{ marginTop: 8 }}>
                      {r.reasons.slice(0, 3).map((x, idx) => (
                        <li key={idx}>{x}</li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {nearMatches && nearMatches.length > 0 && (
        <div style={{ marginTop: 32, opacity: 0.8 }}>
          <h3>Correspondances proches (70–79%)</h3>
          {nearMatches.map((r, i) => (
            <div key={i}>{formatScore(r.score)}</div>
          ))}
        </div>
      )}
    </div>
  );
}
