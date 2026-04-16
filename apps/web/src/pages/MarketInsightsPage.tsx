import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Briefcase,
  Building2,
  ChevronDown,
  Globe,
  MapPin,
  Printer,
  Target,
  TrendingUp,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { ComposableMap, Geographies, Geography, ZoomableGroup } from "react-simple-maps";
import geoUrl from "world-atlas/countries-110m.json?url";
import {
  fetchMarketInsights,
  type MarketInsightsRole,
  type MarketInsightsResponse,
} from "../lib/api";
import { PremiumAppShell } from "../components/layout/PremiumAppShell";
import { TopRolesCard } from "../components/market-insights/TopRolesCard";

const SECTOR_LABELS: Record<string, string> = {
  DATA_IT: "Data / IT",
  FINANCE_LEGAL: "Finance & Légal",
  SUPPLY_OPS: "Supply & Ops",
  MARKETING_SALES: "Marketing & Sales",
  ENGINEERING_INDUSTRY: "Ingénierie",
  ADMIN_HR: "RH & Admin",
  OTHER: "Autres",
};

const GEO_URL = geoUrl;

const SKILL_DISPLAY: Record<string, string> = {
  "gestion de projets": "Gestion de projets",
  "développement par itérations": "Dev. itératif",
  "gestion de projets par méthode agile": "Méthode Agile",
  "amélioration des processus d'affaires": "Process improvement",
  logistique: "Logistique",
  devops: "DevOps",
  "circuits intégrés": "Circuits intégrés",
  sql: "SQL",
  "analyse de données": "Analyse de données",
  finance: "Finance",
  marketing: "Marketing",
  "supply chain": "Supply Chain",
  python: "Python",
  "power bi": "Power BI",
  tableau: "Tableau",
  comptabilité: "Comptabilité",
  vente: "Vente",
  audit: "Audit",
  "planification des ressources d'entreprise": "ERP / Planning",
  "techniques de négociation": "Négociation",
  "gestion de la relation client": "Gestion CRM",
  "développement de logiciels": "Développement logiciel",
  "commerce international": "Commerce int'l",
  "ressources humaines": "RH",
  management: "Management",
  cybersécurité: "Cybersécurité",
  "cloud computing": "Cloud",
  "intelligence artificielle": "IA",
  "machine learning": "Machine Learning",
  "droit des affaires": "Droit des affaires",
};

const COMPANY_DISPLAY: Record<string, string> = {
  "AMARIS FRANCE SAS": "Amaris",
  "EFE INTERNATIONAL": "EFE International",
  EXTIA: "Extia",
  "ALTEN SA": "Alten",
  "CAPGEMINI TECHNOLOGY SERVICES": "Capgemini",
  THALES: "Thales",
  AIRBUS: "Airbus",
  RENAULT: "Renault",
  "TOTAL ENERGIES": "TotalEnergies",
  "SCHNEIDER ELECTRIC": "Schneider Electric",
  SAFRAN: "Safran",
  "SAINT GOBAIN": "Saint-Gobain",
  "BNP PARIBAS": "BNP Paribas",
  "SOCIETE GENERALE": "Société Générale",
};

const ACCENTS = {
  teal: {
    badge: "bg-teal-500/15 text-teal-700 border-teal-200",
    icon: "bg-teal-500/12 text-teal-700",
    text: "text-teal-700",
    fill: "from-teal-500 to-cyan-500",
    featuredCard:
      "bg-gradient-to-br from-teal-50 via-cyan-50 to-white border-teal-200/80",
  },
  sky: {
    badge: "bg-sky-500/15 text-sky-700 border-sky-200",
    icon: "bg-sky-500/12 text-sky-700",
    text: "text-sky-700",
    fill: "from-sky-500 to-blue-500",
    featuredCard:
      "bg-gradient-to-br from-sky-50 via-blue-50 to-white border-sky-200/80",
  },
  blue: {
    badge: "bg-blue-500/15 text-blue-700 border-blue-200",
    icon: "bg-blue-500/12 text-blue-700",
    text: "text-blue-700",
    fill: "from-blue-500 to-indigo-500",
    featuredCard:
      "bg-gradient-to-br from-blue-50 via-indigo-50 to-white border-blue-200/80",
  },
  amber: {
    badge: "bg-amber-500/15 text-amber-700 border-amber-200",
    icon: "bg-amber-500/12 text-amber-700",
    text: "text-amber-700",
    fill: "from-amber-500 to-orange-500",
    featuredCard:
      "bg-gradient-to-br from-amber-50 via-orange-50 to-white border-amber-200/80",
  },
  slate: {
    badge: "bg-slate-500/10 text-slate-600 border-slate-200",
    icon: "bg-slate-500/10 text-slate-600",
    text: "text-slate-700",
    fill: "from-slate-500 to-slate-700",
    featuredCard:
      "bg-gradient-to-br from-slate-50 via-white to-white border-slate-200/80",
  },
} as const;

