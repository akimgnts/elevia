import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageContainer } from "../layout/PageContainer";
import { layout, typography, card, button } from "../../styles/uiTokens";

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
    setTimeout(() => navigate("/analyze"), 800);
  };

  return (
    <section className={layout.section}>
      <PageContainer>
        <div className={card.hero}>
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className={typography.h3}>Drop ton CV</h3>
              <p className={`mt-2 ${typography.body}`}>
                PDF ou DOCX. Tu gardes le contrôle, aucun envoi automatique.
              </p>
              {fileName && (
                <div className="mt-3 text-sm font-semibold text-emerald-600">
                  Fichier sélectionné : {fileName}
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              <button onClick={handlePick} className={button.primary}>
                Drop ton CV
              </button>
              <button onClick={() => navigate("/demo")} className={button.secondary}>
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
