import { Link } from "react-router-dom";
import { PageContainer } from "./PageContainer";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white/70 py-12">
      <PageContainer className="grid gap-8 md:grid-cols-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">ADA Elevia</div>
          <p className="mt-2 text-sm text-slate-600">
            Le copilote IA pour révéler vos opportunités V.I.E.
          </p>
        </div>
        <div className="space-y-2 text-sm text-slate-600">
          <div className="font-semibold text-slate-900">Produit</div>
          <Link to="/offres">Offres</Link>
          <Link to="/analyze">Analyse</Link>
          <Link to="/dashboard">Dashboard</Link>
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
