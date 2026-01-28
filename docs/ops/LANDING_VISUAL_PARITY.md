# Landing Page Visual Parity Checklist

This document tracks visual consistency for the landing page (`/`) as the reference implementation for Elevia's design system.

## Design Tokens Applied

| Token Category | Applied | Notes |
|----------------|---------|-------|
| `layout.section` | Yes | All sections use `py-12 md:py-16` |
| `layout.container` | Yes | Via `PageContainer` |
| `layout.gridGap` | Yes | `gap-4 md:gap-6` |
| `typography.h1` | Yes | Hero headline |
| `typography.h2` | Yes | Section headlines |
| `typography.h3` | Yes | Card/CTA titles |
| `typography.lead` | Yes | Hero subtext |
| `typography.body` | Yes | Body text |
| `typography.label` | Yes | Small labels |
| `typography.caption` | Yes | Tiny captions |
| `card.base` | Yes | Standard cards |
| `card.hero` | Yes | CTA blocks |
| `card.subtle` | Yes | WhyElevia points |
| `cardPadding.sm/md/lg` | Yes | All cards have explicit padding |
| `button.primary` | Yes | Primary CTAs |
| `button.secondary` | Yes | Secondary CTAs |
| `badge.brand` | Yes | Highlight badges |
| `badge.neutral` | Yes | Tag badges |
| `spacing.heroTop` | Yes | Hero section top padding |

## Component Checklist

### LandingPage.tsx
- [x] Uses `bg-gradient-to-b from-surface-muted to-white`
- [x] `HeroVisualLayer` for global aurora
- [x] Lazy-loaded `Testimonials` and `PricingSection`
- [x] Consistent `SectionFallback` component

### HeroSection.tsx
- [x] Uses `spacing.heroTop` for navbar clearance
- [x] Two-column bento layout on desktop
- [x] `badge.subtle` for top tag
- [x] `typography.h1` for headline
- [x] `typography.lead` for subtext
- [x] `button.primary` and `button.secondary` for CTAs

### HeroCardsGroup.tsx
- [x] Bento grid layout (featured card spans 2 cols)
- [x] Motion animation on load

### HeroCard.tsx
- [x] Uses `card.base` / `card.hero` + `cardPadding.md` / `cardPadding.lg`
- [x] `badge.brand` for highlight badge
- [x] `badge.neutral` for tags
- [x] Hover lift animation (`y: -3`)
- [x] Brand color for CTA link

### KPISection.tsx
- [x] Inline KPIs with `typography.caption`
- [x] Clean value/label pairing

### HowItWorks.tsx
- [x] Centered header with `typography.h2`
- [x] Three-column grid on desktop
- [x] Step numbers in `text-brand-cyan`
- [x] Cards use `card.base` + `cardPadding.md`

### CTAUploadBlock.tsx
- [x] Uses `card.hero` + `cardPadding.lg`
- [x] Flex layout for responsive CTA buttons
- [x] File selection feedback in `text-brand-lime`

### WhyElevia.tsx
- [x] Two-column layout
- [x] Header with `typography.h2` and `typography.lead`
- [x] Points use `card.subtle` + `cardPadding.sm`

### Testimonials.tsx
- [x] Centered header
- [x] Three-column grid
- [x] Avatar with brand gradient
- [x] Cards use `card.base` + `cardPadding.md`
- [x] Blockquote for quotes

### PricingSection.tsx
- [x] Centered header
- [x] Three-column pricing grid
- [x] Highlight ring on Pro plan (`ring-brand-cyan/20`)
- [x] Checkmarks in `text-brand-lime`
- [x] Bottom CTA card with `card.hero` + `cardPadding.lg`

### LandingFooter.tsx
- [x] Border-top separator
- [x] Three-column footer grid
- [x] Uses `layout.section` for vertical spacing
- [x] Links use `typography.body`

## Visual Rhythm Rules

1. **Section spacing**: `py-12 md:py-16` for all sections
2. **Grid gaps**: `gap-4 md:gap-6` between cards
3. **Card padding**:
   - Small: `p-4`
   - Medium: `p-5 md:p-6`
   - Large: `p-6 md:p-8`
4. **Typography scale**: h1 > h2 > h3 > body > caption
5. **Brand colors**: `brand-cyan` for accents, `brand-lime` for success

## Brand Colors

- Primary gradient: `from-brand-cyan to-brand-lime`
- Accent: `brand-cyan` (#06B6D4)
- Success: `brand-lime` (#22C55E)
- Neutral: `slate-*` scale

## Verification

To verify visual parity:

1. Run `npm run dev` and navigate to `/`
2. Check each section against this checklist
3. Verify responsive behavior at mobile/tablet/desktop
4. Confirm all cards have visible padding
5. Confirm all text uses token classes

---

Last updated: 2026-01-28
