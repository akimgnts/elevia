import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlarmClock,
  CalendarClock,
  CheckCircle2,
  Filter,
  Search,
  Trash2,
} from "lucide-react";
import type { ApplicationItem, ApplicationStatus } from "../api/applications";
import { deleteApplication, listApplications, patchApplication } from "../api/applications";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { EmptyState } from "../components/ui/EmptyState";

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  shortlisted: "A prioriser",
  applied: "Envoyees",
  dismissed: "Ecartees",
};

const STATUS_STYLES: Record<ApplicationStatus, string> = {
  shortlisted: "bg-sky-50 text-sky-700 border-sky-200",
  applied: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dismissed: "bg-slate-100 text-slate-600 border-slate-200",
};

type FilterStatus = "all" | ApplicationStatus;

function toDateLabel(value: string | null): string {
  if (!value) return "Aucune date";
  try {
    return new Date(`${value}T00:00:00`).toLocaleDateString();
  } catch {
    return value;
  }
}

function daysUntil(value: string | null): number | null {
  if (!value) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${value}T00:00:00`);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

function followUpTone(value: string | null): {
  label: string;
  className: string;
} {
  const delta = daysUntil(value);
  if (delta === null) {
    return {
      label: "Pas de relance planifiee",
      className: "bg-slate-100 text-slate-600 border-slate-200",
    };
  }
  if (delta < 0) {
    return {
      label: `Relance en retard de ${Math.abs(delta)} j`,
      className: "bg-rose-50 text-rose-700 border-rose-200",
    };
  }
  if (delta === 0) {
    return {
      label: "Relance aujourd'hui",
      className: "bg-amber-50 text-amber-700 border-amber-200",
    };
  }
  if (delta <= 3) {
    return {
      label: `Relance dans ${delta} j`,
      className: "bg-cyan-50 text-cyan-700 border-cyan-200",
    };
  }
  return {
    label: `Relance dans ${delta} j`,
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
}

export default function ApplicationsPage() {
  const [items, setItems] = useState<ApplicationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noteDrafts, setNoteDrafts] = useState<Record<string, string>>({});
  const [dateDrafts, setDateDrafts] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");

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

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesStatus = statusFilter === "all" || item.status === statusFilter;
      const matchesSearch =
        search.trim() === "" ||
        item.offer_id.toLowerCase().includes(search.trim().toLowerCase()) ||
        (item.note ?? "").toLowerCase().includes(search.trim().toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [items, search, statusFilter]);

  const grouped = useMemo(() => {
    return {
      shortlisted: filteredItems.filter((item) => item.status === "shortlisted"),
      applied: filteredItems.filter((item) => item.status === "applied"),
      dismissed: filteredItems.filter((item) => item.status === "dismissed"),
    };
  }, [filteredItems]);

  const stats = useMemo(() => {
    const total = items.length;
    const followUpsPlanned = items.filter((item) => item.next_follow_up_date).length;
    const dueSoon = items.filter((item) => {
      const delta = daysUntil(item.next_follow_up_date);
      return delta !== null && delta >= 0 && delta <= 3;
    }).length;
    const overdue = items.filter((item) => {
      const delta = daysUntil(item.next_follow_up_date);
      return delta !== null && delta < 0;
    }).length;
    return { total, followUpsPlanned, dueSoon, overdue };
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

  const renderColumn = (status: ApplicationStatus) => (
    <section
      key={status}
      className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{STATUS_LABELS[status]}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {grouped[status].length} element{grouped[status].length > 1 ? "s" : ""}
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${STATUS_STYLES[status]}`}>
          {STATUS_LABELS[status]}
        </span>
      </div>

      {grouped[status].length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-400">
          Aucun element dans cette colonne.
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          {grouped[status].map((item) => {
            const followUp = followUpTone(item.next_follow_up_date);
            return (
              <article
                key={item.id}
                className="rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      Offer ID
                    </div>
                    <div className="mt-1 break-all text-sm font-semibold text-slate-950">{item.offer_id}</div>
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${followUp.className}`}>
                    {followUp.label}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 text-xs text-slate-500 sm:grid-cols-2">
                  <div>
                    Creee le
                    <div className="mt-1 text-sm text-slate-700">{new Date(item.created_at).toLocaleString()}</div>
                  </div>
                  <div>
                    Mise a jour
                    <div className="mt-1 text-sm text-slate-700">{new Date(item.updated_at).toLocaleString()}</div>
                  </div>
                </div>

                <div className="mt-4 grid gap-3">
                  <div className="grid gap-3 md:grid-cols-[180px_minmax(0,1fr)_180px]">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">Statut</label>
                      <select
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                        value={item.status}
                        onChange={(event) =>
                          handleStatusChange(item.offer_id, event.target.value as ApplicationStatus)
                        }
                      >
                        <option value="shortlisted">A prioriser</option>
                        <option value="applied">Envoyee</option>
                        <option value="dismissed">Ecartee</option>
                      </select>
                    </div>

                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">Note</label>
                      <input
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                        value={noteDrafts[item.offer_id] ?? ""}
                        onChange={(event) =>
                          setNoteDrafts((prev) => ({ ...prev, [item.offer_id]: event.target.value }))
                        }
                        placeholder="Ex: relancer avec CV adapte ou attente reponse RH"
                      />
                    </div>

                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">Relance</label>
                      <input
                        type="date"
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                        value={dateDrafts[item.offer_id] ?? ""}
                        onChange={(event) =>
                          setDateDrafts((prev) => ({ ...prev, [item.offer_id]: event.target.value }))
                        }
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <div className="rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                      Prochaine relance: {toDateLabel(item.next_follow_up_date)}
                    </div>
                    <button
                      className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                      onClick={() => handleSave(item.offer_id)}
                    >
                      Enregistrer
                    </button>
                    <button
                      className="inline-flex items-center gap-1 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 transition hover:bg-rose-100"
                      onClick={() => handleDelete(item.offer_id)}
                    >
                      <Trash2 className="h-4 w-4" />
                      Supprimer
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );

  return (
    <PremiumAppShell
      eyebrow="Suivi"
      title="Suivi des candidatures"
      description="Cette page sert de memoire externe. Elle garde une trace de ce qui a ete shortlist e, envoye, relance ou ecarte, pour t'aider a ne rien laisser retomber."
      actions={
        <>
          <Link
            to="/inbox"
            className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Retour inbox
          </Link>
          <Link
            to="/dashboard"
            className="rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
          >
            Ouvrir le cockpit
          </Link>
        </>
      }
      contentClassName="max-w-7xl"
    >
      <div className="grid gap-6">
        <section className="grid gap-4 lg:grid-cols-4">
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Total</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{stats.total}</div>
            <div className="mt-2 text-sm text-slate-500">candidature{stats.total > 1 ? "s" : ""} suivie{stats.total > 1 ? "s" : ""}</div>
          </div>
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Relances planifiees</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{stats.followUpsPlanned}</div>
            <div className="mt-2 text-sm text-slate-500">dates deja posees</div>
          </div>
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">A relancer bientot</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{stats.dueSoon}</div>
            <div className="mt-2 text-sm text-slate-500">dans les 3 prochains jours</div>
          </div>
          <div className="rounded-[1.5rem] border border-white/80 bg-white/80 p-5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">En retard</div>
            <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{stats.overdue}</div>
            <div className="mt-2 text-sm text-slate-500">relance{stats.overdue > 1 ? "s" : ""} depassee{stats.overdue > 1 ? "s" : ""}</div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <div className="rounded-[1.75rem] border border-white/80 bg-white/80 p-4 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <div className="relative min-w-0 flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    type="search"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Rechercher par offer_id ou note..."
                    className="w-full rounded-xl border border-slate-200 bg-white px-10 py-2.5 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
                    <Filter className="h-4 w-4" />
                    Statut
                  </div>
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value as FilterStatus)}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                  >
                    <option value="all">Tous</option>
                    <option value="shortlisted">A prioriser</option>
                    <option value="applied">Envoyees</option>
                    <option value="dismissed">Ecartees</option>
                  </select>
                </div>
              </div>
            </div>

            {loading && (
              <div className="rounded-[1.75rem] border border-white/80 bg-white/80 px-6 py-8 text-sm text-slate-500 shadow-sm">
                Chargement des candidatures...
              </div>
            )}

            {error && (
              <div className="rounded-[1.75rem] border border-rose-200 bg-rose-50 px-6 py-5 text-sm text-rose-700 shadow-sm">
                {error}
              </div>
            )}

            {!loading && !error && items.length === 0 && (
              <div className="space-y-4">
                <EmptyState
                  title="Aucune candidature suivie"
                  description="Shortliste ou envoie une offre depuis l'inbox pour commencer ton suivi ici."
                />
                <div className="flex justify-center">
                  <Link
                    to="/inbox"
                    className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    Aller a l&apos;inbox
                  </Link>
                </div>
              </div>
            )}

            {!loading && !error && items.length > 0 && (
              <div className="grid gap-6 xl:grid-cols-3">
                {renderColumn("shortlisted")}
                {renderColumn("applied")}
                {renderColumn("dismissed")}
              </div>
            )}
          </div>

          <aside className="space-y-6">
            <section className="rounded-[1.75rem] border border-white/80 bg-white/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.08)] backdrop-blur">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Rituels de suivi</div>
              <div className="mt-4 space-y-3 text-sm text-slate-600">
                <div className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4">
                  <CalendarClock className="mt-0.5 h-4 w-4 text-cyan-600" />
                  <div>Pose une date de relance au moment ou tu passes une offre en envoyee.</div>
                </div>
                <div className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4">
                  <AlarmClock className="mt-0.5 h-4 w-4 text-amber-600" />
                  <div>Utilise la colonne “A prioriser” comme zone de preparation avant envoi.</div>
                </div>
                <div className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                  <div>Archive en “Ecartee” les offres qui ne meritent plus d&apos;energie mentale.</div>
                </div>
              </div>
            </section>
          </aside>
        </section>
      </div>
    </PremiumAppShell>
  );
}
