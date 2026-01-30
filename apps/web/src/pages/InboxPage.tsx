import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import Chart from "chart.js/auto";
import {
  Bell,
  Building2,
  Check,
  ChevronDown,
  ChevronRight,
  Filter,
  Gem,
  Heart,
  LayoutDashboard,
  MessageSquare,
  MoreHorizontal,
  Search,
} from "lucide-react";
import { fetchInbox, postDecision } from "../lib/api";
import { listApplications, upsertApplication } from "../api/applications";
import type { InboxItem } from "../lib/api";
import { useProfileStore } from "../store/profileStore";

const STORAGE_PREFIX = "elevia_inbox";
const DEFAULT_THRESHOLD = 65;
const SNAPSHOT_LIMIT = 7;

type DecisionStatus = "SHORTLISTED" | "DISMISSED";

type DecisionRecord = {
  status: DecisionStatus;
  score: number;
  updated_at: string;
};

type ApplicationStatus = "APPLIED" | "RESPONDED";

type ApplicationRecord = {
  status: ApplicationStatus;
  applied_at: string;
  responded_at?: string;
  score?: number;
  title?: string;
  company?: string | null;
  city?: string | null;
  country?: string | null;
  reasons?: string[];
};

type ScoreSnapshot = {
  date: string;
  avgScoreNew: number;
  countNew: number;
};

function storageKey(profileId: string, suffix: string) {
  return `${STORAGE_PREFIX}_${profileId}_${suffix}`;
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value));
}

function average(values: number[]) {
  if (!values.length) return null;
  const sum = values.reduce((acc, v) => acc + v, 0);
  return sum / values.length;
}

function formatPercent(value: number | null) {
  if (value === null || Number.isNaN(value)) return "—";
  return `${Math.round(value)}%`;
}

function formatScore(value: number | null) {
  if (value === null || Number.isNaN(value)) return "—";
  return value.toFixed(1).replace(".0", "");
}

function formatDateLabel(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleDateString("fr-FR", {
    weekday: "short",
    day: "2-digit",
    month: "short",
  });
}

function daysSince(isoDate: string) {
  const start = new Date(isoDate).getTime();
  const now = Date.now();
  return Math.floor((now - start) / (1000 * 60 * 60 * 24));
}

function buildKeywordCounts(items: InboxItem[]) {
  const stopwords = new Set([
    "avec",
    "pour",
    "sans",
    "dans",
    "plus",
    "moins",
    "avec",
    "sur",
    "chez",
    "vous",
    "nous",
    "leur",
    "par",
    "les",
    "des",
    "une",
    "un",
    "the",
    "and",
    "est",
    "pas",
    "non",
    "mais",
    "de",
    "du",
    "la",
    "le",
    "au",
  ]);
  const counts = new Map<string, number>();
  items.forEach((item) => {
    item.reasons.forEach((reason) => {
      reason
        .toLowerCase()
        .split(/[^a-zA-Zà-ÿ0-9]+/)
        .filter((token) => token.length > 2 && !stopwords.has(token))
        .forEach((token) => {
          counts.set(token, (counts.get(token) ?? 0) + 1);
        });
    });
  });
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([label, count]) => ({ label, count }));
}

