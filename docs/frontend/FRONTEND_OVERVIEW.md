# Frontend Overview — Version Consolidée

**Date du rapport** : 2025-12-09
**Heure du rapport** : 14:58 UTC
**Durée estimée du travail IA** : ~20 minutes de reconstitution et analyse approfondie

---

## 1. Stack Frontend Actuelle

### Technologies Core

| Catégorie | Technologie | Version | Rôle |
|-----------|-------------|---------|------|
| **Framework** | React | 18.3.1 | UI library |
| **Language** | TypeScript | 5.5.3 | Type safety |
| **Build Tool** | Vite | 5.4.2 | Dev server + bundler |
| **Routing** | React Router DOM | 7.9.4 | Navigation |
| **Styling** | Tailwind CSS | 3.4.1 | Utility-first CSS |
| **Animations** | Framer Motion | 12.23.24 | Animations fluides |
| **State** | Zustand | 5.0.8 | State management |
| **Forms** | React Hook Form | 7.65.0 | Form validation |
| **Validation** | Zod | 4.1.12 | Schema validation |
| **Icons** | Lucide React | 0.344.0 | Icon library |

### UI & Component Libraries

| Library | Usage |
|---------|-------|
| **Radix UI** | Dialog, Progress, Select, Tabs, Toast (headless) |
| **Recharts** | Charts & analytics |
| **React Simple Maps** | Carte mondiale interactive |
| **React Dropzone** | Upload de fichiers |
| **Tailwind Merge** | Merge de classes CSS |

### Design Tokens & Plugins

- **@tailwindcss/typography** : Typographie riche
- **@tailwindcss/forms** : Styles de formulaires
- **@fontsource/inter** : Police Inter

### Backend/Auth (prévu)

- **Supabase** : Auth + base de données (intégré mais non utilisé)
- **i18next** : Internationalisation (configuré, non actif)

### Dev Tools

- **ESLint** : Linting
- **Terser** : Minification
- **PostCSS** : Autoprefixer

---

## 2. Structure Générale du Projet Frontend

### Architecture des dossiers

