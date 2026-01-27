import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { runMatch } from "../services/match.service";
import { useProfileStore } from "../store/profileStore";
import type { MatchItem, MatchResponse } from "../types/match";

/* ======================
   Helpers
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
   Diagnostic helpers
====================== */

function isKoLangue(item: MatchItem): boolean {
  return item.diagnostic?.languages?.status === "KO";
}

function isKoGlobal(item: MatchItem): boolean {
  return item.diagnostic?.global_verdict === "KO";
}

/**
 * Tri composite des offres (Sprint 11)
 *
 * Règle stricte:
 * 1. Offres SANS KO Langue → triées par score décroissant
 * 2. Offres AVEC KO Langue → toujours après, triées par score décroissant
 *
 * Le score ne peut jamais compenser un KO Langue.
 */
function sortByProductRules(results: MatchItem[]): MatchItem[] {
  const okLangue = results.filter((r) => !isKoLangue(r));
  const koLangue = results.filter((r) => isKoLangue(r));

  // Tri par score décroissant dans chaque groupe
  okLangue.sort((a, b) => b.score - a.score);
  koLangue.sort((a, b) => b.score - a.score);

  // OK Langue en premier, KO Langue ensuite
  return [...okLangue, ...koLangue];
}

/* ======================
   Page
====================== */