export default function InboxPage() {
  const { userProfile, profileHash } = useProfileStore();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState<number>(() => {
    const stored = readJson<number>(`${STORAGE_PREFIX}_threshold`, DEFAULT_THRESHOLD);
    return stored || DEFAULT_THRESHOLD;
  });
  const [decisions, setDecisions] = useState<Record<string, DecisionRecord>>({});
  const [applications, setApplications] = useState<Record<string, ApplicationRecord>>({});
  const [applicationStatusMap, setApplicationStatusMap] = useState<Record<string, string>>({});
  const [snapshots, setSnapshots] = useState<ScoreSnapshot[]>([]);

  const lineChartRef = useRef<HTMLCanvasElement | null>(null);
  const doughnutRef = useRef<HTMLCanvasElement | null>(null);
  const lineChartInstance = useRef<Chart | null>(null);
  const doughnutInstance = useRef<Chart | null>(null);

  const profileId = profileHash ?? "anonymous";

  useEffect(() => {
    writeJson(`${STORAGE_PREFIX}_threshold`, threshold);
  }, [threshold]);

  useEffect(() => {
    setDecisions(readJson<Record<string, DecisionRecord>>(storageKey(profileId, "decisions"), {}));
    setApplications(readJson<Record<string, ApplicationRecord>>(storageKey(profileId, "applications"), {}));
    setSnapshots(readJson<ScoreSnapshot[]>(storageKey(profileId, "snapshots"), []));
  }, [profileId]);

  useEffect(() => {
    writeJson(storageKey(profileId, "decisions"), decisions);
  }, [decisions, profileId]);

  useEffect(() => {
    writeJson(storageKey(profileId, "applications"), applications);
  }, [applications, profileId]);

  useEffect(() => {
    writeJson(storageKey(profileId, "snapshots"), snapshots);
  }, [snapshots, profileId]);

  const load = useCallback(async () => {
    if (!userProfile) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInbox(userProfile, profileId, threshold, 60);
      setItems(data.items);

      const newItems = data.items.filter(
        (item) => !decisions[item.offer_id] && applications[item.offer_id]?.status !== "APPLIED"
      );
      const avgNew = average(newItems.map((item) => item.score)) ?? 0;
      const today = new Date().toISOString().slice(0, 10);
      setSnapshots((prev) => {
        const existing = prev.filter((snap) => snap.date !== today);
        const updated = [{ date: today, avgScoreNew: avgNew, countNew: newItems.length }, ...existing];
        return updated.slice(0, SNAPSHOT_LIMIT);
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }, [userProfile, profileId, threshold, decisions, applications]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const fetchTracker = async () => {
      try {
        const data = await listApplications();
        const nextMap: Record<string, string> = {};
        data.items.forEach((item) => {
          nextMap[item.offer_id] = item.status;
        });
        setApplicationStatusMap(nextMap);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur inconnue");
      }
    };
    fetchTracker();
  }, []);

  const handleDecision = (offerId: string, status: DecisionStatus, score: number) => {
    setDecisions((prev) => ({
      ...prev,
      [offerId]: { status, score, updated_at: new Date().toISOString() },
    }));
    postDecision(offerId, profileId, status);
  };

  const handleApply = (item: InboxItem) => {
    setApplications((prev) => ({
      ...prev,
      [item.offer_id]: {
        status: "APPLIED",
        applied_at: new Date().toISOString(),
        score: item.score,
        title: item.title,
        company: item.company,
        city: item.city,
        country: item.country,
        reasons: item.reasons,
      },
    }));
  };

  const handleShortlistTracker = async (offerId: string) => {
    if (applicationStatusMap[offerId]) {
      return;
    }
    try {
      await upsertApplication({
        offer_id: offerId,
        status: "shortlisted",
        note: null,
        next_follow_up_date: null,
      });
      setApplicationStatusMap((prev) => ({ ...prev, [offerId]: "shortlisted" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    }
  };

  const handleResponded = (offerId: string) => {
    setApplications((prev) => {
      const existing = prev[offerId];
      if (!existing) return prev;
      return {
        ...prev,
        [offerId]: {
          ...existing,
          status: "RESPONDED",
          responded_at: new Date().toISOString(),
        },
      };
    });
  };

  const shortlistScores = useMemo(() => {
    return Object.values(decisions)
      .filter((decision) => decision.status === "SHORTLISTED")
      .map((decision) => decision.score);
  }, [decisions]);

  const appliedScores = useMemo(() => {
    return Object.values(applications)
      .filter((record) => record.status === "APPLIED")
      .map((record) => record.score)
      .filter((score): score is number => typeof score === "number");
  }, [applications]);

  const avgShortlist = average(shortlistScores);
  const avgApplied = average(appliedScores);

  const appliedCount = Object.values(applications).filter((record) => record.status === "APPLIED").length;
  const respondedCount = Object.values(applications).filter((record) => record.status === "RESPONDED").length;
  const shortlistCount = Object.values(decisions).filter((decision) => decision.status === "SHORTLISTED").length;

  const actionRate = shortlistCount > 0 ? (appliedCount / shortlistCount) * 100 : null;
  const responseRate = appliedCount > 0 ? (respondedCount / appliedCount) * 100 : null;

  const newItems = useMemo(
    () => items.filter((item) => !decisions[item.offer_id] && !applications[item.offer_id]),
    [items, decisions, applications]
  );

  const avgNew = useMemo(() => average(newItems.map((item) => item.score)), [newItems]);

  const topOffers = useMemo(
    () => [...newItems].sort((a, b) => b.score - a.score).slice(0, 5),
    [newItems]
  );

  const recentForThreshold = newItems.slice(0, 20);
  const aboveThreshold = recentForThreshold.filter((item) => item.score >= threshold).length;
  const thresholdRate =
    recentForThreshold.length > 0 ? (aboveThreshold / recentForThreshold.length) * 100 : null;

  const missingSkills = buildKeywordCounts(newItems);

  const followUps = Object.entries(applications)
    .filter(([, record]) => record.status === "APPLIED" && record.applied_at)
    .map(([offerId, record]) => ({ offerId, ...record }))
    .filter((record) => daysSince(record.applied_at) >= 7)
    .slice(0, 5);

  useEffect(() => {
    if (!lineChartRef.current) return;
    if (lineChartInstance.current) {
      lineChartInstance.current.destroy();
    }

    const labels = [...snapshots].reverse().map((snap) => formatDateLabel(snap.date));
    const dataPoints = [...snapshots].reverse().map((snap) => snap.avgScoreNew);

    lineChartInstance.current = new Chart(lineChartRef.current, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            data: dataPoints,
            borderColor: "#0f172a",
            borderWidth: 1.5,
            backgroundColor: (context) => {
              const ctx = context.chart.ctx;
              const gradient = ctx.createLinearGradient(0, 0, 0, 140);
              gradient.addColorStop(0, "rgba(15, 23, 42, 0.08)");
              gradient.addColorStop(1, "rgba(15, 23, 42, 0)");
              return gradient;
            },
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 4,
            pointHoverBackgroundColor: "#0f172a",
            pointHoverBorderColor: "#fff",
            pointHoverBorderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: true,
            intersect: false,
            mode: "index",
            backgroundColor: "#1e293b",
            padding: 8,
            cornerRadius: 8,
            displayColors: false,
            bodyFont: { family: "'Inter', sans-serif", size: 12 },
            titleFont: { family: "'Inter', sans-serif", size: 12, weight: 500 },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#94a3b8", font: { size: 10, family: "'Inter', sans-serif" } },
            border: { display: false },
          },
          y: { display: false, min: 0, max: 100 },
        },
        interaction: { mode: "nearest", axis: "x", intersect: false },
      },
    });

    return () => {
      lineChartInstance.current?.destroy();
    };
  }, [snapshots]);

  useEffect(() => {
    if (!doughnutRef.current) return;
    if (doughnutInstance.current) {
      doughnutInstance.current.destroy();
    }

    const dataValue = thresholdRate ?? 0;

    doughnutInstance.current = new Chart(doughnutRef.current, {
      type: "doughnut",
      data: {
        labels: ["Au-dessus", "Reste"],
        datasets: [
          {
            data: [dataValue, Math.max(0, 100 - dataValue)],
            backgroundColor: ["#0ea5e9", "#e0f2fe"],
            borderWidth: 0,
            hoverOffset: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "75%",
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { animateScale: true, animateRotate: true },
      },
    });

    return () => {
      doughnutInstance.current?.destroy();
    };
  }, [thresholdRate]);

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

  const todayLabel = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="min-h-screen flex items-center justify-center antialiased lg:p-8 text-slate-800 bg-slate-400 px-4 py-4">
      <div className="overflow-hidden grid grid-cols-12 lg:p-8 bg-slate-50 w-full max-w-screen-2xl rounded-[2.5rem] pt-6 pr-6 pb-6 pl-6 relative shadow-2xl gap-x-8 gap-y-8">
        <div className="absolute inset-0 bg-white/40 pointer-events-none"></div>

        <div className="col-span-12 lg:col-span-9 flex flex-col gap-8 z-10">
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="iconify text-slate-900 w-8 h-8">
                <Gem className="w-8 h-8" />
              </span>
              <span className="text-2xl text-slate-900 font-semibold tracking-tight">Elevia</span>
            </div>

            <nav className="hidden md:flex items-center bg-white shadow-sm border border-slate-100 rounded-full p-1.5 gap-1">
              <button className="flex items-center gap-2 px-5 py-2.5 bg-rose-50 text-rose-600 rounded-full transition-colors group">
                <span className="iconify text-lg group-hover:scale-110 transition-transform">
                  <LayoutDashboard className="w-5 h-5" />
                </span>
                <span className="text-sm font-medium">Cockpit</span>
              </button>
              <button className="flex items-center gap-2 px-5 py-2.5 text-slate-500 hover:bg-slate-50 rounded-full transition-colors group">
                <span className="iconify text-lg group-hover:scale-110 transition-transform">
                  <Building2 className="w-5 h-5" />
                </span>
                <span className="text-sm font-medium">Offres</span>
              </button>
              <Link
                to="/applications"
                className="flex items-center gap-2 px-5 py-2.5 text-slate-500 hover:bg-slate-50 rounded-full transition-colors group"
              >
                <span className="iconify text-lg group-hover:scale-110 transition-transform">
                  <MessageSquare className="w-5 h-5" />
                </span>
                <span className="text-sm font-medium">Candidatures</span>
              </Link>
            </nav>

            <div className="flex items-center gap-4">
              <button className="w-12 h-12 flex items-center justify-center bg-white border border-slate-100 rounded-full text-slate-500 hover:text-slate-800 transition">
                <span className="iconify text-xl">
                  <MessageSquare className="w-5 h-5" />
                </span>
              </button>
              <button className="w-12 h-12 flex items-center justify-center bg-white border border-slate-100 rounded-full text-slate-500 hover:text-slate-800 transition relative">
                <span className="iconify text-xl">
                  <Bell className="w-5 h-5" />
                </span>
                <span className="absolute top-3 right-3.5 w-2 h-2 bg-rose-500 rounded-full border border-white"></span>
              </button>
              <div className="flex gap-3 pl-2 items-center cursor-pointer group">
                <img
                  src="https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?ixlib=rb-1.2.1&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80"
                  alt="Utilisateur"
                  className="w-11 h-11 object-cover ring-white ring-2 rounded-full shadow-sm"
                />
                <div className="hidden xl:block leading-tight">
                  <div className="text-sm font-medium text-slate-900 group-hover:text-rose-600 transition-colors">
                    Akim Guentas
                  </div>
                  <div className="text-xs text-slate-400">inbox@elevia.app</div>
                </div>
                <span className="iconify text-slate-400 hidden xl:block group-hover:text-slate-600 transition-colors">
                  <ChevronDown className="w-4 h-4" />
                </span>
              </div>
            </div>
          </header>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-6">
              <div className="text-slate-400 text-sm font-medium">{todayLabel}</div>
              <div className="h-4 w-px bg-slate-300 hidden sm:block"></div>
              <button className="hidden sm:flex items-center justify-center w-10 h-10 bg-white rounded-full shadow-sm text-slate-500 hover:text-slate-800 hover:shadow-md transition-all">
                <span className="iconify">
                  <Filter className="w-4 h-4" />
                </span>
              </button>

              <div className="relative group">
                <span className="iconify absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 text-lg group-focus-within:text-slate-800 transition-colors">
                  <Search className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  placeholder="Filtrer par ville ou pays"
                  className="pl-11 pr-4 py-3 bg-white rounded-full text-sm font-medium text-slate-700 placeholder-slate-400 shadow-sm border-none focus:ring-2 focus:ring-rose-500/20 outline-none w-64 transition-all"
                />
              </div>
            </div>

            <div className="flex bg-white p-1.5 rounded-full shadow-sm">
              <button
                className={`px-6 py-2 text-sm font-medium rounded-full shadow-sm hover:shadow transition-shadow ${
                  threshold === 65 ? "bg-rose-50 text-rose-600" : "text-slate-400"
                }`}
                onClick={() => setThreshold(65)}
              >
                Seuil 65
              </button>
              <button
                className={`px-6 py-2 text-sm font-medium rounded-full hover:bg-slate-50 transition-colors ${
                  threshold === 75 ? "bg-rose-50 text-rose-600" : "text-slate-400"
                }`}
                onClick={() => setThreshold(75)}
              >
                Seuil 75
              </button>
            </div>
          </div>

          <div className="min-h-[420px] flex flex-col overflow-hidden group bg-gradient-to-br from-slate-500 via-slate-400 to-slate-100 rounded-[2rem] p-8 relative justify-between shadow-inner">
            <div className="z-10 flex gap-12 mt-4 relative">
              <div className="">
                <div className="text-sm font-medium text-slate-100/90 mb-1">Match moyen (Shortlist)</div>
                <div className="text-5xl text-white font-semibold tracking-tight">
                  {avgShortlist === null ? "—" : formatScore(avgShortlist)}
                  {avgShortlist === null ? null : (
                    <span className="text-2xl text-slate-200 ml-1 font-medium">%</span>
                  )}
                </div>
              </div>
              <div className="">
                <div className="text-sm font-medium text-slate-100/90 mb-1">Match moyen (Candidatures)</div>
                <div className="text-5xl text-white font-semibold tracking-tight">
                  {avgApplied === null ? "—" : formatScore(avgApplied)}
                  {avgApplied === null ? null : (
                    <span className="text-2xl text-slate-200 ml-1 font-medium">%</span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap max-w-2xl z-10 mt-auto relative gap-5">
              <div
                className="bg-gradient-to-br from-white/90 to-white/40 w-64 rounded-3xl p-5 shadow-xl backdrop-blur-md"
                style={{
                  position: "relative",
                  "--border-gradient":
                    "linear-gradient(135deg, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.2))",
                  "--border-radius-before": "24px",
                } as CSSProperties}
              >
                <div className="flex items-center gap-2 mb-6 text-emerald-800">
                  <span className="iconify text-xl">
                    <Check className="w-5 h-5" />
                  </span>
                  <span className="text-sm font-medium">Taux d'action</span>
                </div>
                <div className="flex items-end justify-between">
                  <div className="text-3xl text-emerald-900 font-semibold tracking-tight">
                    {formatPercent(actionRate)}
                  </div>
                  <div className="text-emerald-700 text-sm font-medium mb-1.5">
                    {shortlistCount === 0 ? "—" : `${appliedCount}/${shortlistCount}`}
                  </div>
                </div>
                <div className="mt-3 h-1.5 w-full bg-emerald-900/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-600 rounded-full"
                    style={{ width: `${actionRate ?? 0}%` }}
                  ></div>
                </div>
              </div>

              <div
                className="bg-gradient-to-br from-white/90 to-white/40 w-64 rounded-3xl p-5 shadow-xl backdrop-blur-md"
                style={{
                  position: "relative",
                  "--border-gradient":
                    "linear-gradient(135deg, rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.2))",
                  "--border-radius-before": "24px",
                } as CSSProperties}
              >
                <div className="flex items-center gap-2 mb-6 text-sky-800">
                  <span className="iconify text-xl">
                    <ChevronRight className="w-5 h-5" />
                  </span>
                  <span className="text-sm font-medium">Taux de réponse</span>
                </div>
                <div className="flex items-end justify-between">
                  <div className="text-3xl text-sky-900 font-semibold tracking-tight">
                    {formatPercent(responseRate)}
                  </div>
                  <div className="bg-sky-200 px-2 py-0.5 rounded-md text-sky-800 text-xs font-medium mb-1">
                    {appliedCount === 0 ? "—" : `${respondedCount}/${appliedCount}`}
                  </div>
                </div>
                <div className="mt-3 h-1.5 w-full bg-sky-900/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-sky-500 rounded-full"
                    style={{ width: `${responseRate ?? 0}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            <div className="md:col-span-3 bg-white rounded-[2rem] p-6 flex flex-col justify-between shadow-sm border border-slate-100 relative overflow-hidden group">
              <div className="flex items-center gap-2 mb-4 z-10">
                <span className="iconify text-slate-900 w-4 h-4">
                  <Gem className="w-4 h-4" />
                </span>
                <span className="font-medium text-slate-900 text-sm">Compétences manquantes</span>
              </div>

              <div className="flex items-end justify-between gap-1 h-24 mt-2 z-10">
                {[
                  "w-full bg-slate-100 rounded-t-md h-[40%] group-hover:bg-rose-100 transition-colors duration-300",
                  "w-full bg-slate-100 rounded-t-md h-[70%] group-hover:bg-rose-200 transition-colors duration-500",
                  "w-full bg-slate-100 rounded-t-md h-[50%] group-hover:bg-rose-100 transition-colors duration-300",
                  "w-full bg-slate-800 rounded-t-md h-[100%] shadow-lg shadow-slate-200 relative group-hover:-translate-y-1 transition-transform duration-300",
                  "w-full bg-slate-100 rounded-t-md h-[60%] group-hover:bg-rose-100 transition-colors duration-500",
                ].map((className, index) => {
                  const item = missingSkills[index === 3 ? 0 : index];
                  const max = missingSkills[0]?.count ?? 1;
                  const height = item ? Math.max(25, (item.count / max) * 100) : 20;
                  const isPrimary = index === 3;
                  return (
                    <div
                      key={`bar-${index}`}
                      className={className}
                      style={{ height: `${height}%` }}
                    >
                      {isPrimary && item && (
                        <div className="w-full h-full flex items-start justify-center pt-2">
                          <span className="text-[10px] text-white font-medium">{item.count}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 z-10">
                <h3 className="font-medium text-slate-900 leading-tight">
                  {missingSkills[0]?.label ?? "—"}
                </h3>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                  Top 3 mots-clés extraits des raisons ({missingSkills.length}/3)
                </p>
              </div>
            </div>

            <div className="md:col-span-5 flex flex-col bg-white border-slate-100 border rounded-[2rem] p-6 shadow-sm justify-between">
              <div className="flex justify-between items-start mb-6">
                <h3 className="text-lg font-medium text-slate-900 tracking-tight">
                  Tendance du match moyen
                </h3>
              </div>

              <div className="flex items-center gap-6 mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-600 border border-slate-100">
                    <span className="iconify text-xl">
                      <LayoutDashboard className="w-5 h-5" />
                    </span>
                  </div>
                  <div className="">
                    <div className="text-xs text-slate-400 font-medium">Match moyen (NEW)</div>
                    <div className="text-xl font-semibold text-slate-900 tracking-tight">
                      {avgNew === null ? "—" : `${formatScore(avgNew)}%`}
                    </div>
                  </div>
                </div>
                <div className="h-8 w-px bg-slate-100"></div>
                <div className="bg-slate-50 rounded-xl px-3 py-2 border border-slate-100">
                  <div className="text-xs text-slate-400 mb-0.5">Offres analysées</div>
                  <div className="flex items-center gap-1">
                    <span className="text-sm font-semibold text-slate-900">{items.length}</span>
                    <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  </div>
                </div>
              </div>

              <div className="flex gap-4 flex-1 min-h-0">
                <div className="flex-1 flex flex-col min-w-0">
                  <div className="text-xs text-slate-400 font-medium mb-4">Match moyen (7 jours)</div>
                  <div className="flex-1 w-full relative min-h-[140px]">
                    <canvas ref={lineChartRef} style={{ width: "100%", height: "100%" }}></canvas>
                  </div>
                </div>
                <div className="bg-sky-50 rounded-2xl p-3 w-28 flex flex-col justify-between relative overflow-hidden shrink-0">
                  <div className="flex justify-between items-start z-10">
                    <span className="text-xs text-sky-700 font-medium">Offres ≥ seuil</span>
                    <span className="iconify text-sky-400 text-xs">
                      <ChevronRight className="w-3 h-3" />
                    </span>
                  </div>
                  <div className="relative z-10 mt-auto">
                    <div className="text-lg font-semibold text-sky-900 mb-1 tracking-tight">
                      {formatPercent(thresholdRate)}
                    </div>
                    <div className="text-[10px] text-sky-600/70 font-medium leading-tight">
                      seuil {threshold}
                    </div>
                  </div>
                  <div className="absolute -bottom-6 -right-6 w-24 h-24 opacity-80 pointer-events-none">
                    <canvas ref={doughnutRef}></canvas>
                  </div>
                </div>
              </div>
            </div>

            <div className="md:col-span-4 bg-white rounded-[2rem] p-6 shadow-sm border border-slate-100 flex flex-col">
              <div className="flex justify-between items-center mb-5">
                <h3 className="text-lg font-medium text-slate-900 tracking-tight">Relances / À faire</h3>
                <button className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-50 transition text-slate-400">
                  <span className="iconify">
                    <MoreHorizontal className="w-4 h-4" />
                  </span>
                </button>
              </div>

              <div className="flex flex-col gap-5">
                {followUps.length === 0 && (
                  <div className="text-sm text-slate-400">Aucune relance en attente.</div>
                )}
                {followUps.map((followUp) => (
                  <div key={followUp.offerId} className="flex items-start gap-3 group cursor-pointer">
                    <img
                      src={`https://ui-avatars.com/api/?name=${encodeURIComponent(
                        followUp.company || "Elevia"
                      )}&background=E2E8F0&color=475569`}
                      className="w-10 h-10 rounded-full object-cover ring-2 ring-slate-50 group-hover:ring-rose-100 transition-all"
                      alt="avatar"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-baseline">
                        <div className="text-sm font-medium text-slate-900 truncate group-hover:text-rose-600 transition-colors">
                          {followUp.company || "Entreprise"}
                        </div>
                        <div className="w-10 h-5 flex items-center justify-center bg-[#ecfccb] text-[#4d7c0f] text-[10px] font-bold rounded-full">
                          J+{daysSince(followUp.applied_at)}
                        </div>
                      </div>
                      <div className="text-xs text-slate-400 truncate">{followUp.title}</div>
                      <button
                        className="mt-2 text-xs text-rose-500 hover:text-rose-600"
                        onClick={() => handleResponded(followUp.offerId)}
                      >
                        Marquer répondu
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {loading && <div className="text-sm text-slate-400">Chargement…</div>}
          {error && <div className="text-sm text-rose-500">{error}</div>}
        </div>

        <div className="col-span-12 lg:col-span-3 z-10 flex flex-col gap-6 border-t lg:border-t-0 lg:border-l border-slate-200/60 lg:pl-8 pt-8 lg:pt-0">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-slate-900 tracking-tight">Inbox (Top offers)</h2>
            <button className="flex items-center gap-1 text-xs font-medium text-slate-500 bg-white px-3 py-1.5 rounded-full shadow-sm border border-slate-100 hover:bg-slate-50 transition-colors">
              Tri score
              <span className="iconify text-slate-400">
                <ChevronDown className="w-3 h-3" />
              </span>
            </button>
          </div>

          {topOffers.length === 0 && (
            <div className="text-sm text-slate-400">Aucune offre disponible.</div>
          )}

          {topOffers.map((offer) => (
            <div key={offer.offer_id} className="group hover:shadow-lg transition-all bg-white border-slate-100 border rounded-[2rem] p-3 shadow-sm">
              <div className="relative aspect-[4/3] overflow-hidden rounded-3xl mb-4">
                <img
                  src="https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?q=80&w=800&auto=format&fit=crop"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  alt="Offre"
                />
                <button className="absolute top-3 right-3 w-8 h-8 bg-white/90 backdrop-blur text-slate-400 flex items-center justify-center rounded-full hover:text-rose-500 transition-colors shadow-sm">
                  <span className="iconify text-lg">
                    <Heart className="w-4 h-4" />
                  </span>
                </button>
              </div>
              <div className="px-2 pb-2">
                <div className="flex justify-between items-start mb-1">
                  <div className="text-emerald-600 text-sm font-semibold">
                    {offer.score}% <span className="text-slate-400 font-normal text-xs">match</span>
                  </div>
                  <button className="text-slate-400 hover:text-slate-800 transition-colors">
                    <span className="iconify">
                      <MoreHorizontal className="w-4 h-4" />
                    </span>
                  </button>
                </div>
                <h3 className="text-base font-medium text-slate-900 mb-0.5 tracking-tight">
                  {offer.title}
                </h3>
                <div className="text-xs text-slate-400 mb-4">
                  {[offer.company, offer.city, offer.country].filter(Boolean).join(" · ") || "—"}
                </div>
                {offer.rome && (
                  <div className="text-xs text-slate-500 mb-4">
                    <span className="font-medium text-slate-600">ROME:</span> {offer.rome.rome_code} —{" "}
                    {offer.rome.rome_label}
                  </div>
                )}
                {offer.rome_competences && offer.rome_competences.length > 0 && (
                  <div className="mb-4 flex flex-wrap gap-2">
                    {offer.rome_competences.slice(0, 3).map((competence) => (
                      <span
                        key={competence.competence_code}
                        className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500"
                      >
                        {competence.competence_label}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                  <button
                    className={`flex items-center gap-1.5 ${
                      applicationStatusMap[offer.offer_id] ? "text-emerald-600" : "text-slate-500"
                    }`}
                    onClick={() => handleShortlistTracker(offer.offer_id)}
                    disabled={Boolean(applicationStatusMap[offer.offer_id])}
                  >
                    <span className="text-xs font-medium">
                      {applicationStatusMap[offer.offer_id] === "shortlisted"
                        ? "Shortlisted"
                        : applicationStatusMap[offer.offer_id]
                          ? applicationStatusMap[offer.offer_id]
                          : "Shortlist"}
                    </span>
                  </button>
                  <button
                    className="flex items-center gap-1.5 text-slate-500"
                    onClick={() => handleDecision(offer.offer_id, "DISMISSED", offer.score)}
                  >
                    <span className="text-xs font-medium">Dismiss</span>
                  </button>
                  <button
                    className="flex items-center gap-1.5 text-slate-500"
                    onClick={() => handleApply(offer)}
                  >
                    <span className="text-xs font-medium">Apply</span>
                  </button>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {offer.reasons.slice(0, 3).map((reason) => (
                    <span
                      key={reason}
                      className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500"
                    >
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
