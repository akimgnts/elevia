import { Download, X } from "lucide-react";
import type { ForOfferLetterResponse } from "../lib/api";

/**
 * LetterPreviewModal — deterministic cover letter preview.
 */
export function LetterPreviewModal({
  offerTitle,
  offerCompany,
  preview,
  onClose,
}: {
  offerTitle: string;
  offerCompany?: string | null;
  preview: ForOfferLetterResponse;
  onClose: () => void;
}) {
  const { document: doc, preview_text } = preview;

  function handleDownload() {
    const blob = new Blob([preview_text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const slug = offerTitle
      .slice(0, 40)
      .replace(/[^a-z0-9]/gi, "-")
      .toLowerCase()
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
    a.href = url;
    a.download = `lettre-elevia-${slug || "offre"}.md`;
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
            <h2 className="text-sm font-semibold text-white truncate">Lettre générée</h2>
            <p className="text-xs text-neutral-400 mt-0.5 truncate">
              {offerTitle}
              {offerCompany ? ` · ${offerCompany}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="rounded-full bg-neutral-800 px-2.5 py-1 text-xs font-medium text-neutral-300">
              {doc.meta.template_version}
            </span>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1 rounded-lg bg-neutral-700 hover:bg-neutral-600 px-3 py-1.5 text-xs font-medium text-white transition-colors"
              title="Télécharger en Markdown"
            >
              <Download className="h-3 w-3" />
              .md
            </button>
            <button
              onClick={onClose}
              className="rounded-lg border border-neutral-700 p-1.5 text-neutral-400 hover:text-white hover:border-neutral-500 transition-colors"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Markdown preview */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <pre className="whitespace-pre-wrap text-xs text-neutral-300 font-mono leading-relaxed">
            {preview_text}
          </pre>
        </div>
      </div>
    </div>
  );
}
