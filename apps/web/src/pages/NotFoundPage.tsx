import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { PageContainer } from "../components/layout/PageContainer";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <PageContainer className="pt-24 pb-16 text-center">
        <div className="text-6xl font-bold text-slate-200">404</div>
        <h1 className="mt-4 text-2xl font-bold text-slate-900">Page introuvable</h1>
        <p className="mt-2 text-slate-600">La page demandée n'existe pas ou a été déplacée.</p>
        <div className="mt-6 flex justify-center">
          <Link to="/">
            <Button>Retour à l'accueil</Button>
          </Link>
        </div>
      </PageContainer>
    </div>
  );
}