```
src/
├── App.tsx                          # Router principal + Layout switcher
├── main.tsx                         # Entry point React
│
├── pages/                           # Pages principales
│   ├── HomePage.tsx                 # Landing page (7 sections)
│   ├── DashboardPage.tsx            # Smart Dashboard Bento
│   ├── OffersPage.tsx               # Liste offres avec filtres
│   ├── OfferDetailPage.tsx          # Détail d'une offre
│   ├── ProfilePage.tsx              # Formulaire profil utilisateur
│   ├── AnalyzePage.tsx              # Upload CV + analyse IA
│   ├── TrainingsPage.tsx            # Liste formations
│   ├── TrainingDetailPage.tsx       # Détail formation
│   ├── LettersPage.tsx              # Lettres générées
│   ├── AnalyticsPage.tsx            # Analytics (deprecated → dashboard)
│   ├── SettingsPage.tsx             # Paramètres utilisateur
│   ├── ContactPage.tsx              # Formulaire contact
│   ├── PricingPage.tsx              # Plans tarifaires
│   ├── AuthPage.tsx                 # Login/Signup
│   ├── MentionsLegalesPage.tsx      # Mentions légales
│   ├── ConfidentialitePage.tsx      # Politique confidentialité
│   ├── 404Page.tsx                  # Page 404
│   ├── 500Page.tsx                  # Erreur serveur
│   ├── MaintenancePage.tsx          # Maintenance
│   └── RedirectPage.tsx             # Redirection
│
├── components/
│   ├── layout/                      # Composants de layout
│   │   ├── Navbar.tsx               # Navigation principale (floating)
│   │   ├── Footer.tsx               # Footer global
│   │   ├── DashboardLayout.tsx      # Layout dashboard (sidebar + topbar)
│   │   ├── PageTransition.tsx       # Transitions Framer Motion
│   │   ├── PageHeader.tsx           # Header de page
│   │   ├── SectionWrapper.tsx       # Wrapper de section
│   │   └── BackgroundLayout.tsx     # Backgrounds aurora/gradient
│   │
│   ├── sections/                    # Sections landing page
│   │   ├── HeroSection.tsx          # Hero V8 (badge + titre + cartes + CTA)
│   │   ├── HowItWorksSection.tsx    # Process 3 étapes
│   │   ├── WhyEleviaWorksSection.tsx # Bento 4 blocs (fusion stats)
│   │   ├── RecommendedOffersSection.tsx # Top 3 matches
│   │   ├── TestimonialsSection.tsx  # Carousel témoignages
│   │   ├── LiveDemoSection.tsx      # Démo IA interactive
│   │   ├── FinalCTASection.tsx      # CTA finale
│   │   └── FeaturesSection.tsx      # Features génériques
│   │
│   ├── ui/                          # Composants UI réutilisables
│   │   ├── Button.tsx               # Bouton avec variants
│   │   ├── Card.tsx                 # Card de base
│   │   ├── GlassCard.tsx            # Card glassmorphism
│   │   ├── BaseListingCard.tsx      # Card liste générique
│   │   ├── OfferCard.tsx            # Card offre avec matching
│   │   ├── MatchingCard.tsx         # Card résultat matching
│   │   ├── KpiCard.tsx              # Card KPI dashboard
│   │   ├── PricingCard.tsx          # Card pricing
│   │   ├── TestimonialCard.tsx      # Card témoignage
│   │   ├── HeroCard.tsx             # Card hero section
│   │   ├── Badge.tsx                # Badge avec variants
│   │   ├── BadgePill.tsx            # Badge pill
│   │   ├── Tag.tsx                  # Tag (compétences, etc.)
│   │   ├── Input.tsx                # Input avec focus ring
│   │   ├── Select.tsx               # Select custom
│   │   ├── Progress.tsx             # Progress bar
│   │   ├── RadialProgress.tsx       # Progress radial
│   │   ├── Toast.tsx                # Toast notifications
│   │   ├── AlertDialog.tsx          # Dialog Radix
│   │   ├── HoverCard.tsx            # Hover card Radix
│   │   ├── Typography.tsx           # Typographie réutilisable
│   │   ├── Skeleton.tsx             # Loading skeleton
│   │   ├── SkeletonCard.tsx         # Card skeleton
│   │   ├── ErrorState.tsx           # État d'erreur
│   │   ├── EmptyState.tsx           # État vide
│   │   ├── FiltersBar.tsx           # Barre de filtres
│   │   ├── Dock.tsx                 # Dock navigation
│   │   ├── Carousel.tsx             # Carousel
│   │   ├── BentoGrid.tsx            # Bento layout
│   │   ├── GridBackgroundDemo.tsx   # Grid background
│   │   ├── DottedMap.tsx            # Carte pointillée
│   │   ├── AuroraBackground.tsx     # Aurora gradient
│   │   ├── Ripple.tsx               # Effet ripple
│   │   ├── AnimatedBeam.tsx         # Beam animation
│   │   ├── AnimatedCounter.tsx      # Counter animé
│   │   ├── AnimatedGradientText.tsx # Gradient text animé
│   │   ├── ScrollVelocity.tsx       # Scroll velocity effect
│   │   ├── NumberTicker.tsx         # Number ticker animation
│   │   ├── TypingAnimation.tsx      # Typing effect
│   │   ├── GradientButton.tsx       # Bouton gradient
│   │   ├── FloatingParticles.tsx    # Particules flottantes
│   │   ├── LightBeam.tsx            # Light beam effect
│   │   ├── GlowIcon.tsx             # Icon avec glow
│   │   └── icons/                   # Icons custom
│   │       ├── LogoElevia.tsx
│   │       ├── ArrowRight.tsx
│   │       ├── Globe.tsx
│   │       └── DotPattern.tsx
│   │
│   ├── dashboard/                   # Composants dashboard
│   │   ├── DashboardCard.tsx        # Card dashboard
│   │   ├── KpiBar.tsx               # Barre KPI
│   │   ├── ProgressTile.tsx         # Tile avec progress
│   │   ├── WorldMap.tsx             # Carte mondiale interactive
│   │   ├── ActivityChart.tsx        # Chart activité
│   │   ├── MarketTrendsChart.tsx    # Chart tendances
│   │   ├── RadarSkillsChart.tsx     # Radar compétences
│   │   ├── AIInsightsCard.tsx       # Insights IA
│   │   ├── FormationsCard.tsx       # Card formations
│   │   ├── TrendPill.tsx            # Pill tendance
│   │   └── MarketInsightChip.tsx    # Chip insight marché
│   │
│   ├── analytics/                   # Composants analytics
│   │   ├── StatsCard.tsx            # Card stats
│   │   ├── ScoreEvolutionChart.tsx  # Évolution scores
│   │   ├── DomainPerformanceChart.tsx # Performance par domaine
│   │   └── CountryPieChart.tsx      # Répartition pays
│   │
│   ├── training/                    # Composants formations
│   │   ├── TrainingCard.tsx         # Card formation
│   │   ├── ImpactBlock.tsx          # Bloc impact
│   │   └── ImpactBadge.tsx          # Badge impact
│   │
│   ├── freemium/                    # Composants freemium
│   │   ├── BlurredCard.tsx          # Card floutée (paywall)
│   │   └── UpgradeCTA.tsx           # CTA upgrade
│   │
│   ├── OfferFilters.tsx             # Filtres offres
│   ├── OfferModal.tsx               # Modal détail offre
│   ├── ProfileExtracted.tsx         # Profil extrait CV
│   ├── ProfileEnrichment.tsx        # Enrichissement profil
│   ├── MatchingResults.tsx          # Résultats matching
│   ├── DragDropZone.tsx             # Zone drag & drop
│   ├── ProgressBar.tsx              # Progress bar générique
│   ├── AIAnalysisLoader.tsx         # Loader analyse IA
│   ├── DemoResults.tsx              # Résultats démo
│   ├── LetterCard.tsx               # Card lettre générée
│   └── LetterInsights.tsx           # Insights lettre
│
├── layout/                          # Layout wrappers (legacy)
│   ├── AppLayout.tsx                # Layout app (Sidebar + Topbar)
│   ├── Topbar.tsx                   # Topbar dashboard
│   ├── Sidebar.tsx                  # Sidebar navigation
│   └── PageContainer.tsx            # Container max-w-7xl
│
├── router/
│   └── AppRouter.tsx                # Router alternatif (non utilisé)
│
├── store/                           # Zustand stores
│   └── userStore.ts                 # Store utilisateur
│
├── data/                            # Données mock
│   ├── offers_mock.json             # Offres mock
│   ├── trainings_mock.json          # Formations mock
│   ├── letters_mock.json            # Lettres mock
│   ├── testimonials_mock.json       # Témoignages mock
│   ├── dashboard_mock.json          # Dashboard mock
│   ├── analytics_mock.json          # Analytics mock
│   └── offers.ts                    # Offres (legacy)
│
├── types/                           # Types TypeScript
│   ├── index.ts                     # Types principaux
│   ├── filters.ts                   # Types filtres
│   └── hero.ts                      # Types hero section
│
├── lib/                             # Utilities & logic
│   ├── animations.ts                # Presets Framer Motion
│   └── utils.ts                     # cn() + helpers
│
├── hooks/                           # Custom hooks
│   ├── index.ts
│   ├── useFocusRing.ts
│   └── useCrossfade.ts
│
├── styles/
│   └── theme.css                    # CSS custom + layers Tailwind
│
└── utils/
    └── cn.ts                        # classNames merge utility
```

### Organisation du routing

**Deux architectures coexistent** :

1. **App.tsx** (principale) : Router avec logique de layout conditional (Navbar pour landing, Sidebar pour dashboard)
2. **AppRouter.tsx** (legacy) : Router plus simple (non utilisé actuellement)

**Séparation des layouts** :
- **Landing pages** : Navbar flottante + Footer
- **Dashboard pages** : AppLayout (Sidebar + Topbar, sans Navbar)

---

## 3. Pages Existantes ou Prévues

### Landing Pages (Navbar + Footer)

| Page | Route | État | Rôle |
|------|-------|------|------|
| **HomePage** | `/` | ✅ Terminé | Landing page (7 sections narratives) |
| **AnalyzePage** | `/analyze` | ✅ Terminé | Upload CV + analyse IA |
| **ProfilePage** | `/profile` | ✅ Terminé | Formulaire profil utilisateur |
| **ContactPage** | `/contact` | ✅ Terminé | Formulaire contact |
| **PricingPage** | `/pricing` | ✅ Terminé | Plans tarifaires (Free/Pro/Enterprise) |
| **AuthPage** | `/auth` | 🟡 WIP | Login/Signup (UI prête, backend manquant) |
| **MentionsLegalesPage** | `/mentions-legales` | ✅ Terminé | Mentions légales |
| **ConfidentialitePage** | `/confidentialite` | ✅ Terminé | Politique confidentialité |

---

### Dashboard Pages (Sidebar + Topbar)

