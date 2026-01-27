import { Link } from "react-router-dom";
import { Button } from "../ui/Button";

export function Navbar() {
  return (
    <nav className="fixed left-0 right-0 top-6 z-50">
      <div className="mx-auto flex w-[min(1100px,92vw)] items-center justify-between rounded-2xl border border-slate-200 bg-white/80 px-6 py-3 backdrop-blur-md shadow-soft">
        <Link to="/" className="text-sm font-semibold text-slate-900">
          ADA Elevia
        </Link>
        <div className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
          <Link to="/#how-it-works">Comment ça marche</Link>
          <Link to="/#why-elevia">Pourquoi</Link>
          <Link to="/#pricing">Tarifs</Link>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/demo" className="hidden md:inline-flex">
            <Button variant="secondary" size="sm">
              Voir la démo
            </Button>
          </Link>
          <Link to="/analyze">
            <Button variant="primary" size="sm">
              Drop ton CV
            </Button>
          </Link>
        </div>
      </div>
    </nav>
  );
}
