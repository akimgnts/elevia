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
      tight_candidates?: {
        items?: string[];
        count?: number;
        top_candidates?: Array<{ phrase?: string; score?: number } | string>;
        top_filtered?: Array<{ phrase?: string; reason?: string }>;
        split_examples?: Array<{ source?: string; added?: string[]; generated?: string[] }>;
        cv_structure_rejected_count?: number;
        cv_structure_rejected_examples?: string[];
      };
      tight_split_trace?: Array<{
        source?: string;
        generated?: string[];
        inserted?: string[];
        survived_after_filter?: string[];
        present_in_final_tight?: string[];
        present_in_mapping_inputs?: string[];
        dropped?: Array<{ chunk?: string; reason?: string }>;
      }>;
      tight_selection_trace?: Array<{
        candidate?: string;
        origin?: string;
        base_score?: number;
        adjustments?: string[];
        final_score?: number;
        selected?: boolean;
      }>;
      top_candidates_source?: string;
      mapping_inputs_source?: string;
      mapping_inputs_preview?: string[];
      noise_removed?: string[];
      split_chunks?: string[];
      split_chunks_count?: number;
      cleaned_chunks?: string[];
      cleaned_chunks_count?: number;
      lemmatized_chunks_count?: number;
      pos_rejected_count?: number;
      stage_flags?: {
        phrase_splitting?: boolean;
        chunk_normalizer?: boolean;
        light_lemmatization?: boolean;
        pos_filter?: boolean;
      };
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
        split_chunks_count?: number;
        cleaned_chunks_count?: number;
        lemmatized_chunks_count?: number;
        pos_rejected_count?: number;
        canonical_count?: number;
        unresolved_count?: number;
        expanded_count?: number;
        promoted_uri_count?: number;
        near_match_count?: number;
        noise_removed_count?: number;
        canonical_success_rate?: number;
        compass_skill_candidates?: number;
        compass_skill_rejected?: number;
        tight_single_token_count?: number;
        tight_generic_rejected_count?: number;
        tight_numeric_rejected_count?: number;
        tight_repeated_fragment_count?: number;
        tight_filtered_out_count?: number;
        tight_split_generated_count?: number;
        broken_token_repair_count?: number;
        generated_composite_rejected_count?: number;
        cv_structure_rejected_count?: number;
      };
      broken_token_repair_examples?: Array<{ from?: string; to?: string }>;
    };
  };
}) {
  const [open, setOpen] = useState(false);
  const [copyLabel, setCopyLabel] = useState("Copy Dev Debug");

  const handleCopy = async () => {
    const analyzeDev = data.analyze_dev ?? {};
    const payload = {
      counters: analyzeDev.counters ?? {},
      raw_tokens: analyzeDev.raw_extraction?.raw_tokens ?? [],
      tight_candidates: analyzeDev.tight_candidates?.items ?? [],
      tight_filtered: analyzeDev.tight_candidates?.top_filtered ?? [],
      canonical_mapping: analyzeDev.canonical_mapping ?? {},
      top_candidates: analyzeDev.tight_candidates?.top_candidates ?? [],
      top_filtered: analyzeDev.tight_candidates?.top_filtered ?? [],
    };
    const json = JSON.stringify(payload, null, 2);
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(json);
      } else {
        throw new Error("clipboard_unavailable");
      }
      setCopyLabel("Copied ✓");
      window.setTimeout(() => setCopyLabel("Copy Dev Debug"), 1500);
    } catch (err) {
      // Fallback: log the payload for manual copy
      // eslint-disable-next-line no-console
      console.log(json);
      setCopyLabel("Copied ✓");
      window.setTimeout(() => setCopyLabel("Copy Dev Debug"), 1500);
    }
  };

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
  const topCandidates =
    analyze?.tight_candidates?.top_candidates?.map((c) => {
      if (typeof c === "string") return c;
      const phrase = String(c.phrase ?? "");
      const score = typeof c.score === "number" ? c.score : null;
      if (!phrase) return null;
      return score !== null ? `${phrase} (${score})` : phrase;
    }).filter(Boolean) as string[] | undefined;
  const topFiltered =
    analyze?.tight_candidates?.top_filtered?.map((c) => {
      const phrase = String(c.phrase ?? "");
      const reason = String(c.reason ?? "");
      if (!phrase) return null;
      return reason ? `${phrase} [${reason}]` : phrase;
    }).filter(Boolean) as string[] | undefined;
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

  const splitExamples =
    analyze?.tight_candidates?.split_examples?.map((ex) => {
      const source = String(ex.source ?? "");
      // prefer `generated` (all identified sub-chunks) over `added` (only newly inserted)
      const sub = Array.isArray(ex.generated) && ex.generated.length > 0
        ? ex.generated
        : Array.isArray(ex.added) ? ex.added : [];
      const subStr = sub.join(", ");
      if (!source) return null;
      return subStr ? `${source} → ${subStr}` : source;
    }).filter(Boolean) as string[] | undefined;

  const splitTrace =
    analyze?.tight_split_trace?.map((t) => {
      const source = String(t.source ?? "");
      const generated = (t.generated ?? []).join(", ");
      const inserted = (t.inserted ?? []).join(", ");
      const survived = (t.survived_after_filter ?? t.present_in_final_tight ?? []).join(", ");
      const present = (t.present_in_mapping_inputs ?? []).join(", ");
      const dropped = (t.dropped ?? [])
        .map((d) => `${d.chunk ?? ""} [${d.reason ?? ""}]`)
        .filter(Boolean)
        .join(", ");
      if (!source) return null;
      return [
        `source: ${source}`,
        generated ? `generated: ${generated}` : "generated: —",
        inserted ? `inserted: ${inserted}` : "inserted: —",
        survived ? `survived_after_filter: ${survived}` : "survived_after_filter: —",
        present ? `present_in_mapping_inputs: ${present}` : "present_in_mapping_inputs: —",
        dropped ? `dropped: ${dropped}` : "dropped: —",
      ].join(" | ");
    }).filter(Boolean) as string[] | undefined;

  const repairExamples =
    analyze?.broken_token_repair_examples?.map((ex) => {
      const from = String(ex.from ?? "");
      const to = String(ex.to ?? "");
      if (!from || !to) return null;
      return `${from} → ${to}`;
    }).filter(Boolean) as string[] | undefined;

  const selectionTrace =
    analyze?.tight_selection_trace?.map((t) => {
      const candidate = String(t.candidate ?? "");
      if (!candidate) return null;
      const origin = String(t.origin ?? "");
      const base = typeof t.base_score === "number" ? t.base_score : Number(t.base_score ?? 0);
      const finalScore = typeof t.final_score === "number" ? t.final_score : Number(t.final_score ?? 0);
      const adjustments = Array.isArray(t.adjustments) ? t.adjustments.join(", ") : "";
      const selected = t.selected ? "selected" : "not_selected";
      return `${candidate} | ${origin} | base:${base} adj:${adjustments || "—"} final:${finalScore} | ${selected}`;
    }).filter(Boolean) as string[] | undefined;

  return (
    <section className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4">
      <div className="flex w-full items-center justify-between gap-2">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-left text-sm font-semibold text-amber-800"
        >
          <span>DEV panel (pipeline)</span>
          <span className="text-xs text-amber-700">{open ? "▲" : "▼"}</span>
        </button>
        <button
          type="button"
          onClick={handleCopy}
          className="rounded-md border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-amber-800 hover:bg-amber-50"
          title="Copy analyze_dev debug payload"
        >
          {copyLabel}
        </button>
      </div>

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
                { key: "split_chunks_count", value: String(counters.split_chunks_count ?? 0) },
                { key: "cleaned_chunks_count", value: String(counters.cleaned_chunks_count ?? 0) },
                { key: "lemmatized_chunks_count", value: String(counters.lemmatized_chunks_count ?? 0) },
                { key: "pos_rejected_count", value: String(counters.pos_rejected_count ?? 0) },
                { key: "canonical_count", value: String(counters.canonical_count ?? 0) },
                { key: "unresolved_count", value: String(counters.unresolved_count ?? 0) },
                { key: "expanded_count", value: String(counters.expanded_count ?? 0) },
                { key: "promoted_uri_count", value: String(counters.promoted_uri_count ?? 0) },
                { key: "near_match_count", value: String(counters.near_match_count ?? 0) },
                { key: "noise_removed_count", value: String(counters.noise_removed_count ?? 0) },
                { key: "canonical_success_rate", value: String(counters.canonical_success_rate ?? 0) },
                { key: "compass_skill_candidates", value: String(counters.compass_skill_candidates ?? 0) },
                { key: "compass_skill_rejected", value: String(counters.compass_skill_rejected ?? 0) },
                { key: "tight_single_token_count", value: String(counters.tight_single_token_count ?? 0) },
                { key: "tight_generic_rejected_count", value: String(counters.tight_generic_rejected_count ?? 0) },
                { key: "tight_numeric_rejected_count", value: String(counters.tight_numeric_rejected_count ?? 0) },
                { key: "tight_repeated_fragment_count", value: String(counters.tight_repeated_fragment_count ?? 0) },
                { key: "tight_filtered_out_count", value: String(counters.tight_filtered_out_count ?? 0) },
                { key: "tight_split_generated_count", value: String(counters.tight_split_generated_count ?? 0) },
                { key: "broken_token_repair_count", value: String(counters.broken_token_repair_count ?? 0) },
                { key: "generated_composite_rejected_count", value: String(counters.generated_composite_rejected_count ?? 0) },
                { key: "cv_structure_rejected_count", value: String(counters.cv_structure_rejected_count ?? 0) },
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
          {block("tight_top_candidates", topCandidates)}
          {block("tight_top_filtered", topFiltered)}
          {block("tight_split_examples", splitExamples, 20)}
          {block("top_candidates_source", analyze?.top_candidates_source ? [analyze.top_candidates_source] : [])}
          {block("mapping_inputs_source", analyze?.mapping_inputs_source ? [analyze.mapping_inputs_source] : [])}
          {block("mapping_inputs_preview", analyze?.mapping_inputs_preview, 20)}
          {block("tight_split_trace", splitTrace, 20)}
          {block("tight_selection_trace", selectionTrace, 20)}
          {block("cv_structure_rejected_examples", analyze?.tight_candidates?.cv_structure_rejected_examples, 10)}
          {block("broken_token_repair_examples", repairExamples, 20)}
          {block("split_chunks", analyze?.split_chunks)}
          {block("cleaned_chunks", analyze?.cleaned_chunks)}
          {block("noise_removed", analyze?.noise_removed)}
          {keyValueBlock("stage_flags", [
            { key: "phrase_splitting", value: String(analyze?.stage_flags?.phrase_splitting ?? false) },
            { key: "chunk_normalizer", value: String(analyze?.stage_flags?.chunk_normalizer ?? false) },
            { key: "light_lemmatization", value: String(analyze?.stage_flags?.light_lemmatization ?? false) },
            { key: "pos_filter", value: String(analyze?.stage_flags?.pos_filter ?? false) },
          ])}
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
