import { useMemo, useState } from "react";

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

async function loadJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { "Cache-Control": "no-cache" } });
  if (!res.ok) throw new Error(`Impossible de charger ${path} (${res.status})`);
  return res.json() as Promise<T>;
}

function normalizeResults(data: ApiResponse): MatchItem[] {
  if (Array.isArray(data)) return data;
  return data.results ?? data.items ?? data.matches ?? [];
}

function formatScore(score: unknown): string {
  if (typeof score !== "number") return "—";
  if (score > 1.01) return `${Math.round(score)}%`;
  return `${Math.round(score * 100)}%`;
}

export default function MatchPage() {
  const [profile, setProfile] = useState<unknown>(null);
  const [offers, setOffers] = useState<unknown>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<MatchItem[] | null>(null);

  const canRun = useMemo(() => Boolean(profile && offers), [profile, offers]);

  async function handleLoadFixtures() {
    setError(null);
    setResults(null);
    try {
      const p = await loadJson<unknown>("/fixtures/profile_demo.json");
      const o = await loadJson<unknown>("/fixtures/offers_demo.json");
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
      const res = await fetch("/v1/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile,
          offers,
        }),
      });

      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`API /v1/match (${res.status}) ${txt}`);
      }

      const data = (await res.json()) as ApiResponse;
      const items = normalizeResults(data);
      setResults(items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24, fontFamily: "ui-sans-serif, system-ui" }}>
      <h1 style={{ margin: 0 }}>Match Runner (MVP)</h1>
      <p style={{ marginTop: 8, opacity: 0.8 }}>
        Charge les fixtures, puis lance le match. On affiche score + 3 raisons max.
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
        <button onClick={handleLoadFixtures} style={{ padding: "10px 14px" }}>
          Charger fixtures
        </button>

        <button
          onClick={handleRunMatch}
          disabled={!canRun || loading}
          style={{ padding: "10px 14px", cursor: !canRun || loading ? "not-allowed" : "pointer" }}
        >
          {loading ? "Match en cours..." : "Lancer le match"}
        </button>
      </div>

      <div style={{ marginTop: 16, fontSize: 14, opacity: 0.85 }}>
        <div>Fixtures profil: {profile ? "✅" : "—"}</div>
        <div>Fixtures offres: {offers ? "✅" : "—"}</div>
      </div>

      {error && (
        <div style={{ marginTop: 16, padding: 12, border: "1px solid #e11d48", borderRadius: 8 }}>
          <strong>Erreur</strong>
          <div style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{error}</div>
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <h2 style={{ marginBottom: 10 }}>Résultats</h2>

        {results && results.length === 0 && (
          <div style={{ padding: 12, border: "1px solid #ddd", borderRadius: 8 }}>
            Aucun match trouvé (résultat vide).
          </div>
        )}

        {results && results.length > 0 && (
          <div style={{ display: "grid", gap: 10 }}>
            {results.slice(0, 50).map((r, idx) => {
              const reasons = Array.isArray(r.reasons) ? r.reasons.slice(0, 3) : [];
              return (
                <div key={r.offer_id ?? idx} style={{ padding: 12, border: "1px solid #ddd", borderRadius: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <div>
                      <strong>Offer</strong>: {r.offer_id ?? "(id manquant)"}
                    </div>
                    <div>
                      <strong>Score</strong>: {formatScore(r.score)}
                    </div>
                  </div>

                  <div style={{ marginTop: 8 }}>
                    <strong>Reasons</strong>
                    {reasons.length === 0 ? (
                      <div style={{ opacity: 0.7, marginTop: 4 }}>—</div>
                    ) : (
                      <ul style={{ marginTop: 6, marginBottom: 0 }}>
                        {reasons.map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!results && (
          <div style={{ padding: 12, border: "1px dashed #bbb", borderRadius: 8, opacity: 0.85 }}>
            Rien à afficher pour l'instant.
          </div>
        )}
      </div>
    </div>
  );
}
