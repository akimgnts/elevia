import { Link } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { PageContainer } from "../components/layout/PageContainer";

export default function DemoPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#F0FDFE] via-white to-[#ECFDF5]">
      <PageContainer className="pt-24 pb-16 text-center">
        <h1 className="text-3xl font-bold text-slate-900 md:text-4xl">Démo Elevia</h1>
        <p className="mt-3 text-slate-600">
          Une démo rapide pour comprendre le flux et les résultats.
        </p>
        <div className="mt-8 flex justify-center gap-4">
          <Link to="/analyze">
            <Button>Essayer l'analyse</Button>
          </Link>
          <Link to="/">
            <Button variant="secondary">Retour</Button>
          </Link>
        </div>
      </PageContainer>
    </div>
  );
}
