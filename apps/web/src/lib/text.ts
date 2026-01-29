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

/**
 * Clean full description text for detail view.
 * Preserves paragraphs but strips HTML and normalizes spacing.
 */
export function cleanFullText(raw: string): string {
  return normalizeWhitespace(stripHtml(raw));
}

const BULLET_RE = /^[\s]*[-•*]\s+(.+)/;
const NUMBERED_RE = /^[\s]*\d+[.)]\s+(.+)/;

/**
 * Extract a named section from text.
 * Looks for lines matching any of the given headings, then collects
 * content until the next heading-like line or end of text.
 */
export function extractSection(
  text: string,
  headings: string[]
): string | null {
  const lines = text.split("\n");
  const headingsLower = headings.map((h) => h.toLowerCase());
  let capturing = false;
  const captured: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (capturing) captured.push("");
      continue;
    }

    // Detect heading-like lines (short, not a bullet)
    const isHeadingLike =
      trimmed.length < 80 &&
      !BULLET_RE.test(trimmed) &&
      !NUMBERED_RE.test(trimmed) &&
      (trimmed.endsWith(":") || trimmed.endsWith(" :") || /^[A-ZÀ-Ü]/.test(trimmed));

    if (isHeadingLike) {
      const normalized = trimmed.toLowerCase().replace(/[:#\s]+$/g, "").trim();
      if (headingsLower.some((h) => normalized.includes(h))) {
        capturing = true;
        continue;
      } else if (capturing) {
        break;
      }
    }

    if (capturing) {
      captured.push(trimmed);
    }
  }

  const result = captured
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return result || null;
}

/**
 * Extract bullet-like lines from text.
 * Matches lines starting with -, •, *, or numbered (1., 2), etc.).
 * Returns up to 8 bullets.
 */
export function extractBullets(text: string): string[] {
  const lines = text.split("\n");
  const bullets: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    const bulletMatch = BULLET_RE.exec(trimmed) || NUMBERED_RE.exec(trimmed);
    if (bulletMatch) {
      const content = bulletMatch[1].trim();
      if (content.length > 5) {
        bullets.push(content);
      }
    }
    if (bullets.length >= 8) break;
  }

  return bullets;
}

const MISSION_HEADINGS = [
  "mission",
  "missions",
  "responsabilit",
  "what you will do",
  "your role",
  "your mission",
  "activit",
  "tâches",
  "rôle",
  "descriptif",
];

/**
 * Build missions content from offer description.
 * Returns { intro, bullets } — both optional.
 */
export function buildMissions(
  displayDesc?: string | null,
  desc?: string | null
): { intro: string | null; bullets: string[] } {
  const raw = displayDesc || desc || "";
  if (!raw) return { intro: null, bullets: [] };

  const clean = cleanFullText(raw);

  // Try extracting a named section first
  const section = extractSection(clean, MISSION_HEADINGS);
  if (section) {
    const sectionBullets = extractBullets(section);
    if (sectionBullets.length >= 3) {
      return { intro: null, bullets: sectionBullets };
    }
    const introParts = section
      .split("\n")
      .filter((l) => !BULLET_RE.test(l.trim()) && !NUMBERED_RE.test(l.trim()) && l.trim().length > 10);
    return {
      intro: introParts[0] || null,
      bullets: sectionBullets,
    };
  }

  // No named section — extract bullets from entire text
  const allBullets = extractBullets(clean);
  if (allBullets.length >= 3) {
    return { intro: null, bullets: allBullets.slice(0, 8) };
  }

  // Fallback: first relevant paragraph
  const best = pickBestParagraph(clean);
  return { intro: best, bullets: [] };
}
