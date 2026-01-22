import { useMemo, useState } from "react";
import { runMatch } from "../services/match.service";
import type { MatchItem, MatchResponse } from "../types/match";

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

function formatScore(score: number): string {
  return `${Math.round(score)}%`;
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
  const [offers, setOffers] = useState<unknown[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<MatchResponse | null>(null);

  const canRun = useMemo(() => Boolean(profile && offers.length > 0), [profile, offers]);

  const filteredResults = useMemo(() => {
    if (!response) return null;
    return response.results
      .filter((r) => r.score >= SCORE_THRESHOLD)
      .sort((a, b) => b.score - a.score);
  }, [response]);

  const nearMatches = useMemo(() => {
    if (!response) return null;
    return response.results
      .filter((r) => r.score >= 70 && r.score < SCORE_THRESHOLD)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3);
  }, [response]);

  const offersMap = useMemo(() => {
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
    setResponse(null);
    try {
      const p = await loadJson("/fixtures/profile_demo.json");
      const o = await loadJson<unknown[]>("/fixtures/offers_demo.json");
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
    setResponse(null);

    try {
      const data = await runMatch({ profile, offers });
      setResponse(data);
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
        <div>Fixtures offres: {offers.length > 0 ? `✅ (${offers.length})` : "—"}</div>
      </div>

      {error && (
        <div style={{ marginTop: 16, color: "#e11d48" }}>{error}</div>
      )}

      {response && (
        <div style={{ marginTop: 16, padding: 10, backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 6, fontSize: 13 }}>
          <strong>Résumé API:</strong> received_offers={response.received_offers}, results={response.results.length}, threshold={response.threshold}
        </div>
      )}

      {filteredResults && (
        <div style={{ marginTop: 24 }}>
          <h2>Résultats (≥{SCORE_THRESHOLD}%)</h2>

          {filteredResults.length === 0 && (
            <div>Aucun match ≥ {SCORE_THRESHOLD}%</div>
          )}

          <div style={{ display: "grid", gap: 12 }}>
            {filteredResults.map((r: MatchItem, i: number) => {
              const offer = offersMap.get(r.offer_id);
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

                  {r.reasons && r.reasons.length > 0 && (
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
          {nearMatches.map((r: MatchItem, i: number) => {
            const offer = offersMap.get(r.offer_id);
            return (
              <div key={i} style={{ marginBottom: 8 }}>
                <strong>{formatScore(r.score)}</strong> — {formatValue(getField(offer, "title"))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
