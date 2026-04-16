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
  { to: "/analyze", label: "Analyse", icon: ScanSearch },
  { to: "/profile", label: "Profil", icon: UserRound },
  { to: "/dashboard", label: "Cockpit", icon: Compass },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/applications", label: "Candidatures", icon: Briefcase },
  { to: "/market-insights", label: "Marché", icon: BarChart3 },
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
    <div className="relative min-h-screen overflow-x-hidden bg-slate-50 text-slate-900">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.98),rgba(248,250,252,0.92)_42%,rgba(241,245,249,1)_100%)]" />

      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
        <PageContainer className="py-4">
          <div className="flex flex-col gap-3 lg:grid lg:grid-cols-[180px_minmax(0,1fr)_180px] lg:items-center">
            <div className="flex items-center lg:justify-start">
              <Link
                to="/"
                className="inline-flex h-11 items-center rounded-full border border-slate-200 bg-white px-4 text-sm font-semibold tracking-tight text-slate-950 shadow-sm"
              >
                Elevia
              </Link>
            </div>

            <div className="flex justify-center">
              <nav className="no-scrollbar flex max-w-full items-center gap-1 overflow-x-auto rounded-full border border-slate-200 bg-slate-50/90 p-1 shadow-sm">
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
                          : "text-slate-600 hover:bg-white hover:text-slate-900"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </div>

            <div className="hidden lg:block" />
          </div>
        </PageContainer>
      </header>

      <PageContainer className={cn("relative z-10 pb-16 pt-6 md:pt-8", contentClassName)}>
        {(title || description || actions) && (
          <section className="mb-8 border-b border-slate-200/80 pb-6">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                {eyebrow && (
                  <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
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
