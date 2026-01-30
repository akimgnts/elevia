import { useEffect, useMemo, useState } from "react";
import type { ApplicationItem, ApplicationStatus } from "../api/applications";
import { deleteApplication, listApplications, patchApplication } from "../api/applications";

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  shortlisted: "Shortlisted",
  applied: "Applied",
  dismissed: "Dismissed",
};

export default function ApplicationsPage() {
  const [items, setItems] = useState<ApplicationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [dateDrafts, setDateDrafts] = useState<Record<string, string>>({});

  const refresh = async () => {
    try {
      setLoading(true);
      const data = await listApplications();
      setItems(data.items);
      setError(null);
      const nextNotes: Record<string, string> = {};
      const nextDates: Record<string, string> = {};
      data.items.forEach((item) => {
        if (item.note) nextNotes[item.offer_id] = item.note;
        if (item.next_follow_up_date) nextDates[item.offer_id] = item.next_follow_up_date;
      });
      setNoteDrafts(nextNotes);
      setDateDrafts(nextDates);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const grouped = useMemo(() => {
    return {
      shortlisted: items.filter((item) => item.status === "shortlisted"),
      applied: items.filter((item) => item.status === "applied"),
      dismissed: items.filter((item) => item.status === "dismissed"),
    };
  }, [items]);

  const handleStatusChange = async (offerId: string, status: ApplicationStatus) => {
    await patchApplication(offerId, { status });
    await refresh();
  };

  const handleSave = async (offerId: string) => {
    await patchApplication(offerId, {
      note: (noteDrafts[offerId] ?? "").trim(),
      next_follow_up_date: dateDrafts[offerId] ? dateDrafts[offerId] : null,
    });
    await refresh();
  };

  const handleDelete = async (offerId: string) => {
    if (!window.confirm("Supprimer cette candidature ?")) return;
    await deleteApplication(offerId);
    await refresh();
  };

  const renderSection = (status: ApplicationStatus) => (
    <section key={status} className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">{STATUS_LABELS[status]}</h2>
      {grouped[status].length === 0 && (
        <div className="text-sm text-slate-400">Aucun élément.</div>
      )}
      <div className="grid gap-4">
        {grouped[status].map((item) => (
          <div key={item.id} className="bg-white border border-slate-100 rounded-2xl p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-xs text-slate-400">Offer ID</div>
                <div className="text-sm font-medium text-slate-900">{item.offer_id}</div>
              </div>
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-slate-100 text-slate-600">
                {STATUS_LABELS[item.status]}
              </span>
            </div>

            {item.note && (
              <div className="mt-3 text-sm text-slate-600">{item.note}</div>
            )}
            {item.next_follow_up_date && (
              <div className="mt-2 text-xs text-slate-500">
                Prochaine relance: {item.next_follow_up_date}
              </div>
            )}

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-slate-500">Statut</label>
                <select
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                  value={item.status}
                  onChange={(event) =>
                    handleStatusChange(item.offer_id, event.target.value as ApplicationStatus)
                  }
                >
                  <option value="shortlisted">Shortlisted</option>
                  <option value="applied">Applied</option>
                  <option value="dismissed">Dismissed</option>
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-slate-500">Note</label>
                <input
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                  value={noteDrafts[item.offer_id] ?? ""}
                  onChange={(event) =>
                    setNoteDrafts((prev) => ({ ...prev, [item.offer_id]: event.target.value }))
                  }
                  placeholder="Note"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-slate-500">Relance</label>
                <input
                  type="date"
                  className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
                  value={dateDrafts[item.offer_id] ?? ""}
                  onChange={(event) =>
                    setDateDrafts((prev) => ({ ...prev, [item.offer_id]: event.target.value }))
                  }
                />
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-sm"
                onClick={() => handleSave(item.offer_id)}
              >
                Enregistrer
              </button>
              <button
                className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-sm"
                onClick={() => handleDelete(item.offer_id)}
              >
                Supprimer
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        <header>
          <h1 className="text-2xl font-semibold text-slate-900">Candidatures</h1>
          <p className="text-sm text-slate-500">
            Mémoire externe minimale pour suivre tes décisions et relances.
          </p>
        </header>

        {loading && <div className="text-sm text-slate-400">Chargement…</div>}
        {error && <div className="text-sm text-rose-500">{error}</div>}

        {!loading && !error && (
          <div className="space-y-10">
            {renderSection("shortlisted")}
            {renderSection("applied")}
            {renderSection("dismissed")}
          </div>
        )}
      </div>
    </div>
  );
}
