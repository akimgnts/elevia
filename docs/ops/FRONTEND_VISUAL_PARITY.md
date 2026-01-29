# Frontend Visual Parity Checklist

Objectif : vérifier la parité visuelle avec le design system **ADA Elevia V9 / Next Horizon+**.

## Route `/` (Home)
- Hero V8 : badge + headline gradient + CTA primaire/secondaire + 4 HeroCards.
- 7 sections présentes : Hero, HowItWorks, WhyEleviaWorks (bento 4 blocs), RecommendedOffers, Testimonials, LiveDemo, FinalCTA.
- Glassmorphisme visible sur cards (bg-white/90 + backdrop-blur + border).
- Spacing global : `pt-32 md:pt-40` pour le hero, sections `py-16 md:py-20`.

## Route `/dashboard`
- Bento layout : KPIs en grille + bloc radar marché + bloc insights IA.
- Cards KPI avec delta (cyan/lime) et shadow soft.
- Bloc “Top matches” listant 2 OfferCards avec badges de score.
- Palette cyan/lime + neutrals slate cohérente.

## Route `/offres`
- Barre de filtres (search + select) en card glassmorphism.
- Grille d’OfferCards (2 colonnes desktop, 1 colonne mobile).
- Badges score avec logique matching (excellent/good/medium/low).

## Route `/analyze`
- Carte principale glassmorphism avec textarea stylée (focus ring cyan).
- CTA gradient primaire + message de contrôle des données.
- Ton visuel premium (shadow soft + border slate-200).

## Tokens & Foundations
- Inter variable activée, weights 400/500/600/700.
- Tailwind palette : cyan/lime + neutres slate + shadows custom.
- `theme.css` chargé (btn-primary, card-boost, gradient-text).
- Animations framer-motion disponibles (`fadeInUp`, `staggerContainer`, etc.).