type AccentKey = keyof typeof ACCENTS;

type CountryCount = { country: string; count: number };
type CompanyCount = { company: string; count: number };
type SkillCount = { skill: string; count: number; label?: string };
type Tab = "overview" | "explorer";

type DashboardSignal = {
  icon: LucideIcon;
  label: string;
  value: string;
  accent: AccentKey;
};

type DashboardPayload = {
  kpis: {
    label: string;
    value: number | string;
    sublabel?: string;
    icon: LucideIcon;
    accent: AccentKey;
    featured?: boolean;
  }[];
  mapTitle: string;
  destinationsTitle: string;
  recruitersTitle: string;
  skillsTitle: string;
  topRolesTitle?: string;
  signalsTitle?: string;
  countryCounts: CountryCount[];
  topCountries: CountryCount[];
  topCompanies: CompanyCount[];
  topSkills: SkillCount[];
  topRoles?: MarketInsightsRole[];
  topRolesEmptyMessage?: string;
  signals?: DashboardSignal[];
};

function displaySkill(raw: string): string {
  return SKILL_DISPLAY[raw.toLowerCase().trim()] ?? raw;
}

function displayCompany(raw: string): string {
  return COMPANY_DISPLAY[raw.trim()] ?? raw;
}

function normalizeText(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

const COUNTRY_ALIASES: Record<string, string> = {
  belgique: "belgium",
  espagne: "spain",
  allemagne: "germany",
  france: "france",
  italie: "italy",
  portugal: "portugal",
  paysbas: "netherlands",
  "pays bas": "netherlands",
  suisse: "switzerland",
  "royaume uni": "united kingdom",
  "etats unis": "united states of america",
  usa: "united states of america",
  etatsunis: "united states of america",
  "cote divoire": "cote d ivoire",
  tchequie: "czechia",
  "république tcheque": "czechia",
  "republique tcheque": "czechia",
  autriche: "austria",
  suede: "sweden",
  norvege: "norway",
  danemark: "denmark",
  finlande: "finland",
  irlande: "ireland",
  pologne: "poland",
  grece: "greece",
  hongrie: "hungary",
};

const COUNTRY_COORDINATES: Record<string, [number, number]> = {
  france: [2.2137, 46.2276],
  germany: [10.4515, 51.1657],
  spain: [-3.7492, 40.4637],
  italy: [12.5674, 41.8719],
  portugal: [-8.2245, 39.3999],
  belgium: [4.4699, 50.5039],
  netherlands: [5.2913, 52.1326],
  switzerland: [8.2275, 46.8182],
  austria: [14.5501, 47.5162],
  denmark: [9.5018, 56.2639],
  sweden: [18.6435, 60.1282],
  norway: [8.4689, 60.472],
  finland: [25.7482, 61.9241],
  ireland: [-8.2439, 53.4129],
  poland: [19.1451, 51.9194],
  czechia: [15.473, 49.8175],
  romania: [24.9668, 45.9432],
  greece: [21.8243, 39.0742],
  hungary: [19.5033, 47.1625],
  "united kingdom": [-3.436, 55.3781],
  canada: [-106.3468, 56.1304],
  "united states of america": [-95.7129, 37.0902],
  mexico: [-102.5528, 23.6345],
  brazil: [-51.9253, -14.235],
  argentina: [-63.6167, -38.4161],
  morocco: [-7.0926, 31.7917],
  algeria: [1.6596, 28.0339],
  tunisia: [9.5375, 33.8869],
  senegal: [-14.4524, 14.4974],
  "cote d ivoire": [-5.5471, 7.54],
  china: [104.1954, 35.8617],
  japan: [138.2529, 36.2048],
  singapore: [103.8198, 1.3521],
  india: [78.9629, 20.5937],
  australia: [133.7751, -25.2744],
};

function normalizeCountryKey(value: string): string {
  const normalized = normalizeText(value);
  return COUNTRY_ALIASES[normalized] ?? normalized;
}

function sectorLabel(key: string): string {
  return SECTOR_LABELS[key] ?? key;
}


function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "0%";
  return `${value.toFixed(value % 1 === 0 ? 0 : 1)}%`;
}

