const beforeMatches = [
  {
    title: "Interior Engineering Budget/Performance",
    company: "Airbus Canada - Montréal",
    score: "100%",
  },
  {
    title: "Supply Chain Business Analyst",
    company: "Safran - Sarasota",
    score: "98%",
  },
  {
    title: "Procurement Data Analyst",
    company: "Schneider Electric - Riga",
    score: "97%",
  },
  {
    title: "Relationship Management Analyst",
    company: "Crédit Agricole - Francfort",
    score: "96%",
  },
];

const afterMatches = [
  {
    title: "VIE Business Analyst",
    company: "Pernod Ricard - Stockholm",
    score: "87%",
  },
  {
    title: "Growth Marketing Analyst",
    company: "Papernest - Barcelone",
    score: "82%",
  },
  {
    title: "Business Analyst",
    company: "Schneider Electric - Oslo",
    score: "79%",
  },
  {
    title: "Business Analyst",
    company: "Richemont - New Delhi",
    score: "75%",
  },
];

function MatchList({
  label,
  title,
  items,
  tone,
}: {
  label: string;
  title: string;
  items: Array<{ title: string; company: string; score: string }>;
  tone: "before" | "after";
}) {
  const isAfter = tone === "after";

  return (
    <section
      className={[
        "rounded-3xl border p-8 shadow-sm",
        isAfter
          ? "border-emerald-200 bg-emerald-50"
          : "border-rose-200 bg-rose-50",
      ].join(" ")}
    >
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <p
            className={[
              "text-sm font-semibold uppercase tracking-[0.18em]",
              isAfter ? "text-emerald-700" : "text-rose-700",
            ].join(" ")}
          >
            {label}
          </p>
          <h2 className="mt-2 text-3xl font-bold text-slate-950">{title}</h2>
        </div>
        <div
          className={[
            "rounded-full px-4 py-2 text-sm font-bold",
            isAfter
              ? "bg-emerald-100 text-emerald-800"
              : "bg-rose-100 text-rose-800",
          ].join(" ")}
        >
          {isAfter ? "Réaliste" : "Biaisé"}
        </div>
      </div>

      <div className="space-y-4">
        {items.map((item) => (
          <div
            key={item.title}
            className="flex min-h-24 items-center justify-between gap-5 rounded-2xl bg-white px-5 py-4 shadow-sm"
          >
            <div>
              <p className="text-xl font-semibold text-slate-900">
                {item.title}
              </p>
              <p className="mt-1 text-base font-medium text-slate-500">
                {item.company}
              </p>
            </div>
            <span
              className={[
                "text-2xl font-black",
                isAfter ? "text-emerald-700" : "text-rose-700",
              ].join(" ")}
            >
              {item.score}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function MatchingShowcasePage() {
  return (
    <main className="min-h-screen bg-slate-100 px-6 py-12 text-slate-950">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <header className="text-center">
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">
            Profil Akim Guentas
          </p>
          <h1 className="text-5xl font-black tracking-tight text-slate-950 md:text-6xl">
            Matching VIE : avant vs après
          </h1>
        </header>

        <div className="rounded-3xl border border-slate-200 bg-white px-8 py-5 text-center shadow-sm">
          <p className="text-2xl font-bold text-slate-950">
            Avant : scores gonflés sur des offres réelles
            <span className="mx-4 text-slate-300">|</span>
            Après : classement réaliste pour le profil
          </p>
          <p className="mt-2 text-sm font-semibold uppercase tracking-[0.16em] text-slate-500">
            Snapshot public VIE - offres figées pour capture LinkedIn
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <MatchList
            label="Ancien matching"
            title="❌ Avant"
            items={beforeMatches}
            tone="before"
          />
          <MatchList
            label="Nouveau matching"
            title="✅ Après"
            items={afterMatches}
            tone="after"
          />
        </div>
      </div>
    </main>
  );
}