| Page | Route | État | Rôle |
|------|-------|------|------|
| **DashboardPage** | `/dashboard` | ✅ Terminé | Smart Dashboard Bento (KPI + WorldMap + Charts) |
| **OffersPage** | `/offres` | ✅ Terminé | Liste offres V.I.E avec filtres avancés |
| **OfferDetailPage** | `/offer/:id` | ✅ Terminé | Détail offre + actions (postuler, sauvegarder) |
| **TrainingsPage** | `/formations` | ✅ Terminé | Liste formations recommandées |
| **TrainingDetailPage** | `/formations/:id` | ✅ Terminé | Détail formation |
| **LettersPage** | `/lettres` | ✅ Terminé | Lettres de motivation générées |
| **SettingsPage** | `/parametres` | ✅ Terminé | Paramètres utilisateur |
| **AnalyticsPage** | `/analytics` | ⚠️ Deprecated | Redirige vers `/dashboard` |

---

### Technical Pages

| Page | Route | État | Rôle |
|------|-------|------|------|
| **NotFoundPage** | `*` (404) | ✅ Terminé | Page 404 custom |
| **ServerErrorPage** | `/500` | ✅ Terminé | Erreur serveur 500 |
| **MaintenancePage** | `/maintenance` | ✅ Terminé | Mode maintenance |
| **RedirectPage** | `/redirect` | ✅ Terminé | Redirection générique |

---

### Redirections

- `/analytics` → `/dashboard` (consolidation)
- `/offers` → `/offres` (francisation)

---

## 4. Design System & UI

### Principes visuels : "Next Horizon+" (Oct 2025)

**Nom du design system** : ADA Elevia V9

**Philosophie** :
- Glassmorphisme premium (`bg-white/70` + `backdrop-blur-sm`)
- Gradients fluides (Cyan → Lime)
- GPU animations partout (`transform-gpu`, `will-change`)
- Performance 60fps stable
- Bundle < 200kB

---

### Palette de couleurs

#### Couleurs primaires

| Couleur | Hex | Usage |
|---------|-----|-------|
| **Cyan 500** | `#06B6D4` | Actions, CTA, accents |
| **Lime 500** | `#22C55E` | États positifs, success |

#### Extended Palette

**Cyan Scale** :
- 50: `#ECFEFF`
- 100: `#CFFAFE`
- 200: `#A5F3FC`
- 300: `#67E8F9`
- 400: `#22D3EE`
- **500: `#06B6D4`** ← Primary
- 600: `#0891B2`
- 700: `#0E7490`
- 800: `#155E75`
- 900: `#164E63`

**Lime Scale** :
- 50: `#F7FEE7`
- 100: `#ECFCCB`
- 200: `#D9F99D`
- 300: `#BEF264`
- 400: `#A3E635`
- **500: `#22C55E`** ← Secondary
- 600: `#16A34A`
- 700: `#15803D`
- 800: `#166534`
- 900: `#14532D`

#### Matching Score Colors

| Score | Couleur | Hex |
|-------|---------|-----|
| 0-39% | Low | `#EF4444` (Red 500) |
| 40-59% | Medium | `#FACC15` (Yellow 400) |
| 60-79% | Good | `#06B6D4` (Cyan 500) |
| 80-100% | Excellent | `#22C55E` (Lime 500) |

#### Neutral Colors (Slate)

- 50: `#F8FAFC` (Background)
- 100: `#F1F5F9`
- 200: `#E2E8F0` (Borders)
- 300: `#CBD5E1`
- 400: `#94A3B8` (Disabled)
- 500: `#64748B` (Muted text)
- 600: `#475569`
- 700: `#334155`
- 800: `#1E293B` (Primary text)
- 900: `#0F172A` (Headings)

#### Semantic Colors

- **Warning**: `#FACC15` (Yellow)
- **Error**: `#EF4444` (Red)
- **Info**: `#3B82F6` (Blue)
- **Disabled**: `#94A3B8` (Slate 400)

---

### Typographie

**Police principale** : **Inter** (variable font)
- Font features : `"rlig" 1, "calt" 1` (ligatures + contextual alternates)
- Poids utilisés : 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold)

**Hiérarchie** :
- H1 : `text-3xl md:text-4xl font-bold`
- H2 : `text-2xl md:text-3xl font-bold`
- H3 : `text-xl md:text-2xl font-semibold`
- Body : `text-base leading-relaxed`
- Caption : `text-sm text-slate-600`
- Label : `text-xs font-semibold`

---

### Spacing & Rhythm

**Section spacing** : `py-16 md:py-20` (consistent rhythm)
**Container** : `max-w-7xl mx-auto px-6`
**Page top spacing** : `pt-32 md:pt-40` (pour Navbar flottante)

---

### Border Radius

- **Card** : `1rem` (16px)
- **Button** : `0.75rem` (12px)
- **Badge** : `0.5rem` (8px)
- **XL** : `1rem`
- **2XL** : `1.5rem`

---

### Shadows

| Shadow | Usage | CSS |
|--------|-------|-----|
| `soft` | Cards | `0 8px 24px rgba(0,0,0,0.05)` |
| `glow` | Hover CTA | `0 0 24px rgba(6,182,212,0.25)` |
| `glow-cyan` | Accents | `0 0 20px rgba(6,182,212,0.2)` |
| `card` | Cards soft | `0 1px 3px 0 rgba(0,0,0,0.1)` |

---

### Glassmorphisme

**Base card** :
```css
.card-boost {
  @apply bg-white/90 backdrop-blur-sm
         border border-slate-200 rounded-2xl shadow-md
         transition-all duration-300;
}

.card-boost-hover {
  @apply card-boost
         hover:bg-white hover:shadow-lg
         hover:-translate-y-1 hover:scale-[1.01]
         transition-all duration-300;
}
```

---

### Boutons

#### Primary Button
```css
.btn-primary {
  @apply bg-gradient-to-r from-[#06B6D4] to-[#22C55E] text-white
         px-6 py-3 rounded-xl font-semibold shadow-md
         hover:shadow-glow transform hover:scale-[1.02] active:scale-95
         transition-all duration-300;
}
```

#### Secondary Button
```css
.btn-secondary {
  @apply bg-white border border-slate-300 text-slate-700
         px-6 py-3 rounded-xl font-semibold
         hover:bg-slate-50 transition-all duration-300;
}
```

#### Outline Button
```css
.btn-outline {
  @apply bg-transparent border-2 border-cyan-500 text-cyan-600
         px-6 py-3 rounded-xl font-semibold
         hover:bg-cyan-500 hover:text-white transition-all duration-300;
}
```

---

### Badges

**Variants avec logique matching** :
- `.badge-excellent` : Lime (80-100%)
- `.badge-good` : Cyan (60-79%)
- `.badge-medium` : Yellow (40-59%)
- `.badge-low` : Red (0-39%)
- `.badge-info` : Blue
- `.badge-default` : Slate

