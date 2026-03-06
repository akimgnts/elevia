import { useState } from "react";

export function DevPanel({
  data,
}: {
  data: {
    pipeline_used?: string | null;
    pipeline_variant?: string | null;
    compass_e_enabled?: boolean | null;
    tight_candidates?: string[] | null;
    filtered_tokens?: string[] | null;
    validated_labels?: string[] | null;
    skills_uri?: string[] | null;
    skills_uri_promoted?: string[] | null;
    skills_uri_effective?: string[] | null;
    warnings?: string[] | null;
  };
}) {
  const [open, setOpen] = useState(false);

  const block = (title: string, items?: string[] | null) => (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-2">
        {title}
      </div>
      {items && items.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <span key={item} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
              {item}
            </span>
          ))}
        </div>
      ) : (
        <div className="text-xs text-slate-400">Aucune donnée.</div>
      )}
    </div>
  );

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left text-sm font-semibold text-amber-800"
      >
        <span>DEV panel (pipeline)</span>
        <span className="text-xs text-amber-700">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-[11px] text-amber-700">
            pipeline_used: <span className="font-semibold">{data.pipeline_used ?? "—"}</span>
            {data.pipeline_variant ? (
              <span className="ml-2 text-amber-900">({data.pipeline_variant})</span>
            ) : null}
            <span className="ml-2">compass_e: {String(data.compass_e_enabled ?? false)}</span>
          </div>

          {block("tight_candidates", data.tight_candidates)}
          {block("filtered_tokens", data.filtered_tokens)}
          {block("validated_labels", data.validated_labels)}
          {block("skills_uri", data.skills_uri)}
          {block("skills_uri_promoted", data.skills_uri_promoted)}
          {block("skills_uri_effective", data.skills_uri_effective)}
          {block("warnings", data.warnings)}
        </div>
      )}
    </section>
  );
}
