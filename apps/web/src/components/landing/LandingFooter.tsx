import { Link } from "react-router-dom";
import { PageContainer } from "../layout/PageContainer";
import { layout, typography } from "../../styles/uiTokens";

export function LandingFooter() {
  return (
    <footer className={`border-t border-gray-100 bg-white ${layout.section}`}>
      <PageContainer>
        <div className="grid gap-8 md:grid-cols-3">
          <div>
            <div className="text-sm font-semibold text-slate-900">ADA Elevia</div>
            <p className={`mt-2 ${typography.body}`}>
              Le copilote IA pour révéler vos opportunités V.I.E.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <div className="text-sm font-semibold text-slate-900">Produit</div>
            <Link to="/analyse" className={typography.body}>Analyse</Link>
            <Link to="/demo" className={typography.body}>Démo</Link>
            <Link to="/offres" className={typography.body}>Offres</Link>
          </div>
          <div className="flex flex-col gap-2">
            <div className="text-sm font-semibold text-slate-900">Légal</div>
            <Link to="/mentions-legales" className={typography.body}>Mentions légales</Link>
            <Link to="/confidentialite" className={typography.body}>Confidentialité</Link>
          </div>
        </div>
      </PageContainer>
    </footer>
  );
}