---

### Gradient Text

```css
.gradient-text {
  @apply bg-gradient-to-r from-[#06B6D4] to-[#22C55E]
         bg-clip-text text-transparent;
}

.gradient-text-reverse {
  @apply bg-gradient-to-r from-[#22C55E] to-[#06B6D4]
         bg-clip-text text-transparent;
}
```

---

### Motion System (Framer Motion)

**Presets définis** (`lib/animations.ts`) :
- `fadeInUp` : Fade + translate Y
- `fadeIn` : Fade simple
- `staggerContainer` : Container avec stagger
- `staggerItem` : Item enfant
- `scaleIn` : Scale + fade
- `slideInLeft/Right` : Slide horizontal

**Durées** : ≤ 600ms
**Easing** : `cubic-bezier(0.4, 0, 0.2, 1)` (easeInOut)

**GPU Compositing** :
- `transform-gpu` systématique
- `will-change-transform` pour animations

---

### Composants UI (shadcn-inspired)

- **Radix UI** utilisé pour les composants headless (Dialog, Progress, Select, Tabs, Toast)
- **Lucide React** pour les icônes (cohérence +344 icons)
- **Tailwind CSS** pour tous les styles (pas de CSS modules)

---

### Inspirations évoquées

- **Vercel** : Gradients subtils, performance
- **Linear** : Motion fluide, microinteractions
- **Stripe** : Bento layouts, glassmorphisme
- **Supabase** : Aurora backgrounds, grid overlays
- **Framer** : Animations GPU, smoothness

---

## 5. Composants Frontend Clés

### Composants de Layout

#### `<Navbar />` (Floating)
- Navigation principale (landing pages)
- **Position** : Fixed top
- **Style** : Glassmorphism + backdrop-blur
- **Responsive** : Mobile burger menu
- **État** : ✅ Terminé

#### `<Footer />`
- Footer global (landing pages)
- **Sections** : Links, social, legal
- **État** : ✅ Terminé

#### `<AppLayout />`
- Layout dashboard avec Sidebar + Topbar
- **Logique** : Sidebar rétractable
- **État** : ✅ Terminé

#### `<Sidebar />`
- Navigation dashboard
- **Items** : Dashboard, Offres, Formations, Lettres, Paramètres
- **Icons** : Lucide React
- **État** : ✅ Terminé

#### `<Topbar />`
- Barre supérieure dashboard
- **Features** : Search, notifications, user menu
- **État** : ✅ Terminé

#### `<PageContainer />`
- Container centré (`max-w-7xl`)
- **Usage** : Toutes les pages dashboard
- **État** : ✅ Terminé

#### `<PageTransition />`
- Wrapper Framer Motion pour transitions de pages
- **Effet** : Fade + slight translate
- **État** : ✅ Terminé

---

### Composants Sections (Landing Page)

#### `<HeroSection />` (V8)
- **Structure** : Badge → Titre → Cartes → CTA → KPI
- **Animations** : Stagger + GPU
- **État** : ✅ Terminé

#### `<HowItWorksSection />` (V3)
- **Structure** : Process 3 étapes directionnelles
- **Style** : Cards avec icons + arrows
- **État** : ✅ Terminé

#### `<WhyEleviaWorksSection />` (V9 - Fusion)
- **Structure** : Bento 4 blocs asymétriques
- **Fusion de** : WhyEleviaSection + StatsAndTrustSection
- **État** : ✅ Terminé

#### `<RecommendedOffersSection />` (V2)
- **Structure** : Top 3 matches
- **Animations** : GPU + hover effects
- **État** : ✅ Terminé

#### `<TestimonialsSection />` (V2)
- **Structure** : Carousel horizontal drag
- **Library** : Framer Motion drag
- **État** : ✅ Terminé

#### `<LiveDemoSection />` (V9.4)
- **Structure** : Démo IA interactive
- **Feature** : Upload CV mock → résultats instantanés
- **État** : ✅ Terminé

#### `<FinalCTASection />` (V1)
- **Structure** : Conversion finale
- **CTA** : "Commencer gratuitement"
- **État** : ✅ Terminé

---

### Composants UI Réutilisables

#### Cards

| Composant | Rôle | État |
|-----------|------|------|
| `<Card />` | Card de base | ✅ |
| `<GlassCard />` | Card glassmorphism | ✅ |
| `<BaseListingCard />` | Card liste générique | ✅ |
| `<OfferCard />` | Card offre avec matching score | ✅ |
| `<MatchingCard />` | Card résultat matching | ✅ |
| `<KpiCard />` | Card KPI dashboard | ✅ |
| `<PricingCard />` | Card pricing (Free/Pro) | ✅ |
| `<TestimonialCard />` | Card témoignage | ✅ |
| `<HeroCard />` | Card hero section | ✅ |
| `<BlurredCard />` | Card floutée (freemium) | ✅ |

#### Form Elements

| Composant | Rôle | État |
|-----------|------|------|
| `<Input />` | Input avec focus ring cyan | ✅ |
| `<Select />` | Select custom (Radix) | ✅ |
| `<Button />` | Bouton avec variants | ✅ |
| `<GradientButton />` | Bouton gradient animé | ✅ |

#### Data Display

| Composant | Rôle | État |
|-----------|------|------|
| `<Badge />` | Badge avec variants | ✅ |
| `<BadgePill />` | Badge pill | ✅ |
| `<Tag />` | Tag (compétences) | ✅ |
| `<Progress />` | Progress bar | ✅ |
| `<RadialProgress />` | Progress radial | ✅ |
| `<Typography />` | Typographie réutilisable | ✅ |

#### Feedback

| Composant | Rôle | État |
|-----------|------|------|
| `<Toast />` | Toast notifications (Radix) | ✅ |
| `<AlertDialog />` | Dialog modale (Radix) | ✅ |
| `<ErrorState />` | État d'erreur | ✅ |
| `<EmptyState />` | État vide | ✅ |
| `<Skeleton />` | Loading skeleton | ✅ |
| `<SkeletonCard />` | Card skeleton | ✅ |

#### Layout

| Composant | Rôle | État |
|-----------|------|------|
| `<BentoGrid />` | Bento layout | ✅ |
| `<Dock />` | Dock navigation | ✅ |
| `<Carousel />` | Carousel (Framer) | ✅ |
| `<FiltersBar />` | Barre de filtres | ✅ |

#### Effects & Animations

