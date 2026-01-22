import type { Offer } from "../types/offer";
import OFFERS from "./mocks/offers.json";

export async function getOffers(): Promise<Offer[]> {
  // petit délai pour simuler une API
  await new Promise((r) => setTimeout(r, 200));
  return OFFERS as Offer[];
}

export async function getOfferById(id: string): Promise<Offer | null> {
  const offers = await getOffers();
  return offers.find((o) => o.id === id) ?? null;
}

