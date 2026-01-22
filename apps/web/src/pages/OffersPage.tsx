import { useEffect, useState } from "react";
import { getOffers } from "../services/offers.service";
import type { Offer } from "../types/offer";
import { Card } from "../components/ui/card";
import { ScoreBadge } from "../components/ui/badge";

export default function OffersPage() {
  const [offers, setOffers] = useState<Offer[]>([]);

  useEffect(() => {
    getOffers().then(setOffers);
  }, []);

  return (
    <div style={{ padding: 24 }}>
      <h1>Offres (mock)</h1>

      <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
        {offers.map((o) => (
          <Card key={o.id} className="flex items-center justify-between">
            <div>
              <div className="text-slate-50 font-medium">{o.title}</div>
              <div className="text-slate-400 text-sm">
                {o.company} — {o.country}
              </div>
            </div>
            <ScoreBadge score={o.score} />
          </Card>
        ))}
      </div>
    </div>
  );
}

