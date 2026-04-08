import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { useAuth } from "../hooks/useAuth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, user } = useAuth();
  const redirectTarget = useMemo(() => {
    const from = (location.state as { from?: string } | null)?.from;
    return from && from.startsWith("/") ? from : "/analyze";
  }, [location.state]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connexion impossible");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isAuthenticated && user) {
    return <Navigate to={redirectTarget} replace />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(6,182,212,0.14),_transparent_30%),radial-gradient(circle_at_bottom_right,_rgba(132,204,22,0.12),_transparent_28%),#f8fafc] px-4 py-10 text-slate-900">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 lg:flex-row lg:items-stretch">
        <section className="flex-1 rounded-[32px] border border-white/60 bg-slate-950 px-8 py-10 text-white shadow-[0_30px_80px_rgba(15,23,42,0.22)]">
          <div className="max-w-xl">
            <Link
              to="/landing"
              className="inline-flex items-center rounded-full border border-white/15 px-3 py-1 text-xs font-medium uppercase tracking-[0.22em] text-cyan-200/90"
            >
              Retour landing
            </Link>
            <p className="mt-8 text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300/90">
              Elevia Access
            </p>
            <h1 className="mt-4 max-w-lg text-4xl font-semibold tracking-tight text-white md:text-5xl">
              Connexion privee a l&apos;espace Elevia.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-slate-300">
              Connecte-toi avec ton compte admin Elevia pour retrouver ton
              profil et tes donnees persistantes. La landing et
              l&apos;exploration restent ouvertes sans login.
            </p>

            <div className="mt-10 grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Scope
                </p>
                <p className="mt-2 text-sm text-slate-200">
                  Session persistante et actions personnelles reliees au compte.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
                  Etat
                </p>
                <p className="mt-2 text-sm text-slate-200">
                  MVP local avec un seul compte admin a creer au seed.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="w-full max-w-xl rounded-[32px] border border-slate-200 bg-white/90 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">
                Login
              </p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                Se connecter
              </h2>
            </div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              MVP access
            </div>
          </div>

          <form className="mt-10 space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">
                Email
              </span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="akim@elevia.fr"
                autoComplete="email"
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-cyan-400 focus:bg-white focus:ring-4 focus:ring-cyan-100"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-medium text-slate-700">
                Mot de passe
              </span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••••••"
                autoComplete="current-password"
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-cyan-400 focus:bg-white focus:ring-4 focus:ring-cyan-100"
              />
            </label>

            <Button className="w-full" size="lg" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Connexion..." : "Continuer"}
            </Button>
          </form>

          <div className={`mt-6 rounded-2xl px-4 py-3 text-sm ${
            error
              ? "border border-rose-200 bg-rose-50 text-rose-900"
              : "border border-cyan-200 bg-cyan-50 text-cyan-900"
          }`}>
            {error ?? "Entre ton email admin et ton mot de passe pour ouvrir la session Elevia."}
          </div>

          <div className="mt-8 flex items-center justify-between gap-4 border-t border-slate-200 pt-6 text-sm text-slate-500">
            <span>Acces prive Elevia</span>
            <Link className="font-medium text-slate-900 hover:text-cyan-700" to="/landing">
              Revenir a la landing
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