| Composant | Rôle | État |
|-----------|------|------|
| `<AuroraBackground />` | Aurora gradient | ✅ |
| `<GridBackgroundDemo />` | Grid background | ✅ |
| `<DottedMap />` | Carte pointillée | ✅ |
| `<Ripple />` | Effet ripple | ✅ |
| `<AnimatedBeam />` | Beam animation | ✅ |
| `<AnimatedCounter />` | Counter animé | ✅ |
| `<AnimatedGradientText />` | Gradient text animé | ✅ |
| `<ScrollVelocity />` | Scroll velocity effect | ✅ |
| `<NumberTicker />` | Number ticker animation | ✅ |
| `<TypingAnimation />` | Typing effect | ✅ |
| `<FloatingParticles />` | Particules flottantes | ✅ |
| `<LightBeam />` | Light beam effect | ✅ |
| `<GlowIcon />` | Icon avec glow | ✅ |

---

### Composants Dashboard

| Composant | Rôle | État |
|-----------|------|------|
| `<WorldMap />` | Carte mondiale interactive (react-simple-maps) | ✅ |
| `<ActivityChart />` | Chart activité (Recharts) | ✅ |
| `<MarketTrendsChart />` | Chart tendances marché | ✅ |
| `<RadarSkillsChart />` | Radar compétences (Recharts) | ✅ |
| `<AIInsightsCard />` | Insights IA | ✅ |
| `<FormationsCard />` | Card formations recommandées | ✅ |
| `<KpiBar />` | Barre KPI | ✅ |
| `<ProgressTile />` | Tile avec progress radial | ✅ |
| `<TrendPill />` | Pill tendance | ✅ |
| `<MarketInsightChip />` | Chip insight marché | ✅ |

---

### Composants Analytics

| Composant | Rôle | État |
|-----------|------|------|
| `<StatsCard />` | Card stats | ✅ |
| `<ScoreEvolutionChart />` | Évolution scores | ✅ |
| `<DomainPerformanceChart />` | Performance par domaine | ✅ |
| `<CountryPieChart />` | Répartition pays | ✅ |

---

### Composants Fonctionnels

| Composant | Rôle | État |
|-----------|------|------|
| `<OfferFilters />` | Filtres avancés offres | ✅ |
| `<OfferModal />` | Modal détail offre | ✅ |
| `<DragDropZone />` | Zone drag & drop CV | ✅ |
| `<ProfileExtracted />` | Profil extrait CV | ✅ |
| `<ProfileEnrichment />` | Enrichissement profil | ✅ |
| `<MatchingResults />` | Résultats matching | ✅ |
| `<AIAnalysisLoader />` | Loader analyse IA | ✅ |
| `<DemoResults />` | Résultats démo | ✅ |
| `<LetterCard />` | Card lettre générée | ✅ |
| `<LetterInsights />` | Insights lettre | ✅ |
| `<UpgradeCTA />` | CTA upgrade premium | ✅ |

---

## 6. Intégration Backend (prévu ou existant)

### Endpoints Backend Évoqués

**Base URL** : `http://localhost:8000` (local) ou TBD (prod)

| Endpoint | Méthode | Usage Frontend | État |
|----------|---------|----------------|------|
| `/health` | GET | Health check | ✅ Backend |
| `/offers` | GET | Liste offres (OffersPage) | ✅ Backend |
| `/offers/{id}` | GET | Détail offre (OfferDetailPage) | ✅ Backend |
| `/match` | POST | Matching profil/offres (AnalyzePage) | ✅ Backend |
| `/profile/users` | POST | Créer/maj profil | ✅ Backend |
| `/profile/extract` | POST | Extraire profil CV | ✅ Backend |
| `/auth/signup` | POST | Inscription | ❌ À implémenter |
| `/auth/login` | POST | Connexion | ❌ À implémenter |
| `/auth/me` | GET | Profil connecté | ❌ À implémenter |
| `/generation/cover-letter` | POST | Générer lettre | ❌ À implémenter |

---

### Flux Front → Back

#### 1. Upload CV & Matching
```
[AnalyzePage]
  ↓ Upload CV (drag & drop)
  ↓ POST /profile/extract (file: FormData)
Backend → OpenAI GPT-4o-mini
  ↓ { profile: ProfileMinimal }
[ProfileExtracted] affiche profil
  ↓ User valide
  ↓ POST /match (body: { profile, offerIds })
Backend → Scoring algorithm
  ↓ [MatchAndInterestResult[]]
[MatchingResults] affiche résultats triés
```

#### 2. Liste Offres avec Filtres
```
[OffersPage]
  ↓ User applique filtres (domain, country, salary, etc.)
  ↓ GET /offers?page=1&limit=20&country=Canada&minSalary=2000
Backend → MongoDB query + pagination
  ↓ { items: Offer[], total: number }
[OfferCard] map sur items
  ↓ User clique sur offre
  ↓ Navigate /offer/:id
[OfferDetailPage]
  ↓ GET /offers/:id
  ↓ { offer: Offer }
Affichage détails + actions (postuler, sauvegarder)
```

#### 3. Profil Utilisateur
```
[ProfilePage]
  ↓ User remplit formulaire (React Hook Form)
  ↓ Validation Zod
  ↓ POST /profile/users (body: ProfileMinimal)
Backend → MongoDB upsert
  ↓ { user: User }
Zustand store.setProfile(user.profile)
LocalStorage persist
```

---

### Hypothèses Techniques

1. **Pas de JWT actuellement** : Toutes les routes sont publiques (MVP)
2. **Pas de rate limiting** : Vulnérable à l'abus (à corriger)
3. **CORS configuré** : `localhost:5173`, `localhost:3000`, `viexplore.ai`
4. **Pas de data fetching library** : Fetch natif (React Query prévu)
5. **Pas de WebSockets** : Pas de real-time (prévu pour notifications)

---

### Ce qui est mocké

**Toutes les données sont actuellement mockées en JSON** :

| Fichier | Données |
|---------|---------|
| `offers_mock.json` | ~50 offres V.I.E |
| `trainings_mock.json` | ~20 formations |
| `letters_mock.json` | ~10 lettres générées |
| `testimonials_mock.json` | ~6 témoignages |
| `dashboard_mock.json` | KPI, WorldMap, ActivityChart |
| `analytics_mock.json` | Stats, évolution scores |

**Format des mocks** :
```json
{
  "offers": [
    {
      "id": "1",
      "title": "Data Analyst - V.I.E",
      "company": "BNP Paribas",
      "location": "Montréal, Canada",
      "country": "Canada",
      "domain": "Finance",
      "salary": 2255,
      "duration": "12 mois",
      "matchScore": 87,
      "hardSkills": ["Python", "SQL", "Power BI"],
      "description": "..."
    }
  ]
}
```

---

