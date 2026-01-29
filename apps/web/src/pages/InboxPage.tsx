import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchInbox, postDecision } from "../lib/api";
import type { InboxItem } from "../lib/api";
import { useProfileStore } from "../store/profileStore";

function scoreBadge(score: number) {
  const bg =
    score >= 85 ? "bg-green-100 text-green-800" :
    score >= 70 ? "bg-yellow-100 text-yellow-800" :
    "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${bg}`}>
      {score}%
    </span>
  );
}

export default function InboxPage() {
  const { userProfile, profileHash } = useProfileStore();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generateModalOfferId, setGenerateModalOfferId] = useState<string | null>(null);

  const profileId = profileHash ?? "anonymous";

  const load = useCallback(async () => {
    if (!userProfile) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInbox(userProfile, profileId, 65, 20);
      setItems(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }, [userProfile, profileId]);

  useEffect(() => { load(); }, [load]);

  const handleDecision = (offerId: string, status: "SHORTLISTED" | "DISMISSED") => {
    setItems((prev) => prev.filter((i) => i.offer_id !== offerId));
    postDecision(offerId, profileId, status);
  };

  const handleGenerate = (offerId: string) => {
    setGenerateModalOfferId(offerId);
    console.log("[inbox] Generate clicked for", offerId);
  };

  if (!userProfile) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-gray-50">
        <p className="text-gray-600">Aucun profil charg&eacute;.</p>
        <Link to="/analyze" className="text-blue-600 underline">
          Analyser un CV
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Inbox</h1>
          <Link to="/dashboard" className="text-sm text-blue-600 underline">
            Dashboard
          </Link>
        </div>

        {loading && <p className="text-gray-500">Chargement&hellip;</p>}
        {error && <p className="text-red-600">{error}</p>}

        {!loading && items.length === 0 && !error && (
          <p className="text-gray-500">Aucune offre correspond &agrave; votre profil.</p>
        )}

        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.offer_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <h2 className="font-semibold text-gray-900 truncate">{item.title}</h2>
                  <p className="text-sm text-gray-500">
                    {[item.company, item.city, item.country].filter(Boolean).join(" \u2022 ")}
                  </p>
                </div>
                {scoreBadge(item.score)}
              </div>

              {item.reasons.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-sm text-gray-700">
                  {item.reasons.map((r, i) => (
                    <li key={i} className="flex gap-1">
                      <span className="text-gray-400">&bull;</span>
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              )}

              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => handleDecision(item.offer_id, "SHORTLISTED")}
                  className="px-3 py-1 text-sm rounded bg-green-600 text-white hover:bg-green-700"
                >
                  Shortlist
                </button>
                <button
                  onClick={() => handleDecision(item.offer_id, "DISMISSED")}
                  className="px-3 py-1 text-sm rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
                >
                  Dismiss
                </button>
                <button
                  onClick={() => handleGenerate(item.offer_id)}
                  className="px-3 py-1 text-sm rounded border border-blue-600 text-blue-600 hover:bg-blue-50"
                >
                  G&eacute;n&eacute;rer
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Generate modal */}
      {generateModalOfferId && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 m-4">
            <h3 className="text-lg font-semibold mb-2">G&eacute;n&eacute;rer un document</h3>
            <p className="text-sm text-gray-500 mb-4">
              Offre : {generateModalOfferId}
            </p>
            <div className="space-y-2">
              <button
                onClick={() => {
                  console.log("[inbox] Copy cover letter for", generateModalOfferId);
                  setGenerateModalOfferId(null);
                }}
                className="w-full px-3 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700"
              >
                Copier la lettre de motivation
              </button>
              <button
                onClick={() => {
                  console.log("[inbox] Copy email for", generateModalOfferId);
                  setGenerateModalOfferId(null);
                }}
                className="w-full px-3 py-2 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                Copier l&apos;email de candidature
              </button>
            </div>
            <button
              onClick={() => setGenerateModalOfferId(null)}
              className="mt-4 w-full text-sm text-gray-500 hover:text-gray-700"
            >
              Fermer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