function ratio(numerator: number, denominator: number): number {
  if (!denominator) return 0;
  return numerator / denominator;
}

function sumCounts<T extends { count: number }>(items: T[], limit: number): number {
  return items.slice(0, limit).reduce((sum, item) => sum + item.count, 0);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function computeMapView(countryCounts: CountryCount[], topCountries: CountryCount[]) {
  const weighted = countryCounts
    .map((entry) => ({
      count: entry.count,
      coords: COUNTRY_COORDINATES[normalizeCountryKey(entry.country)],
    }))
    .filter((entry): entry is { count: number; coords: [number, number] } => Array.isArray(entry.coords));

  const europeCountries = new Set(
    [
      "france",
      "germany",
      "spain",
      "italy",
      "portugal",
      "belgium",
      "netherlands",
      "switzerland",
      "austria",
      "denmark",
      "sweden",
      "norway",
      "finland",
      "ireland",
      "poland",
      "czechia",
      "romania",
      "greece",
      "hungary",
      "united kingdom",
      "uk",
      "england",
      "scotland",
      "wales",
    ].map(normalizeCountryKey),
  );
  const top5 = topCountries.slice(0, 5).map((c) => normalizeCountryKey(c.country));
  const focusEurope = top5.filter((c) => europeCountries.has(c)).length >= 3;

  if (weighted.length === 0) {
    return focusEurope
      ? { center: [12, 49] as [number, number], zoom: 3.2 }
      : { center: [8, 20] as [number, number], zoom: 1.25 };
  }

  const totalWeight = weighted.reduce((sum, entry) => sum + entry.count, 0) || 1;
  const lon = weighted.reduce((sum, entry) => sum + entry.coords[0] * entry.count, 0) / totalWeight;
  const lat = weighted.reduce((sum, entry) => sum + entry.coords[1] * entry.count, 0) / totalWeight;
  const lons = weighted.map((entry) => entry.coords[0]);
  const lats = weighted.map((entry) => entry.coords[1]);
  const lonSpan = Math.max(...lons) - Math.min(...lons);
  const latSpan = Math.max(...lats) - Math.min(...lats);
  const spread = Math.max(lonSpan, latSpan);

  if (focusEurope) {
    return {
      center: [clamp(lon, -4, 22), clamp(lat, 42, 56)] as [number, number],
      zoom: clamp(4.8 - spread / 6, 2.6, 4.4),
    };
  }

  return {
    center: [clamp(lon, -30, 60), clamp(lat, -5, 45)] as [number, number],
    zoom: clamp(2.2 - spread / 55, 1.1, 2.0),
  };
}

function MarketInsightsFrame({
  children,
  strict = false,
}: {
  children: React.ReactNode;
  strict?: boolean;
}) {
  return (
    <div
      className="mx-auto overflow-hidden rounded-[28px] border border-slate-200/80 bg-white/95 shadow-[0_18px_50px_-36px_rgba(15,23,42,0.28)]"
      style={
        strict
          ? {
              width: "min(calc(100vw - 32px), calc((100vh - 32px) * 16 / 9))",
              aspectRatio: "16 / 9",
            }
          : undefined
      }
    >
      <div className="h-full w-full p-2.5">{children}</div>
    </div>
  );
}

function DashboardSection({
  title,
  icon: Icon,
  iconAccent,
  children,
}: {
  title: string;
  icon: LucideIcon;
  iconAccent: AccentKey;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-0 flex-col rounded-[22px] border border-slate-200 bg-white p-3 shadow-[0_16px_40px_-30px_rgba(15,23,42,0.28)] xl:h-full">
      <div className="mb-3 flex items-center gap-2">
        <span
          className={`flex h-7 w-7 items-center justify-center rounded-xl border ${ACCENTS[iconAccent].badge}`}
        >
          <Icon size={14} />
        </span>
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {title}
        </h3>
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sublabel,
  icon: Icon,
  accent,
  featured = false,
}: {
  label: string;
  value: number | string;
  sublabel?: string;
  icon: LucideIcon;
  accent: AccentKey;
  featured?: boolean;
}) {
  return (
    <div
      className={`relative overflow-hidden rounded-[20px] border p-3 shadow-[0_12px_30px_-24px_rgba(15,23,42,0.35)] ${
        featured ? ACCENTS[accent].featuredCard : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {label}
          </p>
          <p className="truncate text-[1.5rem] font-bold leading-none tracking-tight text-slate-900">
            {typeof value === "number" ? value.toLocaleString("fr-FR") : value}
          </p>
          {sublabel && <p className="mt-1 text-[11px] text-slate-500">{sublabel}</p>}
        </div>
        <span
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] ${ACCENTS[accent].icon}`}
        >
          <Icon size={18} />
        </span>
      </div>
    </div>
  );
}

function KpiGrid({
  items,
}: {
  items: DashboardPayload["kpis"];
}) {
  return (
    <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-6">
      {items.map((item) => (
        <MetricCard key={item.label} {...item} />
      ))}
    </div>
  );
}

function SectorOpportunityMap({
  countryCounts,
  topCountries,
  title,
}: {
  countryCounts: CountryCount[];
  topCountries: CountryCount[];
  title: string;
}) {
  const normalizedCounts = new Map(
    countryCounts.map((c) => [normalizeCountryKey(c.country), c.count]),
  );
  const maxCount = Math.max(...countryCounts.map((c) => c.count), 1);

  const colorFor = (count: number) => {
    const t = Math.min(count / maxCount, 1);
    const boosted = Math.sqrt(t);
    const start = [226, 232, 240];
    const end = [13, 148, 136];
    const mix = start.map((s, i) => Math.round(s + (end[i] - s) * boosted));
    return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
  };

  const [hovered, setHovered] = useState<{ name: string; count: number } | null>(null);
  const mapView = useMemo(
    () => computeMapView(countryCounts, topCountries),
    [countryCounts, topCountries],
  );

  return (
    <DashboardSection title={title} icon={Globe} iconAccent="teal">
      <div className="flex h-full flex-col">
        <div className="mb-2 flex items-center justify-between gap-3 text-[11px] text-slate-500">
          <span>Intensité des offres par pays</span>
          <span>{hovered ? `${hovered.name} · ${hovered.count}` : "Survol pour détail"}</span>
        </div>
        <div className="relative h-[320px] min-h-0 flex-1 overflow-hidden rounded-[18px] border border-slate-200 bg-slate-50/80 md:h-[380px] xl:h-full">
          <div className="absolute inset-0 p-1.5">
            <ComposableMap
              projection="geoMercator"
              projectionConfig={{ scale: 145 }}
              style={{ width: "100%", height: "100%" }}
            >
              <ZoomableGroup center={mapView.center} zoom={mapView.zoom}>
                <Geographies geography={GEO_URL}>
                  {({ geographies }: { geographies: any[] }) =>
                    geographies.map((geo: any) => {
                      const name = geo.properties?.name ?? "";
                      const count = normalizedCounts.get(normalizeCountryKey(name)) ?? 0;
                      const fill = count > 0 ? colorFor(count) : "#E2E8F0";

                      return (
                        <Geography
                          key={geo.rsmKey}
                          geography={geo}
                          fill={fill}
                          stroke="#94A3B8"
                          strokeWidth={0.4}
                          onMouseEnter={() => count > 0 && setHovered({ name, count })}
                          onMouseLeave={() => setHovered(null)}
                          onFocus={() => count > 0 && setHovered({ name, count })}
                          onBlur={() => setHovered(null)}
                          title={count > 0 ? `${name} — ${count} offres` : name}
                          style={{
                            default: { outline: "none" },
                            hover: { fill: "#0F766E", outline: "none" },
                            pressed: { fill: "#0F766E", outline: "none" },
                          }}
                        />
                      );
                    })
                  }
                </Geographies>
              </ZoomableGroup>
            </ComposableMap>
          </div>
          {countryCounts.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-400">
              Aucune donnée pays disponible
            </div>
          )}
        </div>
        <div className="mt-2 flex items-center gap-2 text-[10px] text-slate-500">
          <span>Faible</span>
          <div className="h-1.5 flex-1 rounded-full bg-gradient-to-r from-slate-200 via-teal-300 to-teal-600" />
          <span>Élevé</span>
        </div>
      </div>
    </DashboardSection>
  );
}

