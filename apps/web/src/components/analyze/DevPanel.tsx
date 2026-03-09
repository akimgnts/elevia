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
    analyze_dev?: {
      raw_extraction?: {
        raw_extracted_skills?: string[];
        raw_tokens?: string[];
        raw_detected?: number;
        validated_labels?: string[];
      };
      tight_candidates?: { items?: string[]; count?: number };
      canonical_mapping?: {
        mappings?: Array<Record<string, unknown>>;
        matched_count?: number;
        unresolved_count?: number;
        synonym_count?: number;
        tool_count?: number;
      };
      hierarchy_expansion?: {
        input_ids?: string[];
        added_parents?: string[];
        expansion_map?: Record<string, string>;
        expanded_ids?: string[];
      };
      esco_promotion?: {
        canonical_labels?: string[];
        skills_uri_promoted?: string[];
        promoted_uri_count?: number;
      };
      proximity?: {
        links?: Array<Record<string, unknown>>;
        summary?: Record<string, unknown>;
        count?: number;
      };
      explainability?: { status?: string; reason?: string };
      counters?: {
        raw_count?: number;
        tight_count?: number;
        canonical_count?: number;
        unresolved_count?: number;
        expanded_count?: number;
        promoted_uri_count?: number;
        near_match_count?: number;
      };
    };
  };
}) {
  const [open, setOpen] = useState(false);

  const block = (title: string, items?: string[] | null, limit = 60) => {
    const list = items ?? [];
    const sliced = list.slice(0, limit);
    const truncated = list.length > sliced.length;
    return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-2">
        {title}
      </div>
      {sliced.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {sliced.map((item) => (
            <span key={item} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
              {item}
            </span>
          ))}
        </div>
      ) : (
        <div className="text-xs text-slate-400">Aucune donnée.</div>
      )}
      {truncated ? (
        <div className="mt-2 text-[11px] text-slate-400">+ {list.length - sliced.length} autres</div>
      ) : null}
    </div>
  )};

  const keyValueBlock = (title: string, rows: Array<{ key: string; value: string }>) => (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 mb-2">
        {title}
      </div>
      {rows.length > 0 ? (
        <div className="space-y-1 text-xs text-slate-700">
          {rows.map((row) => (
            <div key={`${row.key}-${row.value}`} className="flex gap-2">
              <span className="min-w-[140px] text-slate-500">{row.key}</span>
              <span className="font-medium">{row.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-slate-400">Aucune donnée.</div>
      )}
    </div>
  );

  const analyze = data.analyze_dev;
  const counters = analyze?.counters;
  const mappingRows =
    analyze?.canonical_mapping?.mappings?.map((m) => {
      const raw = String(m.raw ?? "");
      const canonicalId = String(m.canonical_id ?? "");
      const label = String(m.label ?? "");
      const strategy = String(m.strategy ?? "");
      const confidence = typeof m.confidence === "number" ? m.confidence : null;
      if (!raw) return null;
      const core = canonicalId ? `${canonicalId} (${label})` : "unresolved";
      const meta = strategy ? ` • ${strategy}` : "";
      const conf = confidence !== null ? ` • ${confidence}` : "";
      return { key: raw, value: `${core}${meta}${conf}` };
    }).filter(Boolean) as Array<{ key: string; value: string }> | undefined;

  const hierarchyRows =
    analyze?.hierarchy_expansion?.expansion_map
      ? Object.entries(analyze.hierarchy_expansion.expansion_map).map(([child, parent]) => ({
          key: child,
          value: parent,
        }))
      : [];

  const proximityRows =
    analyze?.proximity?.links?.map((link) => {
      const source = String(link.source_id ?? "");
      const target = String(link.target_id ?? "");
      const relation = String(link.relation ?? "");
      const strength =
        typeof link.strength === "number" ? link.strength : Number(link.strength ?? 0);
      if (!source || !target) return null;
      return { key: `${source} → ${target}`, value: `${relation} • ${strength}` };
    }).filter(Boolean) as Array<{ key: string; value: string }> | undefined;

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
          {/* ── Stage 1 ───────────────────────────────────────────────────── */}
          <div className="text-[10px] font-bold uppercase tracking-widest text-amber-700">
            PROFILE PIPELINE (Analyze)
            <span className="ml-1 font-normal normal-case text-amber-500">CV → profile enrichment</span>
          </div>

          <div className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-[11px] text-amber-700">
            pipeline_used: <span className="font-semibold">{data.pipeline_used ?? "—"}</span>
            {data.pipeline_variant ? (
              <span className="ml-2 text-amber-900">({data.pipeline_variant})</span>
            ) : null}
            <span className="ml-2">compass_e: {String(data.compass_e_enabled ?? false)}</span>
          </div>

          {counters ? (
            <div className="grid gap-2 md:grid-cols-3">
              {keyValueBlock("Counters", [
                { key: "raw_count", value: String(counters.raw_count ?? 0) },
                { key: "tight_count", value: String(counters.tight_count ?? 0) },
                { key: "canonical_count", value: String(counters.canonical_count ?? 0) },
                { key: "unresolved_count", value: String(counters.unresolved_count ?? 0) },
                { key: "expanded_count", value: String(counters.expanded_count ?? 0) },
                { key: "promoted_uri_count", value: String(counters.promoted_uri_count ?? 0) },
                { key: "near_match_count", value: String(counters.near_match_count ?? 0) },
              ])}
            </div>
          ) : (
            <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-400">
              Counters: not_available_at_parse_stage
            </div>
          )}

          {block("raw_extracted_skills", analyze?.raw_extraction?.raw_extracted_skills)}
          {block("raw_tokens", analyze?.raw_extraction?.raw_tokens, 80)}
          {block("tight_candidates", analyze?.tight_candidates?.items ?? data.tight_candidates)}
          {block("filtered_tokens", data.filtered_tokens)}
          {block("validated_labels", analyze?.raw_extraction?.validated_labels ?? data.validated_labels)}

          {mappingRows && mappingRows.length > 0
            ? keyValueBlock("canonical_mapping", mappingRows.slice(0, 60))
            : keyValueBlock("canonical_mapping", [])}

          {keyValueBlock("hierarchy_expansion", hierarchyRows.slice(0, 60))}
          {block("canonical_hierarchy_added", analyze?.hierarchy_expansion?.added_parents)}

          {block("skills_uri", data.skills_uri)}
          {block("skills_uri_promoted", analyze?.esco_promotion?.skills_uri_promoted ?? data.skills_uri_promoted)}
          {block("skills_uri_effective", data.skills_uri_effective)}

          {proximityRows && proximityRows.length > 0
            ? keyValueBlock("proximity_links", proximityRows.slice(0, 60))
            : keyValueBlock("proximity_links", [])}

          {keyValueBlock("proximity_summary", [
            { key: "count", value: String(analyze?.proximity?.count ?? 0) },
            { key: "max_strength", value: String(analyze?.proximity?.summary?.max_strength ?? "0") },
            { key: "avg_strength", value: String(analyze?.proximity?.summary?.avg_strength ?? "0") },
          ])}

          {keyValueBlock("explainability", [
            { key: "status", value: String(analyze?.explainability?.status ?? "not_computed_here") },
            { key: "reason", value: String(analyze?.explainability?.reason ?? "not_available_at_parse_stage") },
          ])}

          {block("warnings", data.warnings)}

          {/* ── Stage 2 ───────────────────────────────────────────────────── */}
          <div className="border-t border-amber-200 pt-3 text-[10px] font-bold uppercase tracking-widest text-amber-700">
            MATCH PIPELINE (Inbox)
            <span className="ml-1 font-normal normal-case text-amber-500">profile ↔ offers — near-matches computed at match time</span>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-500">
            <span className="font-medium">near_matches</span> and{" "}
            <span className="font-medium">explainability</span> are available in the Inbox via{" "}
            <code className="rounded bg-slate-100 px-1 font-mono">POST /inbox?explain=true</code>{" "}
            (always enabled). Exact skill matches are excluded — only proximity links appear here.
          </div>
        </div>
      )}
    </section>
  );
}
