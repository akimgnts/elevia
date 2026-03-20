import { Briefcase } from "lucide-react";

import type { MarketInsightsRole } from "../../lib/api";

export function TopRolesCard({
  title,
  roles,
  emptyMessage,
}: {
  title: string;
  roles: MarketInsightsRole[];
  emptyMessage?: string;
}) {
  const displayed = roles.slice(0, 5);
  const mode = displayed[0]?.mode ?? "";
  const showFallbackHint = mode.includes("fallback");

  return (
    <div className="rounded-[22px] border border-slate-200 bg-white p-3 shadow-[0_16px_40px_-30px_rgba(15,23,42,0.28)] h-full min-h-0 flex flex-col overflow-hidden">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-xl border bg-sky-500/15 text-sky-700 border-sky-200">
          <Briefcase size={14} />
        </span>
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {title}
        </h3>
      </div>
      {showFallbackHint && (
        <p className="mb-2 text-[11px] text-slate-500">
          Lecture indicative : signal rôle moins robuste sur ce périmètre.
        </p>
      )}
      <div className="space-y-1 min-h-0 flex-1 overflow-y-auto pr-1">
        {displayed.map((role, index) => (
          <div
            key={`${role.role}-${index}`}
            className="rounded-[16px] border border-slate-100 bg-slate-50/80 px-2.5 py-2"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-[11px] font-bold bg-slate-500/10 text-slate-600 border-slate-200">
                  {index + 1}
                </span>
                <span className="truncate text-[13px] font-medium text-slate-800">{role.role}</span>
              </div>
              <span className="shrink-0 text-[13px] font-bold text-sky-700">
                {role.count.toLocaleString("fr-FR")}
              </span>
            </div>
            {role.skills && role.skills.length > 0 && (
              <p className="mt-1 pl-[34px] text-[11px] leading-6 text-slate-500">
                {role.skills.slice(0, 3).join(" • ")}
              </p>
            )}
          </div>
        ))}
        {displayed.length === 0 && (
          <p className="text-[12px] text-slate-400">{emptyMessage ?? "Aucun poste dominant exploitable."}</p>
        )}
      </div>
    </div>
  );
}
