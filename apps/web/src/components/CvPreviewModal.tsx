import { Download, X } from "lucide-react";
import type { ForOfferResponse } from "../lib/api";

/**
 * CvPreviewModal — displays the generated CV preview and enables download.
 *
 * Rendered on top of OfferDetailModal (z-[60]).
 * Download format: UTF-8 Markdown (.md).
 */
export function CvPreviewModal({
  offerTitle,
  offerCompany,
  preview,
  onClose,
}: {
  offerTitle: string;
  offerCompany?: string | null;
  preview: ForOfferResponse;
  onClose: () => void;
}) {
  const { document: doc, preview_text, context_used } = preview;
  const sanitizedPreview = preview_text.includes("## ATS")
    ? preview_text.split("## ATS")[0].trimEnd()
    : preview_text;

  function handleDownload() {
    const blob = new Blob([sanitizedPreview], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const slug = offerTitle
      .slice(0, 40)
      .replace(/[^a-z0-9]/gi, "-")
      .toLowerCase()
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
    a.href = url;
    a.download = `cv-elevia-${slug || "offre"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl mt-8 mx-4 bg-neutral-900 rounded-2xl shadow-2xl overflow-hidden max-h-[85vh] flex flex-col border border-neutral-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-neutral-800">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-white truncate">CV généré</h2>
            <p className="text-xs text-neutral-400 mt-0.5 truncate">
              {offerTitle}
              {offerCompany ? ` · ${offerCompany}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {/* Context-used badge */}
            {context_used && (
              <span className="rounded-full bg-emerald-500/15 border border-emerald-500/25 px-2.5 py-1 text-xs text-emerald-300">
                Contexte inbox
              </span>
            )}
            {/* Fallback badge */}
            {doc.meta.fallback_used && (
              <span className="rounded-full bg-amber-500/15 border border-amber-500/25 px-2.5 py-1 text-xs text-amber-300">
                Fallback
              </span>
            )}
            {/* Download */}
            <button
              onClick={handleDownload}
              className="flex items-center gap-1 rounded-lg bg-neutral-700 hover:bg-neutral-600 px-3 py-1.5 text-xs font-medium text-white transition-colors"
              title="Télécharger en Markdown"
            >
              <Download className="h-3 w-3" />
              .md
            </button>
            {/* Close */}
            <button
              onClick={onClose}
              className="rounded-lg border border-neutral-700 p-1.5 text-neutral-400 hover:text-white hover:border-neutral-500 transition-colors"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Keywords strip */}
        {doc.keywords_injected.length > 0 && (
          <div className="px-5 py-2.5 border-b border-neutral-800 flex flex-wrap gap-1.5">
            {doc.keywords_injected.map((kw, i) => (
              <span
                key={`${kw}-${i}`}
                className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 text-xs text-emerald-300"
              >
                {kw}
              </span>
            ))}
          </div>
        )}

        {/* Markdown preview */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <pre className="whitespace-pre-wrap text-xs text-neutral-300 font-mono leading-relaxed">
            {sanitizedPreview}
          </pre>
        </div>
      </div>
    </div>
  );
}
