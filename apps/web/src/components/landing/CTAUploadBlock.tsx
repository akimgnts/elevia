import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageContainer } from "../layout/PageContainer";

export function CTAUploadBlock() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const handlePick = () => {
    inputRef.current?.click();
  };

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setTimeout(() => navigate("/analyse"), 800);
  };

  return (
    <section className="bg-gradient-to-b from-[#F0FDFE] via-white to-[#ECFDF5] py-16 md:py-20">
      <PageContainer>
        <div className="rounded-3xl border border-white/40 bg-white/80 p-8 shadow-[0_4px_25px_rgba(0,0,0,0.05)] backdrop-blur-xl">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-2xl font-bold text-slate-900">Drop ton CV</h3>
              <p className="mt-2 text-slate-600">
                PDF ou DOCX. Tu gardes le contrôle, aucun envoi automatique.
              </p>
              {fileName && (
                <div className="mt-3 text-sm font-semibold text-slate-600">
                  Fichier sélectionné : {fileName}
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={handlePick}
                className="rounded-xl bg-gradient-to-r from-[#06B6D4] to-[#22C55E] px-8 py-3 text-sm font-semibold text-white shadow-md"
              >
                Drop ton CV
              </button>
              <button
                onClick={() => navigate("/demo")}
                className="rounded-xl border border-slate-200 bg-white/80 px-5 py-3 text-sm font-semibold text-slate-700"
              >
                Voir une démo
              </button>
            </div>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={handleChange}
          />
        </div>
      </PageContainer>
    </section>
  );
}
