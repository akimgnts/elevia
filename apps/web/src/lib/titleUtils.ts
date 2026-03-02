export type CleanTitleResult = {
  display: string;
  original: string;
  changes: string[];
};

const PREFIX_RE = /^(?:\s*(?:V\.?\s?I\.?\s?E\.?|VIE|Volontariat\s+International)\s*[:\-–—]?\s*)+/i;
const SUFFIX_GENDER_RE = /\s*(?:\((?:H\/F|F\/H|M\/F)\)|(?:H\/F|F\/H|M\/F))\s*$/i;
const SUFFIX_REF_BRACKET_RE = /\s*\[\s*ref[:\s#-]*[^\]]+\]\s*$/i;
const SUFFIX_REF_RE = /\s*ref[:\s#-]*[^\s]+\s*$/i;
const ACRONYM_TOKENS = new Set(["SQL", "SAP", "AWS", "BI", "CRM", "VIE", "API", "UX", "UI", "ETL", "CDI", "CDD"]);
const LOWERCASE_TOKENS = new Set(["de", "du", "des", "la", "le", "les", "et", "en", "d", "l", "au", "aux", "pour", "sur", "chez"]);

function normalizeWhitespace(input: string) {
  return input.replace(/\s+/g, " ").trim();
}

function normalizeSeparators(input: string) {
  let value = input;
  value = value.replace(/\s*\|\s*/g, " — ");
  value = value.replace(/\s+\/\s+/g, " — ");
  value = value.replace(/\s+[-–—]\s+/g, " — ");
  value = value.replace(/[-–—]{2,}/g, " — ");
  value = value.replace(/\s*—\s*/g, " — ");
  value = value.replace(/(?:\s+—\s+)+/g, " — ");
  value = value.replace(/\s+—\s+$/, "");
  return normalizeWhitespace(value);
}

function stripSuffixes(input: string) {
  let value = input;
  value = value.replace(SUFFIX_GENDER_RE, "");
  value = value.replace(SUFFIX_REF_BRACKET_RE, "");
  value = value.replace(SUFFIX_REF_RE, "");
  return normalizeWhitespace(value);
}

function isMostlyUppercase(input: string) {
  const letters = input.match(/[A-Za-zÀ-ÖØ-öø-ÿ]/g) || [];
  if (letters.length === 0) return false;
  const uppercaseCount = letters.filter((ch) => ch === ch.toUpperCase() && ch !== ch.toLowerCase()).length;
  return uppercaseCount / letters.length >= 0.7;
}

function isAcronymToken(token: string) {
  const lettersOnly = token.replace(/[^A-Za-zÀ-ÖØ-öø-ÿ]/g, "");
  if (!lettersOnly) return false;
  const isUpper = lettersOnly === lettersOnly.toUpperCase();
  if (!isUpper) return false;
  if (lettersOnly.length <= 5) return true;
  return /[&./]/.test(token);
}

function toSentenceCase(input: string) {
  const tokens = input.split(" ");
  const normalized = tokens.map((token) => {
    if (!token) return token;
    if (token === "—") return token;
    if (isAcronymToken(token)) return token.toUpperCase();
    return token.toLowerCase();
  });

  let sentence = normalized.join(" ");
  sentence = sentence.replace(/^\s*([A-Za-zÀ-ÖØ-öø-ÿ])/i, (match, chr) => {
    return match.replace(chr, chr.toUpperCase());
  });
  return sentence;
}

function toSmartTitleCase(input: string) {
  const tokens = input.split(" ");
  return tokens
    .map((token, index) => {
      if (!token || token === "—") return token;
      const core = token.replace(/^[^A-Za-zÀ-ÖØ-öø-ÿ0-9]+|[^A-Za-zÀ-ÖØ-öø-ÿ0-9]+$/g, "");
      if (!core) return token;
      const upperCore = core.toUpperCase();
      if (ACRONYM_TOKENS.has(upperCore)) {
        return token.replace(core, upperCore);
      }
      const hasLower = /[a-zà-öø-ÿ]/.test(core);
      const hasUpper = /[A-ZÀ-ÖØ-öø-ÿ]/.test(core);
      if (hasLower && hasUpper) {
        return token;
      }
      const lowerCore = core.toLowerCase();
      if (index > 0 && LOWERCASE_TOKENS.has(lowerCore)) {
        return token.replace(core, lowerCore);
      }
      const titleCore = lowerCore.charAt(0).toUpperCase() + lowerCore.slice(1);
      return token.replace(core, titleCore);
    })
    .join(" ");
}

export function truncateOfferTitle(value: string, maxLen = 90) {
  if (!value) return value;
  if (value.length <= maxLen) return value;
  return `${value.slice(0, maxLen).trimEnd()}…`;
}

export function cleanOfferTitle(raw: string): CleanTitleResult {
  const original = typeof raw === "string" ? raw : "";
  const changes: string[] = [];

  let value = typeof raw === "string" ? raw : "";
  const normalizedOriginal = normalizeWhitespace(value);
  if (normalizedOriginal !== value) changes.push("normalize_whitespace");
  value = normalizedOriginal;

  const withoutPrefix = value.replace(PREFIX_RE, "");
  if (withoutPrefix !== value) changes.push("remove_prefix");
  value = normalizeWhitespace(withoutPrefix);

  const normalizedSeparators = normalizeSeparators(value);
  if (normalizedSeparators !== value) changes.push("normalize_separators");
  value = normalizedSeparators;

  const withoutSuffix = stripSuffixes(value);
  if (withoutSuffix !== value) changes.push("remove_suffix");
  value = withoutSuffix;

  if (isMostlyUppercase(value)) {
    const sentence = toSentenceCase(value);
    if (sentence !== value) changes.push("sentence_case");
    value = sentence;
  }

  const smartCased = toSmartTitleCase(value);
  if (smartCased !== value) changes.push("smart_title_case");
  value = smartCased;

  if (!value) {
    value = normalizedOriginal || original;
  }

  return {
    display: value,
    original: normalizedOriginal || original,
    changes,
  };
}
