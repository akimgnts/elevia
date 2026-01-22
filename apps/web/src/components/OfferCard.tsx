type OfferCardProps = {
  title?: string;
  company?: string;
  country?: string;
  score?: string;
};

export default function OfferCard({
  title,
  company,
  country,
  score,
}: OfferCardProps) {
  return (
    <div
      style={{
        padding: 16,
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        background: "white",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontWeight: 600 }}>{title ?? "Titre non renseigné"}</div>
          <div style={{ fontSize: 14, opacity: 0.8 }}>
            {company ?? "Entreprise"} — {country ?? "Pays"}
          </div>
        </div>

        <div
          style={{
            fontWeight: 700,
            color: "#2563eb",
            fontSize: 16,
          }}
        >
          {score ?? "—"}
        </div>
      </div>
    </div>
  );
}

