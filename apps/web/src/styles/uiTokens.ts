/**
 * UI Tokens for Apple-clean design system
 * Single source of truth for layout, typography, and card styles
 *
 * Design intent: calm, minimal, spacious, professional
 * Reference: Apple, Linear, Notion marketing pages
 */

// Layout tokens
export const layout = {
  /** Main container: max-w-6xl for calmer rhythm */
  container: "mx-auto w-full max-w-6xl px-4 md:px-6",
  /** Section vertical spacing */
  section: "py-12 md:py-16",
  /** Grid gaps */
  gridGap: "gap-4 md:gap-6",
  /** Page background */
  pageBg: "bg-surface-muted",
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
  /** Overline: small category labels */
  overline: "text-sm font-semibold text-slate-500 tracking-wide",
} as const;

// Card tokens (unified card system)
export const card = {
  /** Base card: clean, minimal borders */
  base: "bg-white border border-slate-100 rounded-card shadow-card hover:shadow-sm transition-shadow",
  /** Hero card: slightly larger radius */
  hero: "bg-white border border-slate-100 rounded-2xl shadow-card hover:shadow-sm transition-shadow",
  /** Flat card: no shadow, just border */
  flat: "bg-white border border-slate-100 rounded-card",
  /** Subtle: softer appearance */
  subtle: "bg-white/80 border border-slate-50 rounded-card shadow-xs",
  /** Interactive: lift on hover */
  interactive: "bg-white border border-slate-100 rounded-card shadow-card hover:shadow-md hover:-translate-y-0.5 transition-all duration-200",
} as const;

// Card padding (separate for flexibility)
export const cardPadding = {
  sm: "p-4",
  md: "p-5 md:p-6",
  lg: "p-6 md:p-8",
} as const;

// Button tokens
export const button = {
  /** Primary CTA with brand gradient */
  primary: "rounded-button bg-gradient-to-r from-brand-cyan to-brand-lime px-6 py-3 text-sm font-semibold text-white shadow-sm hover:shadow-md transition-shadow",
  /** Secondary button */
  secondary: "rounded-button border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors",
  /** Ghost: minimal presence */
  ghost: "rounded-button px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors",
} as const;

// Badge tokens
export const badge = {
  /** Brand badge with gradient */
  brand: "rounded-full bg-gradient-to-r from-brand-cyan to-brand-lime px-3 py-1 text-xs font-semibold text-white",
  /** Neutral badge */
  neutral: "rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600",
  /** Subtle badge */
  subtle: "rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-slate-600 shadow-xs",
} as const;

// Spacing helpers
export const spacing = {
  /** Section title to content */
  titleGap: "mt-8 md:mt-10",
  /** Between elements in a group */
  itemGap: "mt-4",
  /** Stack spacing within cards */
  stack: "space-y-4",
  /** Hero top padding (accounts for fixed navbar) */
  heroTop: "pt-24 md:pt-32",
  /** Page top padding (standard pages) */
  pageTop: "pt-10 pb-16",
} as const;
