import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { fetchInbox, postDecision } from "../lib/api";
import { listApplications, upsertApplication } from "../api/applications";
import type { InboxItem } from "../lib/api";
import type { ApplicationItem } from "../api/applications";
import { useProfileStore } from "../store/profileStore";
import { OfferCard } from "../components/ui/OfferCard";

export default function CockpitPage() {
  const { userProfile, profileHash } = useProfileStore();
  const profileId = profileHash ?? "anonymous";

  const [items, setItems] = useState<InboxItem[]>([]);
  const [trackerItems, setTrackerItems] = useState<ApplicationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!userProfile) return;
    setLoading(true);
    setError(null);
    try {
      const [inbox, tracker] = await Promise.all([
        fetchInbox(userProfile, profileId, 65, 40),
        listApplications(),
      ]);
      setItems(inbox.items);
      setTrackerItems(tracker.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }, [userProfile, profileId]);

  useEffect(() => {
    load();
  }, [load]);

  const trackerMap = useMemo(() => {
    const map: Record<string, string> = {};
    trackerItems.forEach((item) => {
      map[item.offer_id] = item.status;
    });
    return map;
  }, [trackerItems]);

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        (item.company ?? "").toLowerCase().includes(q) ||
        (item.city ?? "").toLowerCase().includes(q) ||
        (item.country ?? "").toLowerCase().includes(q)
    );
  }, [items, search]);

  const handleShortlist = async (offerId: string) => {
    if (trackerMap[offerId]) return;
    try {
      await upsertApplication({
        offer_id: offerId,
        status: "saved",
        note: null,
        next_follow_up_date: null,
      });
      await postDecision(offerId, profileId, "SHORTLISTED");
      setTrackerItems((prev) => [
        {
          id: "",
          user_id: null,
          offer_id: offerId,
          offer_title: null,
          offer_company: null,
          offer_city: null,
          offer_country: null,
          status: "saved",
          source: "manual",
          note: null,
          next_follow_up_date: null,
          current_cv_cache_key: null,
          current_letter_cache_key: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          applied_at: null,
          last_status_change_at: null,
          strategy_hint: null,
        },
        ...prev,
      ]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    }
  };

  const handleDismiss = async (offerId: string) => {
    await postDecision(offerId, profileId, "DISMISSED");
    setItems((prev) => prev.filter((item) => item.offer_id !== offerId));
  };

  if (!userProfile) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-gray-50">
        <p className="text-gray-600">Aucun profil chargé.</p>
        <Link to="/analyze" className="text-blue-600 underline">
          Analyser un CV
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-screen-2xl mx-auto px-6 py-10 space-y-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Cockpit</h1>
            <p className="text-sm text-slate-500">
              Vue unifiée de vos offres et candidatures.
            </p>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Filtrer par titre, ville, entreprise…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-white rounded-full text-sm text-slate-700 placeholder-slate-400 shadow-sm border border-slate-200 focus:ring-2 focus:ring-slate-300 outline-none w-72"
            />
          </div>
        </header>

        {loading && <div className="text-sm text-slate-400">Chargement…</div>}
        {error && <div className="text-sm text-rose-500">{error}</div>}

        {!loading && !error && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left: compact list */}
            <div className="lg:col-span-4 space-y-3">
              <h2 className="text-lg font-medium text-slate-900">
                Candidatures ({trackerItems.length})
              </h2>
              {trackerItems.length === 0 && (
                <div className="text-sm text-slate-400">Aucune candidature.</div>
              )}
              {trackerItems.map((app) => (
                <div
                  key={app.id || app.offer_id}
                  className="bg-white border border-slate-100 rounded-xl p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-slate-900 truncate">
                      {app.offer_id}
                    </span>
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                        app.status === "saved"
                          ? "bg-emerald-50 text-emerald-700"
                          : app.status === "applied"
                            ? "bg-blue-50 text-blue-700"
                            : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {app.status}
                    </span>
                  </div>
                  {app.note && (
                    <div className="mt-1 text-xs text-slate-500 truncate">{app.note}</div>
                  )}
                  {app.next_follow_up_date && (
                    <div className="mt-1 text-xs text-slate-400">
                      Relance: {app.next_follow_up_date}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Right: 2-col offer grid */}
            <div className="lg:col-span-8 space-y-3">
              <h2 className="text-lg font-medium text-slate-900">
                Offres inbox ({filtered.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filtered.map((offer) => (
                  <div key={offer.offer_id} className="flex flex-col">
                    <OfferCard
                      title={offer.title}
                      company={offer.company ?? "—"}
                      location={[offer.city, offer.country].filter(Boolean).join(", ") || "—"}
                      preview={offer.reasons.slice(0, 2).join(" · ")}
                      score={offer.score}
                      tags={
                        offer.rome
                          ? [`${offer.rome.rome_code} ${offer.rome.rome_label}`]
                          : []
                      }
                    />
                    <div className="flex items-center gap-2 mt-2 px-1">
                      {trackerMap[offer.offer_id] ? (
                        <span className="text-xs font-medium text-emerald-600">
                          {trackerMap[offer.offer_id]}
                        </span>
                      ) : (
                        <button
                          className="text-xs font-medium text-slate-600 hover:text-emerald-600 transition-colors"
                          onClick={() => handleShortlist(offer.offer_id)}
                        >
                          Shortlist
                        </button>
                      )}
                      <span className="text-slate-200">|</span>
                      <button
                        className="text-xs font-medium text-slate-400 hover:text-rose-500 transition-colors"
                        onClick={() => handleDismiss(offer.offer_id)}
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