### Ce qui manque

**Côté Frontend** :
1. ❌ **Auth flow** : Login/Signup UI prête, mais pas de logique JWT
2. ❌ **Data fetching layer** : Pas de React Query (fetch natif répété)
3. ❌ **Error handling global** : Pas de ErrorBoundary
4. ❌ **Loading states consistants** : Skeleton/loader ad-hoc
5. ❌ **Optimistic updates** : Pas d'UI responsive avant réponse backend
6. ❌ **WebSockets** : Pas de notifications real-time
7. ❌ **Offline support** : Pas de PWA/service worker

**Côté Backend** :
1. ❌ **JWT Auth** : Pas d'authentification (toutes routes publiques)
2. ❌ **Rate limiting** : Pas de protection DoS
3. ❌ **Upload endpoint** : `/profile/extract` nécessite `pypandoc` installé
4. ❌ **Génération documents** : Endpoint `/generation/*` non implémenté
5. ❌ **Scraping pipeline** : Offres manuelles (pas d'auto-update)

---

## 7. Logique Fonctionnelle

### Récupération des Données

**Actuellement** :
- Toutes les données sont **importées directement depuis les fichiers JSON** mock
- Pas d'appel API réel (sauf démo `POST /match`)

**Exemple** (OffersPage.tsx) :
```typescript
import offersDataRaw from '@/data/offers_mock.json';

// Normalisation (support format { offers: [...] } ou [...])
const offersArray = Array.isArray(offersDataRaw)
  ? offersDataRaw
  : offersDataRaw?.offers || [];

// Filtrage côté client
const filteredOffers = offersArray.filter(offer => {
  // Logique de filtrage...
});
```

**Problème** : Pas de séparation entre data fetching et UI.

---

### State Management (Zustand)

**Store principal** : `userStore.ts`

```typescript
interface UserStore {
  user: User | null;
  isPremium: boolean;
  setUser: (user: User) => void;
  logout: () => void;
}
```

**Usage** :
```typescript
const { user, isPremium } = useUserStore();
```

**Persistence** : LocalStorage automatique via Zustand middleware.

**État actuel** :
- ✅ Store user fonctionnel
- ❌ Pas de store offers/profile (données locales)
- ❌ Pas de sync avec backend

---

### Logique de Filtrage (OffersPage)

**FilterState** (types/filters.ts) :
```typescript
interface FilterState {
  domains: string[];      // ["Finance", "Tech"]
  cities: string[];       // ["Montréal", "Paris"]
  countries: string[];    // ["Canada", "France"]
  salaryMin: number;      // 0-3000
  salaryMax: number;
  durationMin: number;    // 0-24 mois
  durationMax: number;
  matchMin: number;       // 0-100
}
```

**Logique de filtrage** (côté client) :
```typescript
const filteredOffers = offersArray.filter(offer => {
  const matchesSearch = searchQuery === '' ||
    offer.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    offer.company?.toLowerCase().includes(searchQuery.toLowerCase());

  const matchesDomain = filters.domains.length === 0 ||
    filters.domains.includes(offer.domain);

  const matchesSalary = offer.salary >= filters.salaryMin &&
    offer.salary <= filters.salaryMax;

  return matchesSearch && matchesDomain && matchesSalary && /* ... */;
});
```

**Problème** : Filtrage côté client = pas scalable si >1000 offres.

---

### Workflow Utilisateur Principal

#### Parcours "Matching CV"

1. **Landing** (`/`) → User découvre Elevia
2. **CTA "Télécharger mon CV"** → Redirect `/analyze`
3. **AnalyzePage** :
   - Upload CV (drag & drop)
   - POST `/profile/extract` → OpenAI parsing
   - Affichage `<ProfileExtracted />`
4. **User valide profil** → POST `/match` (profil vs toutes offres)
5. **MatchingResults** :
   - Liste triée par score
   - Filtrage : POSTULER / SURVEILLER / LAISSER_PASSER
6. **User clique sur offre** → `/offer/:id`
7. **OfferDetailPage** :
   - Actions : "Postuler" (externe), "Sauvegarder"

#### Parcours "Explorer Offres"

1. **Sidebar** → `/offres`
2. **OffersPage** :
   - Search bar + filtres avancés
   - Grid responsive (1/2/3 colonnes)
   - Freemium : 5 claires + 3 semi-blur + reste premium
3. **User clique offre** → `/offer/:id`
4. **Actions** : Postuler, Sauvegarder, Générer lettre (premium)

#### Parcours "Dashboard"

1. **Login** (future) → `/dashboard`
2. **DashboardPage** :
   - Bento layout 6 colonnes
   - WorldMap interactive
   - ActivityChart (Recharts)
   - Top matches, formations, lettres
3. **Navigation** : Sidebar vers Offres, Formations, Lettres

---

### Points Importants du Workflow

**A. Freemium Logic** :
- **Free** : 5 offres complètes + 3 semi-blur + reste locked
- **Pro** : Accès illimité + génération lettres
- **Enterprise** : API access + support dédié

**B. Matching Score Display** :
- **80-100%** : Badge vert "Excellent match" + lime glow
- **60-79%** : Badge cyan "Bon match"
- **40-59%** : Badge jaune "Match moyen"
- **0-39%** : Badge rouge "Match faible"

**C. Responsive Behavior** :
- **Mobile** : 1 colonne, burger menu, sidebar overlay
- **Tablet** : 2 colonnes, sidebar rétractable
- **Desktop** : 3 colonnes, sidebar fixe

**D. Animations** :
- **Page transitions** : Fade + slight translate (300ms)
- **Cards** : Hover lift + scale (300ms)
- **Loading** : Skeleton cards (shimmer effect)

---

## 8. Points Faibles / Incohérences / Risques

### Points Faibles Identifiés

#### 1. **Architecture des données**
- ❌ **Pas de data fetching layer** : Imports JSON directs, répétition de code
- ❌ **Pas de cache** : Re-fetch à chaque navigation
- ❌ **Filtrage côté client** : Non scalable si >1000 offres
- ❌ **Pas de pagination backend** : Toutes les offres chargées d'un coup

#### 2. **State management fragmenté**
- ✅ Zustand pour user
- ❌ Pas de store global pour offers/trainings/letters
- ❌ LocalStorage utilisé ad-hoc sans stratégie
- ❌ Pas de sync state ↔ backend

#### 3. **Performance**
- ⚠️ **Bundle size** : Framer Motion + Recharts + React Simple Maps = lourd
- ⚠️ **Animations partout** : Risque de jank sur mobile low-end
- ⚠️ **Pas de lazy loading** : Toutes les pages chargées d'un coup
- ⚠️ **Images non optimisées** : Pas de WebP/AVIF

#### 4. **Accessibilité (A11y)**
- ✅ Skip link présent
- ✅ Semantic HTML (`<main>`, `<nav>`, `<footer>`)
- ⚠️ **Focus management** : Pas de focus trap dans modals
- ⚠️ **Keyboard navigation** : Carousel/Dock pas totalement accessibles
- ❌ **Screen reader** : Labels aria manquants sur certains boutons icons-only
- ❌ **Color contrast** : Certains badges (yellow) < 4.5:1

#### 5. **SEO**
- ❌ **CSR pur** : Pas de SSR/SSG (Vite SPA)
- ❌ **Meta tags dynamiques** : Pas de React Helmet
- ❌ **Sitemap** : Absent
- ❌ **Schema.org** : Pas de structured data

#### 6. **Sécurité**
- ❌ **XSS** : `dangerouslySetInnerHTML` non utilisé (OK), mais pas de sanitization
- ❌ **CSRF** : Pas de tokens (backend public pour l'instant)
- ❌ **Sensitive data** : Pas de chiffrement LocalStorage
- ⚠️ **CORS** : Trop permissif (`*` dans certains cas)

#### 7. **Testing**
- ❌ **0% coverage** : Aucun test unitaire
- ❌ **Pas de tests E2E** : Pas de Playwright/Cypress
- ❌ **Pas de tests a11y** : Pas d'axe-core

#### 8. **UX/UI**
- ⚠️ **Loading states inconsistants** : Skeleton vs spinner vs rien
- ⚠️ **Error handling** : Pas d'ErrorBoundary global
- ⚠️ **Offline** : Pas de feedback si perte connexion
- ⚠️ **Toast stacking** : Pas de limite (peut overflow)

---

### Incohérences Détectées

1. **Deux routers coexistent** : `App.tsx` (actif) + `AppRouter.tsx` (mort)
2. **Composants legacy** : Dossier `_archive` avec anciens composants non supprimés
3. **Nommage inconsistant** : `OffersPage` vs `offres` route (mix FR/EN)
4. **Styles mixés** : Classes Tailwind + CSS custom (`theme.css`)
5. **Types dupliqués** : `types/index.ts` vs inline types dans composants
6. **Mock data formats** : Certains mocks `{ offers: [...] }`, d'autres `[...]` directs

---

### Risques Techniques

#### Risque 1 : **Performance Mobile**
- **Cause** : Animations GPU + charts lourds + bundle non optimisé
- **Impact** : Jank, battery drain, slow load
- **Mitigation** :
  - Code splitting (React.lazy)
  - Remove unused Framer variants
  - Prefers-reduced-motion

#### Risque 2 : **Scalabilité Données**
- **Cause** : Filtrage côté client, pas de pagination backend
- **Impact** : App freeze si 10k+ offres
- **Mitigation** :
  - Filtrage backend
  - Pagination cursor
  - Virtualization (react-window)

#### Risque 3 : **État de l'Auth**
- **Cause** : UI prête, backend manquant
- **Impact** : Features bloquées (lettres, save, premium)
- **Mitigation** :
  - Implémenter JWT backend ASAP
  - Protected routes frontend

#### Risque 4 : **Maintenance CSS**
- **Cause** : Tailwind + CSS custom mixés
- **Impact** : Duplication, conflicts
- **Mitigation** :
  - Migrer tout vers Tailwind
  - Supprimer `theme.css` custom classes

#### Risque 5 : **Dépendance Mock Data**
- **Cause** : Frontend entièrement dépendant des JSON mocks
- **Impact** : Impossible de tester backend integration
- **Mitigation** :
  - Implémenter data fetching layer
  - Mock Service Worker (MSW) pour tests

---

## 9. Recommandations Techniques et UX

### Recommandations Techniques

#### Priorité 🔴 Haute

1. **Implémenter React Query**
   ```typescript
   const { data, isLoading, error } = useQuery({
     queryKey: ['offers', filters],
     queryFn: () => fetchOffers(filters)
   });
   ```
   - ✅ Cache automatique
   - ✅ Refetch on focus
   - ✅ Loading states standardisés
   - ✅ Error handling unifié

2. **Ajouter ErrorBoundary global**
   ```typescript
   <ErrorBoundary fallback={<ErrorPage />}>
     <App />
   </ErrorBoundary>
   ```

3. **Code splitting agressif**
   ```typescript
   const DashboardPage = lazy(() => import('./pages/DashboardPage'));
   const OffersPage = lazy(() => import('./pages/OffersPage'));
   ```

4. **Migrer vers backend pagination**
   - Remplacer filtres client par params backend
   - Implémenter cursor pagination
   - Ajouter infinite scroll (optionnel)

5. **Implémenter auth flow complet**
   - Protected routes HOC
   - Token refresh automatique
   - Logout on 401

---

#### Priorité 🟡 Moyenne

6. **Optimiser bundle**
   - Tree-shaking Framer Motion (import { motion } specific)
   - Lazy load Recharts/React Simple Maps
   - WebP/AVIF images
   - Terser + gzip

7. **Améliorer a11y**
   - Focus trap dans modals (radix a déjà ça)
   - ARIA labels exhaustifs
   - Keyboard shortcuts (documentation)
   - Color contrast audit (WCAG AA minimum)

8. **Ajouter tests**
   - Vitest + React Testing Library (unitaires)
   - Playwright (E2E critiques : signup, matching, checkout)
   - axe-core (a11y automated)

9. **Uniformiser state management**
   - Store Zustand pour offers/trainings/letters
   - Pas de LocalStorage direct (via Zustand persist)
   - Sync avec backend (optimistic updates)

10. **Refactor CSS**
    - Supprimer `theme.css` custom classes
    - Tout en Tailwind + CVA (class-variance-authority)
    - Design tokens centralisés (tailwind.config.js)

---

#### Priorité 🟢 Basse

11. **SEO (si public)**
    - Migrer vers Next.js (SSR/SSG) ou Astro (SSG)
    - React Helmet (meta tags dynamiques)
    - Sitemap.xml généré
    - Schema.org (JobPosting structured data)

12. **Monitoring**
    - Sentry (error tracking)
    - Google Analytics / Plausible (privacy-first)
    - Web Vitals (CWV tracking)

13. **PWA**
    - Service worker (offline fallback)
    - Manifest.json
    - Install prompt

14. **Internationalisation**
    - Activer i18next (déjà installé)
    - Traduire UI (FR/EN)
    - Language switcher

---

### Recommandations UX

#### UX Quick Wins

1. **Loading states cohérents**
   - Toujours afficher skeleton cards (pas de spinner)
   - Durée minimale 300ms (éviter flash)
   - Désactiver boutons pendant loading

2. **Empty states**
   - Illustrations custom (undraw.co)
   - CTA clair ("Ajouter une offre", "Explorer")
   - Message encourageant (pas juste "Aucun résultat")

3. **Error states**
   - Messages clairs, actionnables
   - Bouton "Réessayer"
   - Éviter jargon technique ("Erreur 500" → "Oups, un problème est survenu")

4. **Toast management**
   - Max 3 toasts simultanés
   - Auto-dismiss après 5s
   - Bouton "Tout fermer"

5. **Feedback visuel**
   - Hover states partout (cursor: pointer)
   - Active states (scale down)
   - Focus visible (cyan ring)

6. **Microinteractions**
   - Success checkmarks animés
   - Confetti sur actions majeures (1er match parfait)
   - Haptic feedback mobile (navigator.vibrate)

---

#### UX Améliorations Structurelles

7. **Onboarding**
   - Tour guidé (react-joyride)
   - Progressive disclosure (pas tout d'un coup)
   - Skip option

8. **Search UX**
   - Autocomplete intelligent
   - Recent searches
   - Suggestions basées sur profil

9. **Filters UX**
   - Compteurs live ("Finance (23)")
   - Reset all button
   - Save filters (user prefs)

10. **Matching UX**
    - Expliquer le score (tooltip détaillé)
    - Graphique radar compétences
    - Suggestions amélioration ("Ajoute Docker pour +15%")

11. **Mobile UX**
    - Swipe actions (save, dismiss)
    - Bottom sheets (vs modals)
    - Thumb-friendly zones (bottom 1/3)

---

### Améliorations Design

12. **Polish visuel**
    - Shadows plus subtiles (actuel trop fort)
    - Spacing plus généreux (whitespace)
    - Illustrations custom (vs stock Unsplash)

13. **Dark mode**
    - Toggle dans settings
    - System preference detection
    - Smooth transition (prefers-color-scheme)

14. **Animations**
    - Reduce motion support (CSS media query)
    - Durées plus courtes (200-300ms vs 600ms)
    - Fewer parallax (nauséabond)

---

## 10. Roadmap Frontend (v1 → v2 → v3)

### Version 1.0 — MVP Fonctionnel ✅ (Actuel)

**Objectif** : Landing + Dashboard + Offres + Matching (mock data)

**Features** :
- [x] Landing page 7 sections (Hero → Final CTA)
- [x] Dashboard Bento layout
- [x] Liste offres avec filtres client-side
- [x] Détail offre + matching score
- [x] Upload CV + extraction profil (UI)
- [x] Design system "Next Horizon+" complet
- [x] Responsive mobile/tablet/desktop
- [x] Animations Framer Motion
- [x] Glassmorphisme + Aurora backgrounds

**Stack** :
- React 18 + TypeScript + Vite
- Tailwind CSS + Framer Motion
- Zustand (state)
- React Router 7

**Status** : 95% complété

**Manque** :
- Auth backend
- Data fetching real (React Query)
- Tests

---

### Version 2.0 — Production Ready 🟡 (Q1 2025)

**Objectif** : Backend intégré + Auth + Optimisations + Tests

**Features** :
- [ ] **Auth JWT** : Login/Signup/Logout + protected routes
- [ ] **React Query** : Data fetching layer + cache
- [ ] **Backend integration** : API calls réels (offers, matching, profile)
- [ ] **Génération lettres** : Endpoint + UI upload/download
- [ ] **Freemium complet** : Paywall + Stripe checkout
- [ ] **Error handling** : ErrorBoundary + toast consistency
- [ ] **Loading states** : Skeleton partout
- [ ] **Code splitting** : Lazy load pages + charts
- [ ] **Bundle optimization** : <150kB gzipped
- [ ] **Tests** : 60%+ coverage (Vitest + Playwright E2E)
- [ ] **A11y audit** : WCAG AA minimum
- [ ] **Monitoring** : Sentry + Web Vitals
- [ ] **SEO basics** : Meta tags + sitemap

**Stack additions** :
- React Query
- Stripe SDK
- Sentry
- Vitest + Playwright

**Timeline** : 4-6 semaines

---

### Version 3.0 — Scale & Polish 🟢 (Q2 2025)

**Objectif** : 10k users + Features avancées + SEO + Internationalisation

**Features** :
- [ ] **SSR/SSG** : Migrer vers Next.js ou Astro (SEO)
- [ ] **i18n** : FR/EN complet + language switcher
- [ ] **Dark mode** : Toggle + system preference
- [ ] **PWA** : Offline support + install prompt
- [ ] **Real-time** : WebSockets (notifications, live matching)
- [ ] **Advanced filters** : Saved searches + alerts
- [ ] **Social features** : Share matching results
- [ ] **Analytics dashboard** : User journey tracking
- [ ] **A/B testing** : Growth experiments
- [ ] **Performance** : <2s LCP, 60fps animations
- [ ] **Tests** : 80%+ coverage
- [ ] **Microservices** : Frontend/Backend découplés (BFF pattern)

**Stack additions** :
- Next.js 15 (ou Astro)
- Socket.io
- Redis (cache)
- PostHog (analytics)

**Timeline** : 3-4 mois

---

## Conclusion

Le frontend **Viexplore AI (Elevia)** est un projet React/TypeScript moderne avec un design system premium "Next Horizon+" basé sur Tailwind CSS, Framer Motion et Radix UI. L'architecture actuelle (V1.0 MVP) est fonctionnelle mais repose entièrement sur des données mockées et manque d'intégration backend réelle.

**Points forts** :
- ✅ Design system cohérent et premium
- ✅ Composants UI réutilisables nombreux
- ✅ Animations fluides (Framer Motion)
- ✅ Responsive complet
- ✅ Structure de routing claire

**Points critiques à adresser** :
- ❌ Pas d'auth JWT
- ❌ Pas de data fetching layer (React Query)
- ❌ Pas de tests
- ❌ Performance bundle à optimiser
- ❌ Accessibilité à améliorer

**Prochaines étapes prioritaires** :
1. Implémenter auth JWT (backend + frontend)
2. Migrer vers React Query
3. Code splitting + lazy loading
4. Tests unitaires + E2E
5. Backend API integration réelle

Le projet est prêt pour une **mise en production beta** après l'implémentation de l'auth et de l'intégration backend complète (estimé 4-6 semaines).

---

**Fin du rapport.**

**Contact** : Akim Guentas
**Repo** : https://github.com/akimguentas/viexplore-ai
**Demo** : TBD
**Prod** : TBD
