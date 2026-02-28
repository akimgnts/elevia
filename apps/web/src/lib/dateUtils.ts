type Freshness = "new" | "recent" | "old";

export function formatRelativeDate(
  publication_date: string
): { label: string; freshness: Freshness } {
  if (!publication_date) {
    return { label: "Date inconnue", freshness: "old" };
  }
  const parsed = new Date(publication_date);
  if (Number.isNaN(parsed.getTime())) {
    return { label: "Date inconnue", freshness: "old" };
  }

  const now = new Date();
  const diffMs = Math.max(0, now.getTime() - parsed.getTime());
  const diffHours = diffMs / (1000 * 60 * 60);
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  let label = "Aujourd\u2019hui";
  if (diffDays === 1) {
    label = "Il y a 1 jour";
  } else if (diffDays > 1) {
    label = `Il y a ${diffDays} jours`;
  }

  let freshness: Freshness = "old";
  if (diffHours < 48) {
    freshness = "new";
  } else if (diffDays < 7) {
    freshness = "recent";
  }

  return { label, freshness };
}
