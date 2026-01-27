import { Link } from "react-router-dom";
import { PageContainer } from "../layout/PageContainer";

export function LandingFooter() {
  return (
    <footer className="bg-gradient-to-b from-[#ECFDF5] via-white to-[#FFFFFF] py-12">
      <PageContainer className="grid gap-8 md:grid-cols-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">ADA Elevia</div>
          <p className="mt-2 text-sm text-slate-600">
            Le copilote IA pour révéler vos opportunités V.I.E.
          </p>
        </div>
        <div className="space-y-2 text-sm text-slate-600">
          <div className="font-semibold text-slate-900">Produit</div>
          <Link to="/analyse">Analyse</Link>
          <Link to="/demo">Démo</Link>
          <Link to="/offres">Offres</Link>
        </div>
        <div className="space-y-2 text-sm text-slate-600">
          <div className="font-semibold text-slate-900">Légal</div>
          <Link to="/mentions-legales">Mentions légales</Link>
          <Link to="/confidentialite">Confidentialité</Link>
        </div>
      </PageContainer>
    </footer>
  );
}