function RankingPanel({
  title,
  icon,
  iconAccent,
  items,
  nameKey,
  valueAccent,
  maxItems,
}: {
  title: string;
  icon: LucideIcon;
  iconAccent: AccentKey;
  items: Array<Record<string, string | number>>;
  nameKey: string;
  valueAccent: AccentKey;
  maxItems: number;
}) {
  const displayed = items.slice(0, maxItems);

  return (
    <DashboardSection title={title} icon={icon} iconAccent={iconAccent}>
      <div className="space-y-1">
        {displayed.map((item, index) => {
          const name = String(item[nameKey]);
          const value = Number(item.count ?? 0);
          const rankAccent: AccentKey = index === 0 ? "amber" : index === 1 ? "slate" : index === 2 ? "blue" : "slate";

          return (
            <div
              key={`${title}-${name}-${index}`}
              className="flex items-center justify-between rounded-[16px] border border-slate-100 bg-slate-50/80 px-2.5 py-2"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-[11px] font-bold ${ACCENTS[rankAccent].badge}`}
                >
                  {index + 1}
                </span>
                <span className="truncate text-[13px] font-medium text-slate-800">
                  {nameKey === "company" ? displayCompany(name) : name}
                </span>
              </div>
              <span className={`text-[13px] font-bold ${ACCENTS[valueAccent].text}`}>
                {value.toLocaleString("fr-FR")}
              </span>
            </div>
          );
        })}
        {displayed.length === 0 && (
          <p className="text-[12px] text-slate-400">Aucune donnée disponible.</p>
        )}
      </div>
    </DashboardSection>
  );
}

function SkillsPanel({
  title,
  skills,
}: {
  title: string;
  skills: SkillCount[];
}) {
  const displayed = [...skills]
    .sort((a, b) => b.count - a.count || a.skill.localeCompare(b.skill))
    .slice(0, 8);
  const maxCount = Math.max(...displayed.map((skill) => skill.count), 1);

  return (
    <DashboardSection title={title} icon={Zap} iconAccent="blue">
      <div className="grid h-full grid-cols-1 gap-x-5 gap-y-2 lg:grid-cols-2">
        {displayed.map((skill) => {
          const label = skill.label ?? displaySkill(skill.skill);
          const width = `${(skill.count / maxCount) * 100}%`;

          return (
            <div key={skill.skill}>
              <div className="mb-1 flex items-center justify-between gap-3">
                <span className="truncate text-[13px] font-medium text-slate-800">{label}</span>
                <span className="shrink-0 text-[11px] text-slate-500">
                  {skill.count.toLocaleString("fr-FR")}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-blue-500 to-teal-500"
                  style={{ width }}
                />
              </div>
            </div>
          );
        })}
        {displayed.length === 0 && (
          <p className="text-[12px] text-slate-400">Aucune compétence exploitable pour ce filtre.</p>
        )}
      </div>
    </DashboardSection>
  );
}

function SignalsPanel({
  title,
  signals,
}: {
  title: string;
  signals: DashboardSignal[];
}) {
  return (
    <DashboardSection title={title} icon={Activity} iconAccent="sky">
      <div className="flex h-full gap-2.5">
        {signals.map((signal) => {
          const Icon = signal.icon;
          return (
            <div
              key={signal.label}
              className="flex flex-1 flex-col items-center justify-center rounded-[18px] border border-slate-100 bg-slate-50/80 px-2 py-3 text-center"
            >
              <span className={`mb-2 flex h-8 w-8 items-center justify-center rounded-xl ${ACCENTS[signal.accent].icon}`}>
                <Icon size={16} />
              </span>
              <p className={`text-lg font-bold ${ACCENTS[signal.accent].text}`}>{signal.value}</p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                {signal.label}
              </p>
            </div>
          );
        })}
      </div>
    </DashboardSection>
  );
}

function MarketDashboardLayout({
  payload,
}: {
  payload: DashboardPayload;
}) {
  return (
    <div className="grid grid-cols-1 gap-2.5 xl:grid-cols-12 xl:grid-rows-[auto_minmax(0,1fr)_minmax(0,0.82fr)]">
      <div className="xl:col-span-12">
        <KpiGrid items={payload.kpis} />
      </div>

      <div className="min-h-0 xl:col-span-12 2xl:col-span-5">
        <SectorOpportunityMap
          countryCounts={payload.countryCounts}
          topCountries={payload.topCountries}
          title={payload.mapTitle}
        />
      </div>

      <div className="min-h-0 xl:col-span-6 2xl:col-span-4">
        <RankingPanel
          title={payload.destinationsTitle}
          icon={MapPin}
          iconAccent="amber"
          items={payload.topCountries as Array<Record<string, string | number>>}
          nameKey="country"
          valueAccent="teal"
          maxItems={3}
        />
      </div>

      <div className="min-h-0 xl:col-span-6 2xl:col-span-3">
        <RankingPanel
          title={payload.recruitersTitle}
          icon={Building2}
          iconAccent="blue"
          items={payload.topCompanies as Array<Record<string, string | number>>}
          nameKey="company"
          valueAccent="blue"
          maxItems={5}
        />
      </div>

      <div className="min-h-0 xl:col-span-12 2xl:col-span-8">
        <SkillsPanel title={payload.skillsTitle} skills={payload.topSkills} />
      </div>

      <div className="min-h-0 xl:col-span-12 2xl:col-span-4">
        {payload.topRoles ? (
          <TopRolesCard
            title={payload.topRolesTitle ?? "Top postes"}
            roles={payload.topRoles}
            emptyMessage={payload.topRolesEmptyMessage}
          />
        ) : (
          <SignalsPanel title={payload.signalsTitle ?? "Signaux"} signals={payload.signals ?? []} />
        )}
      </div>
    </div>
  );
}

function buildOverviewPayload(data: MarketInsightsResponse): DashboardPayload {
  const countryCounts = data.country_counts ?? data.top_countries ?? [];
  const topCountries = countryCounts.slice(0, 5);
  const companyCounts = data.company_counts ?? [];
  const topCompanies = companyCounts.slice(0, 5);
  const topSkills = (data.top_skills ?? []).slice(0, 8).map((skill) => ({
    skill: skill.skill,
    count: skill.count,
    label: skill.display_label,
  }));
  const topDestination = topCountries[0] ?? null;
  const concentration = ratio(sumCounts(topCountries, 5), data.total_offers) * 100;

  return {
    kpis: [
      {
        label: "Offres VIE",
        value: data.total_offers,
        icon: Briefcase,
        accent: "teal",
        featured: true,
      },
      {
        label: "Pays",
        value: data.total_countries,
        sublabel: "Destinations actives",
        icon: Globe,
        accent: "sky",
        featured: true,
      },
      {
        label: "Employeurs",
        value: companyCounts.length,
        sublabel: "Entreprises recrutant",
        icon: Building2,
        accent: "blue",
      },
      {
        label: "Compétences",
        value: data.total_skills,
        sublabel: "Skills recherchés",
        icon: Zap,
        accent: "amber",
      },
      {
        label: "#1 Destination",
        value: topDestination?.country ?? "—",
        sublabel: topDestination ? `${topDestination.count} offres` : "—",
        icon: MapPin,
        accent: "slate",
      },
      {
        label: "Concentration",
        value: formatPercent(concentration),
        sublabel: "Top 5 pays",
        icon: Target,
        accent: "slate",
      },
    ],
    mapTitle: "Répartition géographique",
    destinationsTitle: "Top destinations",
    recruitersTitle: "Top recruteurs",
    skillsTitle: "Compétences dominantes",
    topRolesTitle: "Top postes",
    countryCounts,
    topCountries,
    topCompanies,
    topSkills,
    topRoles: (data.top_roles ?? []).slice(0, 5),
    topRolesEmptyMessage: "Aucun poste dominant exploitable sur le corpus actuel.",
  };
}

function buildSectorPayload(
  data: MarketInsightsResponse,
  activeSector: string,
): DashboardPayload {
  const totalOffers = (data.sectors_distribution ?? [])
    .filter((sector) => sector.sector === activeSector)
    .reduce((sum, sector) => sum + sector.count, 0);

  const countrySource = data.sector_country_counts ?? data.sector_country_matrix ?? [];
  const countryMap: Record<string, number> = {};
  countrySource
    .filter((entry) => entry.sector === activeSector)
    .forEach((entry) => {
      countryMap[entry.country] = (countryMap[entry.country] ?? 0) + entry.count;
    });
  const countryCounts = Object.entries(countryMap)
    .sort((a, b) => b[1] - a[1])
    .map(([country, count]) => ({ country, count }));
  const topCountries = countryCounts.slice(0, 5);

  const companySource = data.sector_company_counts ?? data.sector_companies ?? [];
  const companyMap: Record<string, number> = {};
  companySource
    .filter((entry) => entry.sector === activeSector)
    .forEach((entry) => {
      companyMap[entry.company] = (companyMap[entry.company] ?? 0) + entry.count;
    });
  const topCompanies = Object.entries(companyMap)
    .sort((a, b) => b[1] - a[1])
    .map(([company, count]) => ({ company, count }))
    .slice(0, 5);

  let topSkills: SkillCount[] = [];
  let totalSkillCount = 0;
  if (data.sector_distinctive_skills && data.sector_distinctive_skills.length > 0) {
    const skillMap: Record<string, { count: number; score: number; label?: string }> = {};
    data.sector_distinctive_skills
      .filter((entry) => entry.sector === activeSector)
      .forEach((entry) => {
        const prev = skillMap[entry.skill];
        if (!prev) {
          skillMap[entry.skill] = {
            count: entry.count,
            score: entry.distinctiveness,
            label: entry.display_label ?? entry.skill,
          };
          return;
        }

        skillMap[entry.skill] = {
          count: prev.count + entry.count,
          score: prev.score + entry.distinctiveness,
          label: prev.label ?? entry.display_label ?? entry.skill,
        };
      });

    topSkills = Object.entries(skillMap)
      .sort((a, b) => b[1].score - a[1].score || b[1].count - a[1].count)
      .slice(0, 8)
      .map(([skill, value]) => ({
        skill,
        count: value.count,
        label: value.label,
      }));
    totalSkillCount = Object.keys(skillMap).length;
  }

  if (topSkills.length === 0) {
    const skillMap: Record<string, number> = {};
    (data.sector_skill_matrix ?? [])
      .filter((entry) => entry.sector === activeSector)
      .forEach((entry) => {
        skillMap[entry.skill] = (skillMap[entry.skill] ?? 0) + entry.count;
      });

    topSkills = Object.entries(skillMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([skill, count]) => ({ skill, count }));
    totalSkillCount = Object.keys(skillMap).length;
  }

  const topDestination = topCountries[0] ?? null;
  const concentration = ratio(sumCounts(topCountries, 5), totalOffers) * 100;
  const offersPerCountry = Math.round(ratio(totalOffers, countryCounts.length));
  const marketShare = ratio(totalOffers, data.total_offers) * 100;
  const dominantEmployer = topCompanies[0] ?? null;
  const dominantSectorLabel = sectorLabel(activeSector);
  const topRoles = (data.sector_top_roles ?? [])
    .filter((entry) => entry.sector === activeSector)
    .slice(0, 5)
    .map(({ sector: _sector, ...role }) => role);

  return {
    kpis: [
      {
        label: "Offres secteur",
        value: totalOffers,
        icon: Briefcase,
        accent: "teal",
        featured: true,
      },
      {
        label: "Pays",
        value: countryCounts.length,
        sublabel: "Présence active",
        icon: Globe,
        accent: "sky",
        featured: true,
      },
      {
        label: "Employeurs",
        value: Object.keys(companyMap).length,
        sublabel: "Recruteurs actifs",
        icon: Building2,
        accent: "blue",
      },
      {
        label: "Compétences",
        value: totalSkillCount,
        sublabel: "Corpus secteur",
        icon: Zap,
        accent: "amber",
      },
      {
        label: "#1 Destination",
        value: topDestination?.country ?? "—",
        sublabel: topDestination ? `${topDestination.count} offres` : "—",
        icon: MapPin,
        accent: "slate",
      },
      {
        label: "Concentration",
        value: formatPercent(concentration),
        sublabel: "Top 5 pays",
        icon: Target,
        accent: "slate",
      },
    ],
    mapTitle: `Répartition — ${dominantSectorLabel}`,
    destinationsTitle: "Top destinations",
    recruitersTitle: "Top recruteurs",
    skillsTitle: "Compétences distinctives",
    topRolesTitle: "Top postes",
    countryCounts,
    topCountries,
    topCompanies,
    topSkills,
    topRoles,
    topRolesEmptyMessage: "Aucun poste suffisamment lisible dans ce secteur.",
    signals: [
      {
        icon: Target,
        label: "Part du marché",
        value: formatPercent(marketShare),
        accent: "sky",
      },
      {
        icon: TrendingUp,
        label: "Offres / pays",
        value: offersPerCountry.toLocaleString("fr-FR"),
        accent: "teal",
      },
      {
        icon: Building2,
        label: "Employeur dominant",
        value: dominantEmployer ? dominantEmployer.count.toLocaleString("fr-FR") : "—",
        accent: "amber",
      },
    ],
  };
}

function OverviewView({ data }: { data: MarketInsightsResponse }) {
  const payload = useMemo(() => buildOverviewPayload(data), [data]);
  return <MarketDashboardLayout payload={payload} />;
}

function SectorExplorerView({
  data,
  selectedSector,
}: {
  data: MarketInsightsResponse;
  selectedSector: string | null;
}) {
  const allSectors = (data.sectors_distribution ?? [])
    .filter((sector) => sector.sector !== "OTHER")
    .map((sector) => sector.sector);
  const activeSector = selectedSector || allSectors[0] || null;

  const payload = useMemo(() => {
    if (!activeSector) return null;
    return buildSectorPayload(data, activeSector);
  }, [activeSector, data]);

  if (!payload) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        Aucun secteur exploitable.
      </div>
    );
  }

  return <MarketDashboardLayout payload={payload} />;
}

export default function MarketInsightsPage() {
  const searchParams = new URLSearchParams(window.location.search);
  const [data, setData] = useState<MarketInsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(
    searchParams.get("tab") === "explorer" ? "explorer" : "overview",
  );
  const [selectedSector, setSelectedSector] = useState<string | null>(null);
  const screenshotMode = searchParams.get("nav") !== "1";

  useEffect(() => {
    fetchMarketInsights()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (selectedSector || !data?.sectors_distribution?.length) return;
    const firstSector =
      data.sectors_distribution.find((sector) => sector.sector !== "OTHER")?.sector ?? null;
    setSelectedSector(firstSector);
  }, [data, selectedSector]);

  const sectorOptions = useMemo(
    () =>
      (data?.sectors_distribution ?? [])
        .filter((sector) => sector.sector !== "OTHER")
        .map((sector) => sector.sector),
    [data],
  );

  const dashboardBody = (
    <MarketInsightsFrame strict={screenshotMode}>
      <div className="flex h-full w-full flex-col gap-3 rounded-[24px] border border-slate-200/80 bg-slate-50/75 p-3 md:p-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 md:text-[1.35rem]">
                <span className="text-teal-700">V.I.E</span> Marché
              </h1>
              <div className="flex w-full flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-1 print:hidden xl:w-auto">
                {(
                  [
                    { key: "overview", label: "Vue d'ensemble" },
                    { key: "explorer", label: "Par secteur" },
                  ] as { key: Tab; label: string }[]
                ).map((item) => (
                  <button
                    key={item.key}
                    onClick={() => setTab(item.key)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      tab === item.key
                        ? "bg-teal-600 text-white shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              {tab === "explorer" && sectorOptions.length > 0 && (
                <div className="relative min-w-0 flex-1 print:hidden xl:min-w-[220px] xl:flex-none">
                  <select
                    value={selectedSector ?? sectorOptions[0]}
                    onChange={(e) => setSelectedSector(e.target.value)}
                    className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-9 text-sm font-medium text-slate-700 outline-none transition focus:border-slate-400"
                  >
                    {sectorOptions.map((sector) => (
                      <option key={sector} value={sector}>
                        {sectorLabel(sector)}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    size={16}
                    className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                </div>
              )}
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              Vue macro du marché V.I.E, alignée avec le reste du produit et lisible sur mobile.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className="text-[11px] text-slate-500">
              Source: Elevia Compass
            </span>
            {!screenshotMode && (
              <button
                onClick={() => window.print()}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-medium text-slate-600 shadow-sm transition hover:bg-slate-50 print:hidden"
              >
                <Printer size={14} />
                Exporter PDF
              </button>
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-visible xl:overflow-hidden">
          {loading && (
            <div className="flex h-full min-h-[240px] items-center justify-center text-sm text-slate-400">
              Chargement des données marché…
            </div>
          )}

          {error && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
              Erreur : {error}
            </div>
          )}

          {!loading && !error && data && tab === "overview" && <OverviewView data={data} />}
          {!loading && !error && data && tab === "explorer" && (
            <SectorExplorerView data={data} selectedSector={selectedSector} />
          )}
        </div>
      </div>
    </MarketInsightsFrame>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      {screenshotMode ? (
        <div className="relative flex min-h-screen w-full items-center justify-center p-4">
          {dashboardBody}
        </div>
      ) : (
        <PremiumAppShell
          eyebrow="Marché"
          title="Lire le marché avant d'agir"
          description="Cette page reste macro. Elle donne le contexte V.I.E global, avec le même framing produit que le cockpit, l'inbox et le catalogue."
          contentClassName="max-w-7xl"
        >
          {dashboardBody}
        </PremiumAppShell>
      )}

      <style>{`
        @media print {
          body { background: white; }
          .print\\:hidden { display: none !important; }
          @page { size: A4 landscape; margin: 1.5cm; }
        }
      `}</style>
    </div>
  );
}
