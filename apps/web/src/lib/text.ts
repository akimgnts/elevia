/**
 * Deterministic text helpers for offer preview descriptions.
 * No LLM — pure string transforms.
 */

const HTML_TAG_RE = /<[^>]*>/g;
const MULTI_SPACE_RE = /[ \t]+/g;
const MULTI_NEWLINE_RE = /\n{3,}/g;

export function stripHtml(input: string): string {
  return input.replace(HTML_TAG_RE, " ");
}

export function normalizeWhitespace(input: string): string {
  return input
    .replace(MULTI_SPACE_RE, " ")
    .replace(MULTI_NEWLINE_RE, "\n\n")
    .trim();
}

const PRIORITY_KEYWORDS = [
  "mission",
  "responsabilit",
  "role",
  "activit",
  "profil",
  "compétence",
  "requirement",
  "you will",
  "we are looking",
  "recherch",
  "poste",
];

export function pickBestParagraph(text: string): string {
  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter((p) => p.length > 20);

  if (paragraphs.length === 0) return text.trim();

  const lower = (s: string) => s.toLowerCase();
  for (const p of paragraphs) {
    const l = lower(p);
    if (PRIORITY_KEYWORDS.some((kw) => l.includes(kw))) {
      return p;
    }
  }

  return paragraphs[0];
}

export function truncate(text: string, maxChars = 320): string {
  if (text.length <= maxChars) return text;
  const cut = text.lastIndexOf(" ", maxChars);
  return text.slice(0, cut > 0 ? cut : maxChars) + "…";
}

export function buildOfferPreview(
  displayDesc?: string | null,
  desc?: string | null
): string {
  const raw = displayDesc || desc || "";
  if (!raw) return "";
  const clean = normalizeWhitespace(stripHtml(raw));
  const best = pickBestParagraph(clean);
  return truncate(best);
}
