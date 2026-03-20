import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { BarChart3, Briefcase, Compass, Inbox, ScanSearch, UserRound } from "lucide-react";
import { cn } from "../../lib/cn";
import { PageContainer } from "./PageContainer";

type PremiumAppShellProps = {
  eyebrow?: string;
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  contentClassName?: string;
};

const NAV_ITEMS = [
  { to: "/analyze", label: "Analyser", icon: ScanSearch },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/dashboard", label: "Cockpit", icon: Compass },
  { to: "/applications", label: "Candidatures", icon: Briefcase },
  { to: "/market-insights", label: "Marche", icon: BarChart3 },
  { to: "/profile", label: "Profil", icon: UserRound },
] as const;

function isActive(pathname: string, to: string): boolean {
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function PremiumAppShell({
  eyebrow,
  title,
  description,
  actions,
  children,
  contentClassName,
}: PremiumAppShellProps) {
  const location = useLocation();

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-[#f8fafc] text-slate-900">
      <div className="pointer-events-none fixed inset-0 -z-20 overflow-hidden">
        <div className="absolute -left-28 top-0 h-80 w-80 rounded-full bg-emerald-200/35 blur-3xl" />
        <div className="absolute right-[-8rem] top-24 h-96 w-96 rounded-full bg-cyan-200/30 blur-3xl" />
        <div className="absolute left-1/3 top-1/2 h-[28rem] w-[28rem] rounded-full bg-slate-200/35 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.85),rgba(248,250,252,0.96)_45%,rgba(241,245,249,1)_100%)]" />
        <div
          className="absolute inset-0 opacity-[0.045]"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.7' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
          }}
        />
      </div>

      <header className="sticky top-0 z-40 border-b border-white/60 bg-white/65 backdrop-blur-xl">
        <PageContainer className="py-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <Link
                to="/"
                className="inline-flex h-11 items-center rounded-full border border-slate-200/80 bg-white/80 px-4 text-sm font-semibold tracking-tight text-slate-900 shadow-sm"
              >
                Elevia
              </Link>
              <div className="hidden text-xs font-medium text-slate-500 md:block">
                Workspace inspire d&apos;AdCoach, adapte aux pages produit.
              </div>
            </div>

            <nav className="no-scrollbar flex items-center gap-2 overflow-x-auto rounded-full border border-slate-200/80 bg-white/70 p-1 shadow-sm">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isActive(location.pathname, item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-medium transition-all",
                      active
                        ? "bg-slate-900 text-white shadow-sm"
                        : "text-slate-600 hover:bg-slate-100/90 hover:text-slate-900"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </PageContainer>
      </header>

      <PageContainer className={cn("relative z-10 pb-16 pt-8 md:pt-10", contentClassName)}>
        {(title || description || actions) && (
          <section className="mb-8 rounded-[2rem] border border-white/80 bg-white/70 px-6 py-6 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl md:px-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                {eyebrow && (
                  <div className="mb-3 inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">
                    {eyebrow}
                  </div>
                )}
                {title && <h1 className="text-3xl font-semibold tracking-tight text-slate-950 md:text-5xl">{title}</h1>}
                {description && (
                  <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600 md:text-base">
                    {description}
                  </p>
                )}
              </div>
              {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
            </div>
          </section>
        )}

        {children}
      </PageContainer>
    </div>
  );
}
