import { Download, X } from "lucide-react";
import type { CvHtmlResponse } from "../lib/api";

export function CvHtmlPreviewModal({
  offerTitle,
  offerCompany,
  preview,
  onClose,
}: {
  offerTitle: string;
  offerCompany?: string | null;
  preview: CvHtmlResponse;
  onClose: () => void;
}) {
  const { html, meta } = preview;

  function handleDownload() {
    // TextEncoder always produces UTF-8 bytes; passing a raw string to Blob
    // can silently downgrade to Latin-1 in some browsers, corrupting accented chars.
    const bytes = new TextEncoder().encode(html);
    const blob = new Blob([bytes], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const slug = offerTitle
      .slice(0, 40)
      .replace(/[^a-z0-9]/gi, "-")
      .toLowerCase()
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
    a.href = url;
    a.download = `cv-elevia-${slug || "offre"}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl mt-6 mx-4 bg-neutral-900 rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col border border-neutral-700"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-neutral-800">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-white truncate">CV HTML</h2>
            <p className="text-xs text-neutral-400 mt-0.5 truncate">
              {offerTitle}
              {offerCompany ? ` · ${offerCompany}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="rounded-full bg-neutral-800 px-2.5 py-1 text-xs font-medium text-neutral-300">
              {meta.template_version}
            </span>
            <button
              onClick={handleDownload}
              className="flex items-center gap-1 rounded-lg bg-neutral-700 hover:bg-neutral-600 px-3 py-1.5 text-xs font-medium text-white transition-colors"
              title="Télécharger en HTML"
            >
              <Download className="h-3 w-3" />
              .html
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

        <div className="flex-1 bg-neutral-800">
          <iframe
            title="CV HTML Preview"
            className="w-full h-full"
            sandbox=""
            srcDoc={html}
          />
        </div>
      </div>
    </div>
  );
}
