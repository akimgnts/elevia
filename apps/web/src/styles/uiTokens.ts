/**
 * UI Tokens for Apple-clean design system
 * Single source of truth for layout, typography, and card styles
 */

// Layout tokens
export const layout = {
  /** Main container: max-w-6xl for calmer rhythm */
  container: "mx-auto w-full max-w-6xl px-4 md:px-6",
  /** Section vertical spacing */
  section: "py-12 md:py-16",
  /** Grid gaps */
  gridGap: "gap-4 md:gap-6",
} as const;

// Typography tokens (Apple-clean scale)
export const typography = {
  /** H1: Hero headlines */
  h1: "text-4xl md:text-5xl font-semibold tracking-tight leading-[1.05] text-slate-900",
  /** Lead: Hero subtext */
  lead: "text-base md:text-lg text-gray-600 leading-relaxed max-w-2xl",
  /** H2: Section headlines */
  h2: "text-2xl md:text-3xl font-semibold text-slate-900",
  /** H3: Card/block titles */
  h3: "text-xl md:text-2xl font-semibold text-slate-900",
  /** Body text */
  body: "text-sm md:text-base text-gray-600",
  /** Small labels */
  label: "text-sm font-medium text-slate-500",
  /** Tiny captions */
  caption: "text-xs text-slate-500",
} as const;

// Card tokens (unified card system)
export const card = {
  /** Base card: clean, minimal borders */
  base: "bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md transition-shadow p-6 md:p-8",
  /** Hero card: slightly larger radius */
  hero: "bg-white border border-gray-100 rounded-3xl shadow-sm hover:shadow-md transition-shadow p-6 md:p-8",
  /** Flat card: no shadow, just border */
  flat: "bg-white border border-gray-100 rounded-2xl p-6 md:p-8",
  /** Subtle: softer border for less emphasis */
  subtle: "bg-white/80 border border-gray-50 rounded-2xl shadow-sm p-5 md:p-6",
} as const;

// Button tokens
export const button = {
  /** Primary CTA with brand gradient */
  primary: "rounded-xl bg-gradient-to-r from-[#06B6D4] to-[#22C55E] px-6 py-3 text-sm font-semibold text-white shadow-sm hover:shadow-md transition-shadow",
  /** Secondary button */
  secondary: "rounded-xl border border-gray-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-gray-50 transition-colors",
} as const;

// Badge tokens
export const badge = {
  /** Brand badge with gradient */
  brand: "rounded-full bg-gradient-to-r from-[#06B6D4] to-[#22C55E] px-3 py-1 text-xs font-semibold text-white",
  /** Neutral badge */
  neutral: "rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-slate-600",
  /** Subtle badge */
  subtle: "rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm",
} as const;

// Spacing helpers
export const spacing = {
  /** Section title to content */
  titleGap: "mt-8 md:mt-10",
  /** Between elements in a group */
  itemGap: "mt-4",
  /** Hero top padding (accounts for fixed navbar) */
  heroTop: "pt-24 md:pt-32",
} as const;