export default function MatchPage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<unknown>(null);
  const [offers, setOffers] = useState<unknown[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<MatchResponse | null>(null);

  // Modal warning KO Langue
  const [warningModal, setWarningModal] = useState<{
    visible: boolean;
    offerId: string | null;
    offerTitle: string;
  }>({ visible: false, offerId: null, offerTitle: "" });

  const canRun = useMemo(
    () => Boolean(profile && offers.length > 0),
    [profile, offers]
  );

  // Tri composite: OK Langue > KO Langue, puis par score
  const sortedResults = useMemo(() => {
    if (!response) return null;
    return sortByProductRules(response.results);
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

  function handlePostuler(item: MatchItem, offerTitle: string) {
    if (isKoLangue(item)) {
      // Afficher warning modal
      setWarningModal({
        visible: true,
        offerId: item.offer_id,
        offerTitle,
      });
    } else {
      // Comportement normal
      alert(`Candidature envoyée pour: ${offerTitle}`);
    }
  }

  function handleConfirmPostuler() {
    alert(`Candidature envoyée pour: ${warningModal.offerTitle}`);
    setWarningModal({ visible: false, offerId: null, offerTitle: "" });
  }

  function handleCancelPostuler() {
    setWarningModal({ visible: false, offerId: null, offerTitle: "" });
  }

  /* ======================
     Render
  ====================== */

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Match Runner</h1>

      <p style={{ opacity: 0.8 }}>
        Charge les fixtures, puis lance le match.
      </p>

      <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
        <button onClick={handleLoadFixtures}>Charger fixtures</button>
        <button onClick={handleRunMatch} disabled={!canRun || loading}>
          {loading ? "Match en cours…" : "Lancer le match"}
        </button>
        {profile !== null && (
          <button
            onClick={async () => {
              await useProfileStore.getState().setIngestResult(profile);
              navigate("/profile");
            }}
            style={{ backgroundColor: "#2563eb", color: "white" }}
          >
            Sauver profil
          </button>
        )}
        <Link to="/dashboard" style={{ padding: "8px 12px", textDecoration: "none" }}>
          Dashboard →
        </Link>
      </div>

      <div style={{ marginTop: 16 }}>
        <div>Fixtures profil: {profile ? "✅" : "—"}</div>
        <div>
          Fixtures offres: {offers.length > 0 ? `✅ (${offers.length})` : "—"}
        </div>
      </div>

      {error && (
        <div style={{ marginTop: 16, color: "#e11d48" }}>{error}</div>
      )}

      {response && (
        <div
          style={{
            marginTop: 16,
            padding: 10,
            backgroundColor: "#f0fdf4",
            border: "1px solid #bbf7d0",
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          <strong>Résumé API:</strong> received_offers=
          {response.received_offers}, results={response.results.length}
        </div>
      )}

      {sortedResults && sortedResults.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h2>Résultats ({sortedResults.length} offres)</h2>

          <div style={{ display: "grid", gap: 12 }}>
            {sortedResults.map((r: MatchItem, i: number) => {
              const offer = offersMap.get(r.offer_id);
              const title = formatValue(getField(offer, "title"));
              const koLangue = isKoLangue(r);
              const koGlobal = isKoGlobal(r);

              return (
                <div
                  key={r.offer_id ?? i}
                  style={{
                    padding: 12,
                    border: koLangue
                      ? "2px solid #fbbf24"
                      : "1px solid #ddd",
                    backgroundColor: koLangue ? "#fffbeb" : "white",
                    borderRadius: 6,
                  }}
                >
                  {/* Header: Titre + Score + Badges */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <strong>{title}</strong>

                      {/* Badge KO Global */}
                      {koGlobal && (
                        <span
                          style={{
                            backgroundColor: "#dc2626",
                            color: "white",
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          Bloquant
                        </span>
                      )}

                      {/* Badge KO Langue (si pas déjà KO global) */}
                      {koLangue && !koGlobal && (
                        <span
                          style={{
                            backgroundColor: "#f59e0b",
                            color: "white",
                            padding: "2px 8px",
                            borderRadius: 4,
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          Langue manquante
                        </span>
                      )}
                    </div>

                    <strong>{formatScore(r.score)}</strong>
                  </div>

                  {/* Infos entreprise / pays */}
                  <div style={{ fontSize: 13, opacity: 0.8, marginTop: 4 }}>
                    {formatValue(getField(offer, "company"))} —{" "}
                    {formatValue(getField(offer, "country"))}
                  </div>

                  {/* Raisons bloquantes (si KO) */}
                  {r.diagnostic?.top_blocking_reasons &&
                    r.diagnostic.top_blocking_reasons.length > 0 && (
                      <div
                        style={{
                          marginTop: 8,
                          padding: 8,
                          backgroundColor: koGlobal ? "#fef2f2" : "#fefce8",
                          borderRadius: 4,
                          fontSize: 13,
                        }}
                      >
                        <strong>Points d'attention :</strong>
                        <ul style={{ margin: "4px 0 0 0", paddingLeft: 20 }}>
                          {r.diagnostic.top_blocking_reasons
                            .slice(0, 3)
                            .map((reason, idx) => (
                              <li key={idx}>{reason}</li>
                            ))}
                        </ul>
                      </div>
                    )}

                  {/* Raisons positives */}
                  {r.reasons && r.reasons.length > 0 && !koGlobal && (
                    <ul style={{ marginTop: 8 }}>
                      {r.reasons.slice(0, 3).map((x, idx) => (
                        <li key={idx} style={{ fontSize: 13 }}>
                          {x}
                        </li>
                      ))}
                    </ul>
                  )}

                  {/* Bouton Postuler */}
                  <div style={{ marginTop: 12 }}>
                    <button
                      onClick={() => handlePostuler(r, title)}
                      style={{
                        padding: "8px 16px",
                        backgroundColor: koLangue ? "#f59e0b" : "#2563eb",
                        color: "white",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                        fontWeight: 500,
                      }}
                    >
                      {koLangue ? "Postuler (langue manquante)" : "Postuler"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {sortedResults && sortedResults.length === 0 && (
        <div style={{ marginTop: 24 }}>Aucune offre disponible.</div>
      )}

      {/* Modal Warning KO Langue */}
      {warningModal.visible && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "white",
              padding: 24,
              borderRadius: 8,
              maxWidth: 400,
              boxShadow: "0 4px 20px rgba(0,0,0,0.2)",
            }}
          >
            <h3 style={{ marginTop: 0, color: "#d97706" }}>
              Langue non maîtrisée
            </h3>
            <p>
              Cette offre requiert une langue non maîtrisée selon votre profil.
            </p>
            <p style={{ fontSize: 14, opacity: 0.8 }}>
              Souhaitez-vous continuer malgré tout ?
            </p>
            <div
              style={{
                display: "flex",
                gap: 12,
                marginTop: 16,
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={handleCancelPostuler}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#e5e7eb",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                }}
              >
                Voir des offres adaptées
              </button>
              <button
                onClick={handleConfirmPostuler}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#f59e0b",
                  color: "white",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                  fontWeight: 500,
                }}
              >
                Continuer quand même
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
