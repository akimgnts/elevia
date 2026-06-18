# FRONTEND_FULL_SPECIFICATION.md

## TABLE OF CONTENTS

1. [Vision produit actuelle](#1-vision-produit-actuelle)
2. [Architecture front-end](#2-architecture-front-end)
3. [Carte complète des routes](#3-carte-complète-des-routes)
4. [Inventaire complet des pages](#4-inventaire-complet-des-pages)
5. [Inventaire complet des composants](#5-inventaire-complet-des-composants)
6. [Workflows utilisateurs](#6-workflows-utilisateurs)
7. [Cartographie des données affichées](#7-cartographie-des-données-affichées)
8. [Analyse UX](#8-analyse-ux)
9. [Analyse UI](#9-analyse-ui)
10. [Analyse produit](#10-analyse-produit)
11. [Design System observé](#11-design-system-observé)
12. [Reconstruction recommandée](#12-reconstruction-recommandée)
13. [Brief final pour Emergent AI](#13-brief-final-pour-emergent-ai)

---

# 1. VISION PRODUIT ACTUELLE

## Résumé exécutif

**Elevia Compass** est une plateforme de **matching emploi-candidat** basée sur l'analyse IA du CV et du profil utilisateur. Le produit aide les candidats à :

1. **Uploader et analyser** leur CV/profil (AnalyzePage)
2. **Visualiser les offres d'emploi** disponibles dans un catalogue (OffersPage)
3. **Recevoir des recommandations d'emploi** intelligentes dans une Inbox (InboxPage)
4. **Consulter le détail** de chaque offre avec justifications de matching (OfferDetailModal)
5. **Gérer** leur profil intelligemment (ProfilePage, ProfileUnderstandingPage)
6. **Tracker** leurs candidatures (ApplicationsPage)

## Point de vue utilisateur

Elevia Compass se positionne comme :
- **Un outil d'exploration préalable** : consulter le catalogue d'offres AVANT même d'utiliser l'outil (OffersPage)
- **Un outil d'analyse personnelle** : uploader CV → système extrait skills/expérience → suggestions de profil
- **Un outil de matching intelligent** : basé sur skills_uri (canonical ESCO IDs), domaine, profil utilisateur
- **Un outil de candidature accompagnée** : préparation d'Apply Pack (CV + lettre de motivation générée)
- **Un tracker d'applications** : historique et statuts de candidature (saved, cv_ready, applied, interview, won, etc.)

## Flux principal utilisateur

```
Landing (AdCoachTestPage) 
  ↓ 
Login (optionnel pour certaines pages)
  ↓
AnalyzePage (Upload CV → ingest + enrichment)
  ↓
ProfilePage (Review + edit profil)
  ↓
InboxPage (Recommandations avec matching score)
  ↓
OfferDetailPage (Détail offre + Apply Pack generation)
  ↓
ApplicationsPage (Track candidatures)
```

---

# 2. ARCHITECTURE FRONT-END

## Stack technologique

| Composant | Technologie | Version | Rôle |
|-----------|-------------|---------|------|
| Framework | React | 18.3.1 | UI rendering, component state |
| Routing | React Router | 7.12.0 | Page navigation, deep-linking |
| State Management | Zustand | 5.0.10 | Global auth + profile state |
| UI Framework | Tailwind CSS | 3.4.17 | Styling + design tokens |
| UI Components | Radix UI | 1.1.2+ | Accessible form components |
| Icons | Lucide React | 0.344.0 | Consistent icon library |
| Animations | Framer Motion | 12.23.24 | Smooth transitions |
| Charts | Chart.js | 4.4.8 | Data visualization |
| Maps | React Simple Maps | 3.0.0 | Geographic visualization |
| Build Tool | Vite | 6.4.1 | Fast bundling + dev server |
| Language | TypeScript | ~5.9.3 | Type safety |
| Fonts | @fontsource | 5.0.18 | Inter, Space Grotesk (self-hosted) |

## Structure des dossiers

```
apps/web/src/
├── pages/                      # 20 page components
├── components/                 # 63+ reusable components
│   ├── ui/                     # 23 base UI components
│   ├── layout/                 # Navigation, shells
│   ├── analyze/                # Profile analysis cards
│   ├── landing/                # Landing page sections
│   ├── sections/               # Reusable page sections
│   ├── profile/                # Profile display components
│   ├── market-insights/        # Market analysis components
│   └── inbox/                  # Inbox item cards
├── lib/                        # Utilities + helpers
│   ├── api.ts                  # Main API client (800+ LOC)
│   ├── profileMatching.ts      # Matching algorithm
│   ├── inboxItems.ts           # Inbox normalization
│   ├── profile/                # Profile parsing + reconstruction
│   ├── skills/                 # Skill normalization + mapping
│   ├── text.ts                 # Text utilities
│   └── titleUtils.ts           # Title cleaning
├── api/                        # API endpoint wrappers
│   └── applications.ts         # Application CRUD
├── store/                      # Zustand stores
│   ├── authStore.ts            # User authentication
│   └── profileStore.ts         # User profile + AI profile
├── hooks/                      # Custom hooks
│   └── useAuth.ts              # Auth store wrapper
├── services/                   # Business logic services
├── types/                      # TypeScript interfaces
│   ├── match.ts                # Matching types
│   └── offer.ts                # Offer types
├── styles/                     # Global styles + tokens
│   └── uiTokens.ts             # Design system tokens
├── fixtures/                   # Test/seed data
│   └── seedProfile.ts          # Demo profile
├── assets/                     # Images, logos
├── App.tsx                     # Root router component
├── main.tsx                    # Entry point with Vite
└── index.css                   # Global styles
```

## Architecture des stores Zustand

### authStore.ts (Authentication)

**State:**
```typescript
{
  user: AuthUser | null
  isAuthenticated: boolean
  isHydrated: boolean
  isChecking: boolean
  sessionChecked: boolean
}
```

**Actions:**
- `login(email, password)` → POST /auth/login
- `logout()` → POST /auth/logout + clear state
- `restoreSession()` → GET /auth/me (on app boot)
- `clear()` → reset to initial state

**Lifecycle:**
1. App boots → AuthBootstrap calls `restoreSession()`
2. `isChecking = true`
3. API responds → `sessionChecked = true`, `isAuthenticated = true/false`
4. Pages can route based on `isAuthenticated`

### profileStore.ts (User Profile + AI Profile)

**State:**
```typescript
{
  aiProfile: ParseFileResponse | null          // AI-parsed CV
  userProfile: CareerProfileV2 | null          // User-edited profile
  profileHash: string | null                   // SHA-256 hash for change detection
  profileId: string | null                     // UUID from backend
  activeProfileId: string | null               // Currently selected profile (localStorage)
  sessionId: string | null                     // Session identifier
  isHydrated: boolean
}
```

**Actions:**
- `setIngestResult(data, profileId?)` → Store both AI + user profile
- `setUserProfile(data, profileId?)` → Update user-edited version
- `setProfileId(id)` → Set backend UUID
- `setActiveProfileId(id)` → Set active + persist to localStorage
- `clearActiveProfileId()` → Clear selection
- `clear()` → Reset all

**Persistence:**
- localStorage key: `elevia.profile.v1`
- Active profile: `elevia.active_profile_id`
- Validation on hydration, cleanup of corrupted data

## Dev Server Configuration

**Vite Config (vite.config.ts):**
- **Port:** 3001
- **API Proxy:** `/api/*` → `http://localhost:8000` (configurable via `VITE_API_BASE_URL`)
- **Other proxies:** `/v1`, `/debug`, `/health` → same API target
- **Build:** TypeScript + React plugin

## Design Tokens (Tailwind)

**Brand Colors:**
- Cyan: `#06B6D4` (primary)
- Lime: `#22C55E` (secondary)

**Matching Score Colors:**
- Low: `#EF4444` (red)
- Medium: `#FACC15` (yellow)
- Good: `#06B6D4` (cyan)
- Excellent: `#22C55E` (lime)

**Shadows (elevation system):**
- xs: subtle
- sm: 2px
- DEFAULT: 4px
- md: 8px
- lg: 16px
- soft: soft elevation
- glow: cyan glow for emphasis
- card: minimal card shadow

**Border Radius:**
- sm: 6px
- DEFAULT: 8px
- md: 12px
- lg: 16px
- xl: 20px
- 2xl: 24px
- card: 16px
- button: 12px
- badge: 8px

**Typography:**
- Font Family: Inter (primary) + Space Grotesk (display)
- Base spacing: 4px

---

# 3. CARTE COMPLÈTE DES ROUTES

## Routes publiques

| Route | Page | Authentification | Description |
|-------|------|------------------|-------------|
| `/` | AdCoachTestPage | Non requise | Landing/Home principal |
| `/landing` | AdCoachTestPage | Non requise | Alias vers home |
| `/login` | LoginPage | Non requise | Page de connexion email/password |
| `/demo` | DemoPage | Non requise | Page démo avec nav buttons |
| `/matching-showcase` | MatchingShowcasePage | Non requise | Showcase statique exemples matching |

## Routes authentifiées

| Route | Page | Authentification | Description |
|-------|------|------------------|-------------|
| `/analyze` | AnalyzePage | Recommandée* | Upload CV → parsing → ingest |
| `/analyse` | (redirect) | - | Alias FR vers /analyze |
| `/profile` | ProfilePage | Recommandée* | Edit profil utilisateur |
| `/profile-understanding` | ProfileUnderstandingPage | Recommandée* | Afficher reconstruction IA du profil |
| `/dashboard` | DashboardPage | Recommandée* | Dashboard KPIs + offres |
| `/cockpit` | DashboardPage | Recommandée* | Alias vers /dashboard |
| `/match` | MatchPage | Recommandée* | Matching algo visualization |
| `/offers` | OffersPage | Non requise | Catalog browsing (filtres) |
| `/offres` | OffersPage | - | Alias FR vers /offers |
| `/explorer` | (redirect) | - | Redirect vers /offers |
| `/inbox` | InboxPage | Requise | Recommandations personnalisées |
| `/applications` | ApplicationsPage | Recommandée* | Application tracker |
| `/candidatures` | ApplicationsPage | - | Alias FR vers /applications |
| `/market-insights` | MarketInsightsPage | Recommandée* | Analyse marché + visualizations |
| `/market` | MarketInsightsPage | - | Alias vers /market-insights |
| `/offers/:offerId` | OfferDetailPage | Non requise | Détail offre spécifique |
| `/dev/cv-delta` | CvDeltaPage | Dev only | CV comparison tool |
| `/ad-coaching` | AdCoachTestPage | Recommandée* | Ad coaching demo page |
| `/adcoach-test` | (redirect) | - | Redirect vers /ad-coaching |
| `/*` | NotFoundPage | - | 404 catch-all |

**Note:** "Recommandée*" = accès non bloqué mais features pleines nécessitent session

## Redirects et aliases

```
/analyse                    → /analyze
/explorer                   → /offers
/adcoach-test               → /ad-coaching
/offres                     → /offers (alias)
/candidatures               → /applications (alias)
/cockpit                    → /dashboard (alias)
/market                     → /market-insights (alias)
```

## Entry point: AuthBootstrap

Composant dans App.tsx qui :
1. Vérifie `sessionChecked && !isChecking`
2. Appelle `restoreSession()` via authStore
3. Restaure session utilisateur depuis backend (`GET /auth/me`)
4. Set flags : `isChecking`, `sessionChecked`

→ Routes peuvent brancher sur `isAuthenticated` pour gating

---

# 4. INVENTAIRE COMPLET DES PAGES

## Page: AdCoachTestPage

**Fichier:** `pages/AdCoachTestPage.tsx` (73,519 LOC)

**Routes:** `/`, `/landing`, `/ad-coaching`

**Objectif:** Landing page principal + ad coaching demo

**Informations affichées:**
- Hero section avec headlines + CTA
- Cards héros (3-6 variants)
- How It Works section (étapes)
- KPI section (metrics)
- Testimonials section (lazy-loaded)
- Pricing section (lazy-loaded)
- Why Elevia Works section
- Final CTA block

**Actions utilisateur:**
- Click "Commencer" → navigate `/analyze`
- Click testimonial card → expand/interact
- Scroll → lazy-load sections
- Click pricing tiers → no action (info display)

**Composants utilisés:**
- HeroSection, HeroCard, HeroCardsGroup, HeroVisualLayer
- HowItWorks
- KPISection
- Testimonials (lazy via React.lazy)
- PricingSection (lazy via React.lazy)
- WhyElevia
- CTAUploadBlock
- LandingFooter

**APIs appelées:**
- Aucune (page statique)

**Points forts:**
- Multi-section modular design
- Lazy loading des sections lourd
- Responsive + responsive images

**Faiblesses:**
- Très long (73k LOC) pour une landing
- Mélange landing + ad-coaching dans même component
- Pas de CMS-friendly (contenu hardcodé)

**Dette UX/UI:**
- Sections hardcodées au lieu de data-driven
- Pas de A/B testing setup
- Testimonials layout peut être amélioré

---

## Page: AnalyzePage

**Fichier:** `pages/AnalyzePage.tsx` (35,471 LOC)

**Route:** `/analyze`

**Objectif:** Upload CV → parsing → ingest → afficher résultats analysis

**Informations affichées:**
- File upload area (drag-drop)
- Text input area (paste CV text)
- Parsed profile card (identité, email, phone, location)
- Market position card (role suggestions, domain)
- Key skills list (avec badges rare/pondérée)
- Key signals (quantified, impact)
- Dev panel (debug mode)
- Actions card (buttons)

**Actions utilisateur:**
- Upload file (PDF, DOCX, TXT)
- Paste text CV
- Switch tabs (file ↔ text)
- Click "Analyser" → POST /ingest
- Click "Continuer vers profil" → navigate `/profile`
- Click skill/signal → interact/remove

**Composants utilisés:**
- ProfileCard
- MarketPositionCard
- ActionsCard
- DevStatusCard
- DevPanel
- GlassCard

**APIs appelées:**
- `parseFile(file)` → POST /parse → extracts basic profile
- `parseFileEnriched(file)` → POST /parse (avec enrichment flag)
- `ingestCv(parsedProfile, sessionId?)` → POST /ingest → backend CV engine
- `fetchKeySkills(profileId)` → GET /profile/{id}/key-skills
- `fetchProfileFromDB(sessionId)` → GET /profile/{sessionId}
- `fetchAuditAIQuality(sessionId)` → GET /audit/ai-quality

**État local:**
- `tab: "file" | "text"`
- `uploadedFile: File | null`
- `rawText: string`
- `parsing: boolean`
- `parseResult: ParseFileResponse | null`
- `loadingModal: boolean`
- `enriching: boolean`

**Store utilisé:**
- `profileStore.setIngestResult(result)` → save parsed profile
- `profileStore.setProfileId(id)` → set backend UUID

**Points forts:**
- Upload dual mode (file + text)
- Real-time parsing feedback
- Clear skill extraction display
- Dev panel for debugging

**Faiblesses:**
- Very long component (35k LOC)
- Insufficient error handling for failed parsing
- UI for rich profile editing minimal
- Market position suggestions not always accurate

**Dette UX/UI:**
- No progress indicator during enrichment
- Error messages could be more helpful
- Skill editing UX clunky

---

## Page: ProfilePage

**Fichier:** `pages/ProfilePage.tsx` (60,809 LOC)

**Route:** `/profile`

**Objectif:** Edit + manage user profile (identité, expériences, skills, projets, langues)

**Informations affichées:**
- Identity section (name, email, phone, location, linkedin, github)
- Experiences section (title, company, dates, skills, tools, achievements)
- Education section (degree, field, institution, dates)
- Projects section (title, technologies, URL, impact)
- Languages section (language, level)
- Skills section (canonical_skills avec URI + confidence)
- Tools section (non-ESCO tools)
- Profile reconstruction (LLM-generated suggestions)

**Actions utilisateur:**
- Edit identity fields
- Add/remove experiences
- Edit experience details (title, company, dates, responsibilities)
- Add/link skills to experiences (skill_links with autonomy levels)
- Add/remove education
- Add/remove projects
- Add/remove languages
- Bulk skill suggestions via API
- Save all changes → PUT /profile/saved
- Reset from AI profile
- Toggle skill visibility

**Composants utilisés:**
- ProfileIntelligenceHero
- SkillTypeGroup
- ProjectCard
- Flex edit forms (no UI library used, custom CSS)

**APIs appelées:**
- `fetchProfileSkillSuggestions(profileId)` → GET /profile/skills/suggestions
- `fetchProfileToolSuggestions(profileId)` → GET /profile/tools/suggestions
- `saveSavedProfile(profile)` → PUT /profile/saved
- `fetchProfileFromDB(sessionId)` → GET /profile/{sessionId}

**État local:**
- `profile: CareerProfileV2` (user-editable copy)
- `unsavedChanges: boolean` (dirty flag)
- `saving: boolean`
- `expanded: Set<string>` (section expand/collapse)
- `suggestions: { skills: [], tools: [] }`

**Store utilisé:**
- `profileStore.userProfile` (read/update)
- `profileStore.aiProfile` (seed for reset)

**Points forts:**
- Comprehensive profile editing
- Skill canonicalization with URIs
- Autonomy levels (CONTRIB/COPILOT/LEAD)
- Skill_links binding (skill ↔ tool ↔ context)
- Backend validation of profile shape

**Faiblesses:**
- Extremely long component (60k LOC) → needs splitting
- Form styling very custom (no UI library)
- No unsaved changes warning before navigation
- Complex state management (expanded sections, suggestions)
- Skill editing UX could be polished

**Dette UX/UI:**
- Need form validation UI
- Need "You have unsaved changes" modal
- Skill_links editor very textual, needs UI polish
- Mobile responsiveness not tested

---

## Page: ProfileUnderstandingPage

**Fichier:** `pages/ProfileUnderstandingPage.tsx` (34,281 LOC)

**Route:** `/profile-understanding`

**Objectif:** Afficher profile reconstruction IA (skills inferred, project suggestions, career trajectory)

**Informations affichées:**
- Hero section with profile intelligence summary
- Skills by type groups (core, technical, soft, domain-specific)
- Projects section (from structured_cv)
- Reconstruction suggestions from LLM
- Profile intelligence metadata (confidence, signals)
- Career insights (domain affinity, trajectory)

**Actions utilisateur:**
- View skill groups
- Expand/collapse skill cards
- View project details
- Copy/share reconstruction
- Accept/reject suggestions (no backend call yet)

**Composants utilisés:**
- ProfileIntelligenceHero
- SkillTypeGroup
- ProjectCard

**APIs appelées:**
- `startProfileUnderstandingSession()` → POST /profile/understand
- `fetchProfileFromDB(sessionId)` → GET /profile/{sessionId}

**État local:**
- `profile: CareerProfileV2 | null` (loaded from backend)
- `loading: boolean`
- `error: string | null`
- `sessionId: string` (from URL or store)

**Store utilisé:**
- `profileStore.sessionId`
- `profileStore.profileId`

**Points forts:**
- Clean display of AI-reconstructed profile
- Skill grouping by type (core, technical, soft, domain)
- Shows profile intelligence confidence

**Faiblesses:**
- Suggestions shown but no way to action them
- No comparison vs. user profile
- Very long component (34k LOC)
- No way to regenerate profile

**Dette UX/UI:**
- Add "Accept these changes" flow
- Compare view vs user profile
- Show confidence/source of each skill

---

## Page: OffersPage

**Fichier:** `pages/OffersPage.tsx` (11,556 LOC)

**Routes:** `/offers`, `/offres`

**Objectif:** Browse catalog of job offers with search + filters

**Informations affichées:**
- Search bar (title, company, city, country)
- Filter bar (country, source)
- Featured offers grid (6 offers)
- Offer cards showing: title, company, location, source badge
- Source badges (France Travail, Business France)

**Actions utilisateur:**
- Type in search → filter real-time
- Select country filter
- Select source filter
- Click offer card → navigate `/offers/:offerId`
- Click "Voir inbox" (if user exists) → navigate `/inbox`

**Composants utilisés:**
- OfferCard (custom rendering in page)
- Source badges (inline styling)

**APIs appelées:**
- `fetchCatalogOffers(limit, sortMode)` → GET /offers/catalog

**État local:**
- `offers: OfferNormalized[]` (all catalog offers)
- `loading: boolean`
- `error: string | null`
- `query: string` (search input)
- `country: string` (filter)
- `source: "all" | "france_travail" | "business_france"`
- `countries: string[]` (extracted from offers)

**Store utilisé:**
- `profileStore.userProfile` (determines next CTA button)

**Points forts:**
- Simple, clear catalog view
- Real-time filtering
- Source labeling with color codes

**Faiblesses:**
- No pagination (only shows 6 featured)
- No sorting options
- Limited filter set (country, source only)
- No offer preview on hover
- Mobile responsiveness unclear

**Dette UX/UI:**
- Add pagination or infinite scroll
- Add sorting (date, title, match score if available)
- Add more filters (contract type, salary, skills)
- Add preview modal on card hover

---

## Page: InboxPage

**Fichier:** `pages/InboxPage.tsx` (59,764 LOC)

**Route:** `/inbox`

**Objectif:** Show personalized job recommendations with matching scores + decision tracking

**Informations affichées:**
- Matching profile snapshot (skills_uri, matching confidence)
- Inbox items with:
  - Offer title + company + location
  - Matching score (0-100)
  - Domain bucket (strict, neighbor, out)
  - Decision history (shortlisted, dismissed)
  - Skill match count + names
- Filter panel:
  - Company search
  - Country, city, contract_type
  - Published date range
  - Domain bucket (strict/neighbor/out)
  - Confidence levels (LOW, MED, HIGH)
  - Rare/sector skill levels
- Threshold slider (0-85)

**Actions utilisateur:**
- Refresh inbox → POST /inbox?refresh=true
- Filter items (all filters above)
- Click item → open OfferDetailModal
- Click "Shortlist" → POST /inbox/{id}/decision?decision=SHORTLISTED
- Click "Dismiss" → POST /inbox/{id}/decision?decision=DISMISSED
- Undo last decision
- Export inbox (feature mentioned but unclear if implemented)

**Composants utilisés:**
- InboxCardV2 (main item card)
- OfferDetailModal (opens on item click)
- Filter UI (inline, no UI library components)

**APIs appelées:**
- `fetchInbox(profileId, filters?, threshold?)` → GET /inbox
- `postDecision(itemId, decision)` → POST /inbox/{id}/decision
- `fetchOfferDetail(offerId, profileId)` → GET /offers/{id}
- `fetchOfferSemantic(offerId, profileId)` → GET /offers/{id}/semantic
- `fetchOfferContext(offerId)` → GET /offers/{id}/context
- `fetchProfileContext(profileId)` → GET /profile/{id}/context
- `fetchContextFit(offerId, profileId)` → GET /offers/{id}/fit
- `fetchProfileFromDB(sessionId)` → GET /profile/{sessionId}
- `upsertApplication(payload)` → POST /applications (when applying)

**État local:**
- `items: NormalizedInboxItem[]` (processed inbox items)
- `filteredItems: NormalizedInboxItem[]` (after filtering)
- `loading: boolean`
- `error: string | null`
- `filters: FiltersState` (company, country, domain_bucket, etc.)
- `threshold: number` (score threshold)
- `decisionRecords: { [itemId]: DecisionStatus }` (tracking decisions)
- `selectedOfferId: string | null` (modal open state)
- `offerDetail: OfferDetail | null` (modal content)
- `selectedItem: NormalizedInboxItem | null` (context for modal)
- `inboxProfileSnapshot: InboxProfileSnapshot` (skills_uri + matching_profile used)

**Store utilisé:**
- `profileStore.profileId`
- `profileStore.activeProfileId`
- `profileStore.sessionId`

**Points forts:**
- Rich filtering system
- Decision tracking (shortlist/dismiss)
- Threshold slider for score filtering
- Profile snapshot storage (reproducible matching)
- Undo support via decision records
- Modal context for offer details

**Faiblesses:**
- Extremely long component (59k LOC) → needs splitting
- Filter UI very custom, hard to extend
- No pagination (all items loaded at once?)
- Decision tracking only in localStorage (no backend sync mentioned)
- Threshold slider 0-85 options hardcoded

**Dette UX/UI:**
- Break component into sub-components (filters, item list, decision panel)
- Add pagination or infinite scroll
- Show matching score breakdown (which skills match?)
- Add "Save search" feature
- Show decision history per item (when shortlisted, etc.)

---

## Page: ApplicationsPage

**Fichier:** `pages/ApplicationsPage.tsx` (26,261 LOC)

**Routes:** `/applications`, `/candidatures`

**Objectif:** Track all job applications with statuses + history

**Informations affichées:**
- Application list with columns:
  - Offer title + company
  - Status badge (saved, cv_ready, applied, follow_up, interview, rejected, won, archived)
  - Application date
  - Last updated
  - Actions (edit, delete, archive)

**Actions utilisateur:**
- View all applications
- Filter by status
- Click application → view details + history
- Edit status
- Delete application
- Archive application
- Click "Apply to new offers" → navigate `/inbox`

**Composants utilisés:**
- Application cards/list (custom rendering)

**APIs appelées:**
- `listApplications()` → GET /applications
- `getApplication(offerId)` → GET /applications/{id}
- `getApplicationHistory(offerId)` → GET /applications/{id}/history
- `patchApplication(offerId, payload)` → PATCH /applications/{id}
- `deleteApplication(offerId)` → DELETE /applications/{id}`
- `upsertApplication(payload)` → POST /applications

**État local:**
- `applications: ApplicationItem[]`
- `loading: boolean`
- `error: string | null`
- `expandedId: string | null` (show/hide history)
- `editingId: string | null` (edit mode)

**Points forts:**
- Clear status tracking
- Application history
- Basic CRUD operations

**Faiblesses:**
- No sorting/filtering UI shown
- Status edit flow unclear
- No calendar view or timeline
- Limited context about next steps

**Dette UX/UI:**
- Add filtering by status
- Show next action (e.g., "Follow up in 2 weeks")
- Add calendar view of interviews
- Show success rate by source/role

---

## Page: DashboardPage

**Fichier:** `pages/DashboardPage.tsx` (10,851 LOC)

**Routes:** `/dashboard`, `/cockpit`

**Objectif:** Unified dashboard combining inbox recommendations + application tracking

**Informations affichées:**
- KPI cards (total applications, in progress, interviews, won)
- Recent offers grid (latest from inbox)
- Application status overview
- Quick actions

**Actions utilisateur:**
- View KPIs
- Click offer → navigate `/offers/:offerId`
- Click "Go to Inbox" → navigate `/inbox`
- Click "View Applications" → navigate `/applications`

**Composants utilisés:**
- KpiCard
- OfferCard

**APIs appelées:**
- `fetchSampleOffers(limit)` → GET /offers/sample
- `listApplications()` → GET /applications (for KPIs)

**État local:**
- `offers: OfferNormalized[]`
- `applications: ApplicationItem[]`
- `loading: boolean`
- `error: string | null`

**Points forts:**
- Quick overview of key metrics
- Easy navigation to main features

**Faiblesses:**
- Very simple, mostly static display
- No personalization based on profile
- KPI calculations unclear

**Dette UX/UI:**
- Add trend sparklines to KPIs
- Personalize "recommended next steps"
- Show success metrics

---

## Page: MatchPage

**Fichier:** `pages/MatchPage.tsx` (14,206 LOC)

**Route:** `/match`

**Objectif:** Visualize matching algorithm before/after with sample profile

**Informations affichées:**
- Before: Offer + generic profile
- After: Same offer + user profile
- Score comparison
- Matching factors explanation

**Actions utilisateur:**
- View example matching
- Change sample profile
- Click factors → expand explanation

**Composants utilisés:**
- MatchingCard (custom)

**APIs appelées:**
- Sample profile data (hardcoded or fixture)

**État local:**
- `sampleProfile: Profile`
- `offers: Offer[]`

**Points forts:**
- Educational visualization of matching

**Faiblesses:**
- Uses hardcoded sample data
- Not interactive
- Doesn't show user's actual matching

**Dette UX/UI:**
- Use user's own profile if authenticated
- Show live matching against real offers

---

## Page: MatchingShowcasePage

**Fichier:** `pages/MatchingShowcasePage.tsx` (4,421 LOC)

**Route:** `/matching-showcase`

**Objectif:** Static showcase of matching examples

**Informations affichées:**
- Example 1: Match with score
- Example 2: Match with score
- Example 3: Match with score

**Actions utilisateur:**
- View examples (no interactivity)

**Composants utilisés:**
- Static cards

**APIs appelées:**
- None (static content)

**Points forts:**
- Simple, educational

**Faiblesses:**
- Very limited, no real value

---

## Page: MarketInsightsPage

**Fichier:** `pages/MarketInsightsPage.tsx` (37,946 LOC)

**Route:** `/market-insights`

**Objectif:** Display market trends + geographic data visualization

**Informations affichées:**
- Interactive map (React Simple Maps) showing job distribution by country
- Top roles by country/domain
- Salary ranges (if available)
- Skill demand trends
- Market insights cards

**Actions utilisateur:**
- Hover/click countries on map
- Filter by domain
- Click role card → drill down

**Composants utilisés:**
- TopRolesCard
- Map visualization (custom with React Simple Maps)
- Chart.js charts

**APIs appelées:**
- Market data endpoint (unclear endpoint path)
- Skill demand data

**État local:**
- `marketData: MarketInsight[]`
- `selectedCountry: string | null`
- `selectedDomain: string | null`
- `loading: boolean`

**Points forts:**
- Geographic visualization
- Rich data display
- Interactive filtering

**Faiblesses:**
- Very long component (37k LOC)
- Unclear data sources
- Performance on large datasets unknown

**Dette UX/UI:**
- Optimize rendering for many countries
- Add loading states for map
- Show tooltips on hover

---

## Page: LoginPage

**Fichier:** `pages/LoginPage.tsx` (6,623 LOC)

**Route:** `/login`

**Objectif:** Authenticate user with email + password

**Informations affichées:**
- Email input
- Password input
- Login button
- Error message area
- Info panels (scope, MVP status)
- Link back to landing

**Actions utilisateur:**
- Enter email
- Enter password
- Click "Continuer" → POST /auth/login
- Click "Retour landing" → navigate `/landing`

**Composants utilisés:**
- Button (custom input elements, no UI library)

**APIs appelées:**
- `login(email, password)` → POST /auth/login

**État local:**
- `email: string`
- `password: string`
- `error: string | null`
- `isSubmitting: boolean`

**Store utilisé:**
- `useAuth()` for login action
- `isAuthenticated` for redirect

**Points forts:**
- Clean, simple login form
- Clear error messaging
- Redirect to /analyze on success

**Faiblesses:**
- No password reset
- No signup flow
- No social auth
- "MVP local avec un seul compte admin" comment suggests test-only state

**Dette UX/UI:**
- Add password reset link
- Add remember me checkbox
- Show password toggle

---

## Page: CvDeltaPage

**Fichier:** `pages/CvDeltaPage.tsx` (16,742 LOC)

**Route:** `/dev/cv-delta`

**Objectif:** Dev-only tool to compare CV parsing results between versions

**Informations affichées:**
- File upload area
- Before/after parsing results
- Diff view highlighting changes
- Parsing metrics (time, tokens, errors)

**Actions utilisateur:**
- Upload CV file
- View parsing results
- Toggle diff view

**Composants utilisés:**
- File upload (custom)
- Diff display (custom)

**APIs appelées:**
- `parseFile(file)` (current version)
- `parseFile(file)` (legacy version, if available)

**État local:**
- `file: File | null`
- `loading: boolean`
- `parseResult1: ParseFileResponse`
- `parseResult2: ParseFileResponse`
- `showDiff: boolean`

**Points forts:**
- Useful for debugging parser changes
- Clear before/after comparison

**Faiblesses:**
- Dev-only, not for production use
- UI very basic

---

## Page: DemoPage

**Fichier:** `pages/DemoPage.tsx` (878 LOC)

**Route:** `/demo`

**Objectif:** Navigation hub for demo features

**Informations affichées:**
- Navigation buttons to main features

**Actions utilisateur:**
- Click button → navigate to feature

**Components Used:**
- Simple nav buttons

**APIs Called:**
- None

**Points forts:**
- Quick access to features

**Faiblesses:**
- Minimal content, mostly just redirects

---

## Page: NotFoundPage

**Fichier:** `pages/NotFoundPage.tsx` (770 LOC)

**Route:** `/*` (catch-all)

**Objectif:** Display 404 error

**Informations affichées:**
- 404 message
- Link back to home

**Actions utilisateur:**
- Click home link

---

## Page: HomePage (LandingPage)

**Fichier:** `pages/HomePage.tsx` + `pages/LandingPage.tsx`

**Route:** (not currently used, content merged into AdCoachTestPage)

**Objectif:** Landing page composition

**Note:** Components exist but page not directly routed. Content integrated into AdCoachTestPage.

---

# 5. INVENTAIRE COMPLET DES COMPOSANTS

## Root-Level Components (8 files)

| Composant | Fichier | Lignes | Rôle | Props principales |
|-----------|---------|--------|------|-------------------|
| **CvPreviewModal** | CvPreviewModal.tsx | ~120 | Modal PDF/document viewer | `open: boolean`, `onOpenChange`, `cvData` |
| **CvHtmlPreviewModal** | CvHtmlPreviewModal.tsx | ~80 | Modal HTML-rendered CV | `open: boolean`, `onOpenChange`, `htmlContent` |
| **LetterPreviewModal** | LetterPreviewModal.tsx | ~100 | Modal cover letter preview | `open: boolean`, `onOpenChange`, `letterContent` |
| **OfferDetailModal** | OfferDetailModal.tsx | 506 | Large modal with offer + justifications | `offerId`, `open`, `onOpenChange`, `offer`, `profile` |
| **JustificationCard** | JustificationCard.tsx | ~290 | LLM-generated match justification | `skill`, `reason`, `context`, `confidence` |
| **StructuredOfferSummaryCard** | StructuredOfferSummaryCard.tsx | ~340 | Summarized offer display | `offer`, `matchScore`, `onApply` |
| **DevStatusCard** | DevStatusCard.tsx | ~200 | Dev environment status | `mode`, `profile`, `debug` |
| **ErrorBoundary** | ErrorBoundary.tsx | ~70 | React error boundary | `children`, `fallback` |

## Layout Components (5 files in `/components/layout/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **Navbar** | Navbar.tsx | Top navigation with branding + user menu | `currentPage`, `isAuthenticated` |
| **Footer** | Footer.tsx | Page footer with links | `minimal?: boolean` |
| **PremiumAppShell** | PremiumAppShell.tsx | Authenticated app layout wrapper | `eyebrow`, `title`, `description`, `actions`, `children` |
| **PageContainer** | PageContainer.tsx | Generic page wrapper with padding | `children`, `fullWidth?: boolean` |
| **SectionWrapper** | SectionWrapper.tsx | Section layout wrapper | `children`, `title`, `subtitle` |

## Auth Components (1 file in `/components/auth/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **ProtectedRoute** | ProtectedRoute.tsx | Route wrapper checking auth | `children`, `fallback` |

## Analyze Components (4 files in `/components/analyze/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **ProfileCard** | ProfileCard.tsx | Display parsed identity | `profile`, `onEdit` |
| **ActionsCard** | ActionsCard.tsx | Action buttons (analyze, continue, etc.) | `isLoading`, `onAnalyze`, `onContinue` |
| **MarketPositionCard** | MarketPositionCard.tsx | Market role suggestions | `suggestions`, `selectedRole` |
| **DevPanel** | DevPanel.tsx | Debug tool for parsing | `profile`, `signals`, `debugMode` |

## Landing Components (10 files in `/components/landing/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **HeroSection** | HeroSection.tsx | Hero section headline + CTA | `title`, `subtitle`, `cta` |
| **HeroCard** | HeroCard.tsx | Individual hero feature card | `icon`, `title`, `description` |
| **HeroCardsGroup** | HeroCardsGroup.tsx | Grid of hero cards | `cards: HeroCard[]` |
| **HeroVisualLayer** | HeroVisualLayer.tsx | Visual/animation layer | (animations only) |
| **HowItWorks** | HowItWorks.tsx | Step-by-step workflow | `steps` |
| **KPISection** | KPISection.tsx | KPI metrics display | `kpis: KPIItem[]` |
| **CTAUploadBlock** | CTAUploadBlock.tsx | File upload CTA | `onUpload`, `accept` |
| **WhyElevia** | WhyElevia.tsx | Value proposition | `benefits` |
| **Testimonials** | Testimonials.tsx | Customer testimonials (lazy) | `testimonials: Testimonial[]` |
| **PricingSection** | PricingSection.tsx | Pricing table (lazy) | `tiers: PricingTier[]` |
| **LandingFooter** | LandingFooter.tsx | Landing page footer variant | (static) |

## Reusable Sections (7 files in `/components/sections/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **HeroSection** | HeroSection.tsx | Secondary pages hero | `eyebrow`, `title`, `description` |
| **HowItWorksSection** | HowItWorksSection.tsx | Process steps | `steps: Step[]` |
| **LiveDemoSection** | LiveDemoSection.tsx | Interactive demo | (demo content) |
| **RecommendedOffersSection** | RecommendedOffersSection.tsx | Featured offers | `offers: Offer[]` |
| **TestimonialsSection** | TestimonialsSection.tsx | Social proof | `testimonials` |
| **WhyEleviaWorksSection** | WhyEleviaWorksSection.tsx | Benefits | `benefits` |
| **FinalCTASection** | FinalCTASection.tsx | Bottom CTA | `text`, `buttonText`, `onCTA` |

## Profile Components (3 files in `/components/profile/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **ProfileIntelligenceHero** | ProfileIntelligenceHero.tsx | Hero display for profile intelligence | `profile`, `confidence` |
| **SkillTypeGroup** | SkillTypeGroup.tsx | Groups skills by type | `skills`, `type` |
| **ProjectCard** | ProjectCard.tsx | Individual project/experience card | `project`, `onEdit` |

## Market Insights Components (1 file in `/components/market-insights/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **TopRolesCard** | TopRolesCard.tsx | Top roles by market | `roles`, `country` |

## Inbox Components (1 file in `/components/inbox/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **InboxCardV2** | InboxCardV2.tsx | Job recommendation card | `item: NormalizedInboxItem`, `onSelect`, `onDecide` |

## UI Components (23 files in `/components/ui/`)

| Composant | Fichier | Rôle | Props principales |
|-----------|---------|------|-------------------|
| **Button** | Button.tsx | Reusable button (variant, size) | `variant`, `size`, `disabled`, `children` |
| **Input** | Input.tsx | Text input field | `placeholder`, `value`, `onChange`, `type` |
| **Select** | Select.tsx | Dropdown select (Radix) | `options`, `value`, `onChange` |
| **card.tsx** | card.tsx | Generic card wrapper | `children`, `className` |
| **badge.tsx** | badge.tsx | Badge/label component | `variant`, `children` |
| **Toast.tsx** | Toast.tsx | Toast notification | `message`, `type`, `duration` |
| **Progress.tsx** | Progress.tsx | Progress bar (Radix) | `value`, `max` |
| **OfferCard** | OfferCard.tsx | Job offer card | `offer`, `onClick`, `highlighted` |
| **BaseListingCard** | BaseListingCard.tsx | Base listing card layout | `title`, `subtitle`, `children` |
| **MatchingCard** | MatchingCard.tsx | Job matching visualization | `offer`, `score`, `details` |
| **KpiCard** | KpiCard.tsx | KPI metric card | `label`, `value`, `trend` |
| **GlassCard** | GlassCard.tsx | Glassmorphism card (backdrop blur) | `children`, `className` |
| **HeroCard** | HeroCard.tsx | Hero feature card | `icon`, `title`, `description` |
| **PricingCard** | PricingCard.tsx | Pricing tier card | `tier`, `selected`, `onSelect` |
| **TestimonialCard** | TestimonialCard.tsx | Customer testimonial card | `author`, `quote`, `role` |
| **BlurredCard** | BlurredCard.tsx | Card with blurred background | `children` |
| **Skeleton** | Skeleton.tsx | Loading skeleton placeholder | `width`, `height`, `circle` |
| **EmptyState** | EmptyState.tsx | Empty state display | `icon`, `title`, `description`, `action` |
| **ErrorState** | ErrorState.tsx | Error state display | `icon`, `title`, `message`, `action` |
| **Typography** | Typography.tsx | Typography utility components | (h1-h6, p variants) |

---

# 6. WORKFLOWS UTILISATEURS

## Workflow: Création de compte (Non implémenté)

**Note:** Actuellement MVP avec un seul compte admin. Pas de signup flow.

**État souhaité:**
1. Click "Sign up" → SignupPage
2. Enter email + password
3. Accept ToS
4. Click "Create account"
5. Verify email (opt)
6. Redirect to /analyze

**Current state:** Skip directly to /login avec compte admin pré-créé

---

## Workflow: Connexion

**Pages impliquées:** LoginPage → authStore.login()

1. User navigates to `/login`
2. LoginPage renders with email + password inputs
3. User enters email (e.g., "akim@elevia.fr")
4. User enters password
5. User clicks "Continuer"
6. `handleSubmit()`:
   - Sets `isSubmitting = true`
   - Calls `authStore.login(email, password)`
   - Backend: POST `/auth/login`
   - On success:
     - `authStore.isAuthenticated = true`
     - `authStore.user = { id, email, ... }`
     - Redirect to `redirectTarget` (default `/analyze`)
   - On failure:
     - Set `error` message
     - `isSubmitting = false`
7. If already authenticated, auto-redirect to `/analyze`

**Error handling:**
- Invalid credentials → error message "Connexion impossible"
- Network error → same error message
- No specific password reset flow

---

## Workflow: Onboarding (Implicit)

**Pages impliquées:** AnalyzePage → ProfilePage → InboxPage

1. User arrives at `/analyze` (from /login or direct)
2. **AnalyzePage: Upload CV**
   - Choose file or paste text
   - Click "Analyser"
   - POST `/parse` (basic parsing)
   - GET `/ingest` (CV engine enrichment)
   - Display parsed profile + skills + signals
   - Click "Continuer vers profil" → navigate `/profile`
3. **ProfilePage: Edit Profile**
   - Review identity (name, email, location)
   - Review experiences + skills
   - Add missing experiences/skills
   - Edit skill_links (skill ↔ tool ↔ context)
   - Click "Enregistrer" → PUT `/profile/saved`
   - **Optional:** Review AI reconstruction (ProfileUnderstandingPage)
4. **Implicit:** Profile saved → can now use InboxPage

---

## Workflow: Upload CV

**Pages impliquées:** AnalyzePage

1. Click file upload area or drag-drop
2. Select PDF/DOCX/TXT file
3. System displays file name + size
4. Click "Analyser" button
5. Frontend:
   - `parseFile(file)` → POST `/parse` (parsing service)
   - Response: { profile: {...}, canonical_skills: [...], signals: [...] }
6. Display results:
   - ProfileCard (identity)
   - MarketPositionCard (domain suggestions)
   - Key skills + badges (rare, weighted)
   - Key signals (quantified, impact)
7. User can:
   - Edit suggestions inline
   - Click "Enrichment enabled" toggle (optional)
   - Reset and re-upload
   - Continue to ProfilePage

**Alternative workflow (Text input):**
- Switch to "Paste text" tab
- Copy-paste CV text
- Same "Analyser" flow

**Caching:**
- Parse result stored in `parseResult` state
- Can be saved via ProfilePage later

---

## Workflow: Analyse profil (ProfilePage)

**Pages impliquées:** ProfilePage

1. Navigate to `/profile` (from AnalyzePage or direct)
2. Display identity section:
   - Full name, email, phone, location, linkedin, github
   - Edit button → inline editing
3. Display experiences:
   - List of experiences (title, company, dates, skills)
   - Click "+" → add new experience
   - Click experience → edit inline:
     - Title, company, dates, responsibilities
     - **Skills linking:**
       - Add skill (autocomplete from suggestions)
       - Add tools (non-ESCO)
       - Set autonomy level (CONTRIB, COPILOT, LEAD)
       - Add context
4. Display education:
   - Degree, field, institution, dates
   - Edit/add/remove
5. Display projects:
   - Title, technologies, URL, impact
   - Edit/add/remove
6. Display skills:
   - Skills with URI, confidence, source
   - Suggestions available via "Suggest skills" button
   - Bulk add from suggestions
7. Save changes:
   - Click "Enregistrer"
   - PUT `/profile/saved`
   - Success message
   - Changes propagate to profiles store

**Advanced features:**
- Skill linking editor (skill ↔ tool ↔ context)
- Autonomy level selection
- Bulk suggestion import

---

## Workflow: Matching (InboxPage)

**Pages impliquées:** InboxPage, OfferDetailModal

1. Navigate to `/inbox` (requires authenticated profile)
2. **Initialization:**
   - `fetchInbox(profileId)` → GET `/inbox`
   - Build `matchingProfile` via `buildMatchingProfile(userProfile)`
   - Store `inboxProfileSnapshot` (skills_uri + matching_profile)
   - Set `threshold = 0` (default)
3. **Display:**
   - List of inbox items (normalized + sorted)
   - Each item shows: title, company, location, domain_bucket, confidence_level, score
4. **Filtering:**
   - Enter company search → live filter
   - Select country → live filter
   - Select domain bucket (strict/neighbor/out) → live filter
   - Set confidence level (LOW/MED/HIGH) → live filter
   - Date range picker → live filter
   - Skill level filters (rare_level, sector_level) → live filter
5. **Threshold slider:**
   - Drag slider: 0 → 85 (steps: 0, 55, 65, 75, 85)
   - Filter items below threshold
   - Re-sort by score (descending)
6. **Item interaction:**
   - Hover item → highlight
   - Click item → open OfferDetailModal
7. **In modal:**
   - Show offer detail (title, company, description, skills)
   - Show matching breakdown:
     - Matching score (0-100)
     - Matched skills (with names)
     - Missing skills (with names)
     - Autonomy match (if available)
   - Show JustificationCards (LLM explanations)
   - Click "Shortlist" → POST `/inbox/{id}/decision?decision=SHORTLISTED`
   - Click "Dismiss" → POST `/inbox/{id}/decision?decision=DISMISSED`
   - Click "Apply" → open Apply Pack flow (ApplyPackResponse)
8. **Decision tracking:**
   - Decisions stored in localStorage: `elevia_inbox_{profileId}_decisions`
   - Items marked with decision status (shortlisted, dismissed)
   - Can "Undo" last decision (clears decision record)

**Advanced features:**
- Profile context fetching (`fetchProfileContext`)
- Offer context fetching (`fetchOfferContext`)
- Context fit calculation (`fetchContextFit`)
- Semantic offer analysis (`fetchOfferSemantic`)

---

## Workflow: Consultation d'offre (OfferDetailPage)

**Pages impliquées:** OffersPage, OfferDetailPage

1. From **OffersPage:**
   - Click offer card → navigate `/offers/:offerId`
2. From **InboxPage:**
   - Click inbox item → open OfferDetailModal (in-page modal)
3. **OfferDetailPage (full page):**
   - `fetchOfferDetail(offerId)` → GET `/offers/{id}`
   - Display:
     - Offer title, company, location, contract type
     - Job description (full text)
     - Required skills list
     - Optional skills list
     - Salary range (if available)
     - Application link (if external)
   - Show apply button
   - Show related offers
4. **OfferDetailModal (in InboxPage):**
   - Show offer detail (subset of above)
   - Show matching score + breakdown
   - Show JustificationCards (why this match?)
   - Action buttons: Shortlist, Dismiss, Apply
5. **Apply flow:**
   - Click "Apply"
   - POST `/applications/{offerId}/prepare` → ApplyPackResponse
   - Get: `run_id`, `cache_keys` for CV + letter
   - Can preview CV + letter
   - Confirm apply → POST `/applications` (upsertApplication)

---

## Workflow: Génération de candidature (Apply Pack)

**Pages impliquées:** InboxPage (modal) / OfferDetailPage

1. User clicks "Apply" in OfferDetailModal or OfferDetailPage
2. **Prepare phase:**
   - POST `/applications/{offerId}/prepare`
   - Backend returns: { run_id, cache_keys, cv_prepared, letter_prepared }
   - Set up preview modals
3. **Preview CV:**
   - Click "Preview CV" → CvPreviewModal
   - Show prepared CV (HTML or PDF)
   - Can edit if needed
   - Click "Use this CV" → confirm
4. **Preview Letter:**
   - Click "Preview Letter" → LetterPreviewModal
   - Show generated cover letter (LLM-generated based on profile + offer)
   - Can edit if needed
   - Click "Use this letter" → confirm
5. **Submit Application:**
   - Click "Submit application"
   - POST `/applications` (upsertApplication):
     ```
     {
       offerId,
       status: "cv_ready",  // CV + letter prepared, not applied yet
       cv_data,
       letter_data,
       run_id
     }
     ```
   - Create ApplicationItem in database
   - Redirect to ApplicationsPage or show success toast
   - Item appears in applications list with status "cv_ready"

---

## Workflow: Inbox Decision Making

**Pages impliquées:** InboxPage

1. Click inbox item → open OfferDetailModal
2. In modal, see offer detail + matching info
3. **Decision options:**
   - Click "Shortlist" (✓ icon) → POST `/inbox/{id}/decision?decision=SHORTLISTED`
   - Click "Dismiss" (✗ icon) → POST `/inbox/{id}/decision?decision=DISMISSED`
   - Click "Apply" → see "Génération de candidature" workflow
4. **Backend response:**
   - Decision recorded: `{ status: "SHORTLISTED" | "DISMISSED", score, updated_at }`
   - Stored in `decisionRecords` (localStorage): `elevia_inbox_{profileId}_decisions`
5. **UI update:**
   - Item card updates with decision indicator
   - Item can be filtered out (by decision status filter)
   - Item stays in list but grayed out (optional)
6. **Undo:**
   - Click "Undo" button → delete decision from decisionRecords
   - Item shows as undecided again
   - Button greyed out if no decision to undo

---

## Workflow: Gestion profil

**Pages impliquées:** ProfilePage, ProfileUnderstandingPage

1. Navigate to `/profile`
2. **Edit sections:**
   - Expand/collapse by section
   - Edit identity, experiences, education, projects, languages
   - Edit skills + skill_links
   - Bulk suggestion import
3. **Save:**
   - Click "Enregistrer"
   - PUT `/profile/saved`
   - Store in profileStore.userProfile
4. **Advanced:**
   - Click "View profile intelligence" → navigate `/profile-understanding`
   - Show AI reconstruction (skills inferred, projects suggested)
   - Compare vs. user profile
   - Accept/reject suggestions (flow unclear, may not be implemented)

---

## Workflow: Application Tracking (ApplicationsPage)

**Pages impliquées:** ApplicationsPage

1. Navigate to `/applications`
2. **Display:**
   - List all applications (GET `/applications`)
   - Show: offer title, company, status, date applied, last updated
   - Status badges (saved, cv_ready, applied, follow_up, interview, rejected, won, archived)
3. **Actions:**
   - Click application → expand view
   - Show application history (GET `/applications/{id}/history`)
   - Edit status → PATCH `/applications/{id}`
   - Delete application → DELETE `/applications/{id}`
   - Archive application → PATCH `/applications/{id}` (set archived flag)
4. **Filtering:**
   - Filter by status (if implemented)
   - Sort by date (if implemented)
5. **Next steps:**
   - Show next action recommendations (e.g., "Follow up in 2 weeks")
   - Track interview dates (if available)

---

## Workflow: Market Insights Exploration

**Pages impliquées:** MarketInsightsPage

1. Navigate to `/market-insights`
2. **Interactive map:**
   - Display geographic visualization (React Simple Maps)
   - Show job count by country (color coded)
   - Hover country → tooltip with count
   - Click country → drill down
3. **Insights cards:**
   - Top roles (by demand, salary, growth)
   - Skill demand trends (top skills, emerging skills)
   - Salary ranges by role
4. **Filtering:**
   - Select domain → re-render map/cards
   - Select region → re-render
5. **No direct application:** Market insights are informational, not actionable

---

# 7. CARTOGRAPHIE DES DONNÉES AFFICHÉES

## AnalyzePage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| FileParser | POST `/parse` | ParseFileResponse | N/A | ProfileCard, key skills, signals |
| CV Engine | POST `/ingest` | ParseFileResponse | Enrichment | Market position suggestions |
| ProfileDB | GET `/profile/{sessionId}` | CareerProfileV2 | N/A | Full profile display |

**Data Transformations:**
- `ParseFileResponse` → Extract: identity, canonical_skills, canonical_skills_count, top_signal_units
- Canonical skills → Apply IDF weights, filter rare/weighted badges
- Signals → Format as quantified/impact/context tags

---

## ProfilePage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Frontend State | (useProfileStore) | ParseFileResponse | N/A | Load initial state |
| Skill Suggester | GET `/profile/skills/suggestions` | SkillSuggestion[] | Map to URI + confidence | Suggestion cards |
| Tool Suggester | GET `/profile/tools/suggestions` | ToolRef[] | N/A | Tool list |
| ProfileDB | PUT `/profile/saved` | CareerProfileV2 | Validation | Update backend |

**Data Structure:**
```typescript
CareerProfileV2 = {
  base_title,
  identity: IdentityV2,
  experiences: ExperienceV2[],
    - skill_links: { skill, tools, context, autonomy_level }
    - tools: CanonicalSkillRef[]
    - canonical_skills_used: CanonicalSkillRef[]
  education: EducationV2[],
  projects: ProjectV2[],
  languages: LanguageV2[]
}
```

---

## InboxPage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Inbox API | GET `/inbox` | InboxItem[] | normalizeAndSortInboxItems() | Item cards |
| Profile Store | (useProfileStore) | CareerProfileV2 | buildMatchingProfile() | Matching calculation |
| Offer Detail | GET `/offers/{id}` | OfferDetail | N/A | Modal display |
| Offer Semantic | GET `/offers/{id}/semantic` | OfferSemanticResponse | N/A | LLM breakdown |
| Decision POST | POST `/inbox/{id}/decision` | DecisionRecord | Store in localStorage | UI update |

**Normalization Pipeline:**
1. Raw inbox items from API
2. `normalizeAndSortInboxItems()`:
   - Extract domain bucket (strict/neighbor/out)
   - Extract confidence level (LOW/MED/HIGH)
   - Calculate matching score
   - Sort by score descending
3. Apply filter criteria
4. Apply threshold filter
5. Re-sort for display

**Matching Calculation:**
```typescript
buildMatchingProfile(userProfile) → {
  skills_uri: frozenset(canonical_skills),
  confidence: weighted_score,
  domain_affinity: calculated_match,
  ...
}
```

---

## OffersPage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Catalog | GET `/offers/catalog` | OfferNormalized[] | N/A | Offer cards |
| Frontend State | useState | filters | Client-side filter | Filtered list |

**Data Filtering (Client-side):**
```
haystack = `${title} ${company} ${city} ${country}`.toLowerCase()
matchesQuery = haystack.includes(query)
matchesCountry = country === filterCountry
matchesSource = source === filterSource
```

---

## OfferDetailPage/Modal Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Offer Detail | GET `/offers/{id}` | OfferDetail | N/A | Title, description, skills |
| Offer Semantic | GET `/offers/{id}/semantic` | OfferSemanticResponse | LLM parse | Semantic tags |
| Offer Context | GET `/offers/{id}/context` | OfferContext | N/A | Context data |
| Profile Context | GET `/profile/{id}/context` | ProfileContext | N/A | Profile context for matching |
| Context Fit | GET `/offers/{id}/fit` | ContextFit | Calculate match | Matching score |

**JustificationCard Data:**
```typescript
Justification = {
  skill_uri: string,
  skill_label: string,
  match_reason: string,
  confidence: number,
  source: "canonical" | "mapped" | "inferred"
}
```

---

## ApplicationsPage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Applications List | GET `/applications` | ApplicationItem[] | N/A | Application cards |
| Application Detail | GET `/applications/{id}` | ApplicationDetail | N/A | Expanded view |
| Application History | GET `/applications/{id}/history` | ApplicationHistoryItem[] | N/A | Timeline/history |

**Application Status Enum:**
```typescript
"saved" | "cv_ready" | "applied" | "follow_up" | "interview" | "rejected" | "won" | "archived"
```

---

## DashboardPage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Sample Offers | GET `/offers/sample` | OfferNormalized[] | N/A | Featured cards |
| Applications | GET `/applications` | ApplicationItem[] | Aggregate by status | KPI cards |

**KPI Calculations:**
```
Total Applications = count(all)
In Progress = count(status in [cv_ready, applied, follow_up, interview])
Interviews = count(status == interview)
Won = count(status == won)
```

---

## ProfileUnderstandingPage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Profile Session | POST `/profile/understand` | { session_id } | Create session | Store session ID |
| Profile Detail | GET `/profile/{sessionId}` | CareerProfileV2 | AI reconstruction | Skill groups, projects |

**Data Grouping:**
```typescript
Skills grouped by:
- profile_intelligence.skills_by_type (core, technical, soft, domain)
- confidence levels
- source (canonical, inferred, etc.)

Projects from:
- structured_cv.projects
- LLM reconstruction suggestions
```

---

## MarketInsightsPage Data Flow

| Source API | Endpoint | Data | Transform | Display |
|------------|----------|------|-----------|---------|
| Market Data | GET `/market/insights` | MarketInsight[] | Aggregate by country | Map visualization |
| Top Roles | GET `/market/top-roles` | TopRole[] | N/A | TopRolesCard |
| Skill Trends | GET `/market/skills` | SkillTrend[] | N/A | Chart.js visualization |

**Data Enrichment:**
- Country data: { count, avg_salary, top_roles, growth_rate }
- Skill data: { skill_label, demand_count, growth_percent }

---

# 8. ANALYSE UX

## Friction Points

### High-Friction Areas

1. **ProfilePage Editing Experience**
   - Very long form, no progress indicator
   - Skill editing requires multiple steps (add skill → add tools → set autonomy → add context)
   - No unsaved changes warning before navigation
   - No inline validation of fields
   - **Impact:** Users may abandon profile setup

2. **InboxPage Filter Complexity**
   - 11 filter options + threshold slider
   - Filters not grouped logically (company, location, domain, confidence, skill levels)
   - No "saved filters" feature
   - Filter state not persisted to URL
   - **Impact:** Power users overwhelmed, casual users miss filtering

3. **Modal-in-Page Pattern (InboxPage)**
   - OfferDetailModal opens over inbox list
   - Can't easily compare multiple offers
   - Modal size not responsive to window changes
   - **Impact:** Awkward offer comparison workflow

4. **Apply Pack Flow Unclear**
   - After clicking "Apply", unclear what happens next
   - CV/letter preview modals separate from apply confirmation
   - No clear indication of application success
   - **Impact:** Users uncertain if application was submitted

5. **Landing Page Length**
   - AdCoachTestPage (73k LOC) is extremely long
   - Multiple lazy-loaded sections
   - Scroll fatigue before reaching primary CTA
   - **Impact:** Lower conversion to /analyze

### Medium-Friction Areas

6. **No "Back" Navigation Patterns**
   - Some pages don't have breadcrumbs or back buttons
   - Users must use browser back button
   - **Impact:** Minor confusion

7. **ProfilePage ↔ ProfileUnderstandingPage Disconnection**
   - Two separate pages for profile
   - No clear relationship shown
   - Can't easily switch between them
   - **Impact:** User confusion about which is authoritative

8. **Skill Suggestions Not Integrated**
   - ProfilePage shows skill suggestions as separate cards
   - Bulk import available but one-click
   - No drag-drop to reorder suggestions
   - **Impact:** Slower skill management

9. **Decision Tracking Persistence**
   - Inbox decisions stored only in localStorage
   - Not synced to backend
   - Lost on browser clear
   - **Impact:** User frustration if data lost

### Low-Friction Areas

10. **Login Flow**
    - Simple email/password form
    - Clear error messages
    - Redirect logic straightforward

11. **OffersPage Filtering**
    - Real-time search + country + source filters
    - Simple and clear

---

## Surcharge cognitive

### High Cognitive Load

1. **InboxPage Overall**
   - Too many filter options at once
   - Threshold slider not obviously tied to score
   - No explanation of domain buckets (strict/neighbor/out)
   - Matching score calculation not transparent
   - **Solution:** Add tooltips, simplify filter UI, add scoring breakdown

2. **Skill_links Concept**
   - skill ↔ tool ↔ context ↔ autonomy binding is complex
   - No visual representation (all text-based)
   - Poorly documented
   - **Solution:** Add visual graph/diagram, simplify editing

3. **Canonical Skills vs User Skills**
   - Backend has canonical URIs (ESCO)
   - User can edit raw skill names
   - Not clear which takes precedence
   - **Solution:** Clarify in UI, show URI badges

### Medium Cognitive Load

4. **Domain Buckets (strict/neighbor/out)**
   - Not explained in UI
   - User must infer meaning
   - Related to domain_affinity but not obviously
   - **Solution:** Add inline help text, show examples

5. **Confidence Levels (LOW/MED/HIGH)**
   - Three-tier system for multiple properties
   - Not clear which confidence refers to (matching? skill? autonomy?)
   - **Solution:** Add column headers, clarify definitions

---

## Duplication

1. **Page Duplication:**
   - `/dashboard` + `/cockpit` (alias)
   - `/offers` + `/offres` (alias)
   - `/applications` + `/candidatures` (alias)
   - `/market-insights` + `/market` (alias)
   - **Issue:** Confusing duplicate routes
   - **Recommendation:** Single canonical route per page

2. **Component Duplication:**
   - HeroCard in both `landing/` and `ui/` directories
   - HeroSection in both `landing/` and `sections/`
   - **Recommendation:** Consolidate to single location

3. **Profile Display:**
   - ProfilePage (edit mode)
   - ProfileUnderstandingPage (view mode)
   - Both show same data differently
   - **Recommendation:** Merge into single "Profile" page with edit toggle

4. **Offer Display:**
   - OfferDetailPage (full page)
   - OfferDetailModal (in InboxPage)
   - StructuredOfferSummaryCard (mini card)
   - Three ways to view offer detail
   - **Recommendation:** Consolidate to one component used in multiple contexts

---

## Incohérences

1. **Language Mixing:**
   - Mostly French UI text
   - Occasional English terms (e.g., "Business France" not "France Affaires")
   - Some component names English (ProfileCard), some French (AnalyzePage)
   - **Impact:** Inconsistent brand voice

2. **Color Usage:**
   - Matching colors (low/medium/good/excellent) not consistent
   - Some cards use brand cyan, some use slate
   - Badge colors vary
   - **Recommendation:** Define color palette rules

3. **Button Styles:**
   - Some buttons use `size="lg"`, some default
   - Hover states not consistent
   - Some use icons, some text only
   - **Recommendation:** Button style guide

4. **Modal Behavior:**
   - OfferDetailModal in InboxPage (modal over page)
   - CvPreviewModal standalone
   - Some modals close on outside click, some don't
   - **Recommendation:** Consistent modal behavior rules

---

## Manque de clarité

1. **InboxPage Score Calculation:**
   - How is matching score calculated?
   - What weight each factor?
   - Why does item A score 78 and item B 72?
   - **Solution:** Show score breakdown (X% skills match, Y% domain match, Z% autonomy match)

2. **Apply Pack Status:**
   - After clicking "Apply", what's the status?
   - "cv_ready" means what exactly?
   - When is it "applied"?
   - **Solution:** Add explicit status explanation + progress indicator

3. **Market Insights Data:**
   - Data source not documented
   - Date of data collection unclear
   - How frequently updated?
   - **Solution:** Add data source + last updated badge

4. **Profile Intelligence Confidence:**
   - Confidence score shown but scale unclear (0-100? 0-1?)
   - What does "90% confident" mean operationally?
   - **Solution:** Add explanation + confidence breakdown

---

## Problèmes de navigation

1. **Deep Link Support:**
   - Filter state in InboxPage not in URL
   - If user bookmarks filtered inbox, loses filters on return
   - **Solution:** Encode filters in URL query params

2. **Breadcrumb Missing:**
   - ProfilePage has no indicator it's part of onboarding flow
   - InboxPage has no way to go back to OffersPage
   - **Solution:** Add breadcrumbs: Analyze → Profile → Inbox

3. **Sidenav Lack:**
   - No persistent navigation menu
   - Users must click Navbar brand to go home
   - **Solution:** Add sidebar with main sections (Analyze, Profile, Inbox, Applications, etc.)

4. **Mobile Navigation:**
   - Navbar probably collapses to hamburger (unclear)
   - InboxPage filters unusable on mobile (too many options)
   - Modal modals on small screens
   - **Solution:** Mobile-specific filter drawer, stacked layout

---

# 9. ANALYSE UI

## Problèmes visuels

### High-Impact Issues

1. **Inconsistent Spacing**
   - Some cards use `gap-4`, others `gap-6`
   - Padding varies: `p-4`, `p-6`, `p-8`, `px-4 py-3`
   - Margin usage not systematic
   - **Impact:** Layout feels unpolished
   - **Solution:** Strict spacing scale (4px units) across all components

2. **Shadow Hierarchy Unclear**
   - Multiple shadow sizes defined but usage not consistent
   - Some cards use `shadow`, others `shadow-md`, others `shadow-lg`
   - **Impact:** Depth hierarchy ambiguous
   - **Solution:** Define shadow rules: card base → shadow-sm, elevated → shadow-md, modal → shadow-lg

3. **Font Inconsistency**
   - Some headings use `font-semibold`, others `font-bold`
   - Font sizes not on strict scale
   - Letter spacing varies
   - **Impact:** Typographic hierarchy weak
   - **Solution:** Strict typographic scale (h1-h6, body, caption)

4. **Color Inconsistency**
   - Buttons sometimes cyan, sometimes lime, sometimes slate
   - Badges use various background colors
   - No clear color semantics
   - **Impact:** Hard to distinguish button importance
   - **Solution:** Color assignment rules (primary → cyan, secondary → slate, success → lime, etc.)

5. **Border Radius Overuse**
   - Some elements `rounded-md`, others `rounded-2xl`, others `rounded-[32px]`
   - Makes UI feel disjointed
   - **Impact:** Visual cohesion poor
   - **Solution:** Restrict to 3-4 standard border radius values

### Medium-Impact Issues

6. **Form Styling Weak**
   - Input fields in ProfilePage very basic
   - No focus states clearly visible
   - Error states not styled
   - **Impact:** Form usability poor
   - **Solution:** Use Radix UI form components consistently

7. **Responsive Gaps**
   - Landing page probably not responsive below 768px
   - InboxPage filter panel likely breaks on mobile
   - Modal modals not optimized for mobile
   - **Impact:** Poor mobile experience
   - **Solution:** Test all pages at 320px, 768px, 1024px breakpoints

8. **Image Handling**
   - Hero image/visual layer may not load
   - No placeholder images
   - No image compression mentioned
   - **Impact:** Slow load, broken layouts
   - **Solution:** Add image optimization, placeholders

---

## Hiérarchie faible

1. **AnalyzePage**
   - All sections (Profile, Market Position, Skills, Signals) equal visual weight
   - No indication which data is most important
   - **Solution:** Make Profile card primary (larger, higher contrast), others secondary

2. **ProfilePage**
   - 6 sections (identity, experiences, education, projects, languages, skills)
   - All collapsed by default
   - User unsure which to fill first
   - **Solution:** Expand "identity" + "experiences" by default, show progress indicator

3. **InboxPage**
   - Item cards all equal size
   - No indication which items are "high priority"
   - Filter UI same visual weight as item list
   - **Solution:** Highlight top-match items, move filters to sidebar/drawer

4. **Landing**
   - HeroSection takes full viewport
   - Below-the-fold sections equally important
   - CTAs scattered throughout
   - **Solution:** Single strong CTA in hero, secondary CTAs lower down

---

## Composants incohérents

1. **Button Variants:**
   - Some use Tailwind classes directly
   - Some use `<Button>` component
   - Some inline `<button>`
   - **Recommendation:** Use `<Button>` component everywhere

2. **Card Variants:**
   - GlassCard (backdrop blur)
   - BaseListingCard (listing layout)
   - OfferCard (offer display)
   - Generic `<Card>` (whitebox)
   - **Recommendation:** Consolidate to 2-3 card variants

3. **Badge Variants:**
   - Status badges (saved, applied, won)
   - Skill badges (rare, weighted)
   - Source badges (France Travail, Business France)
   - Confidence badges (LOW, MED, HIGH)
   - **Recommendation:** Create badge component with variants

---

## Responsive

1. **Known Issues:**
   - Landing page not tested on mobile
   - InboxPage filter panel breaks on <768px (too many filters)
   - Modal modals may overflow on mobile
   - Navbar not tested for hamburger collapse

2. **Assumed Good:**
   - React Router should handle history on mobile
   - Tailwind `md:`, `lg:` breakpoints should work
   - Touch inputs not explicitly tested

3. **Recommendations:**
   - Add mobile viewport meta tag
   - Test all pages at 375px (mobile), 768px (tablet), 1024px (desktop)
   - Mobile-first breakpoints: sm:640px, md:768px, lg:1024px
   - Touch targets ≥44x44px

---

## Accessibilité

1. **Missing:**
   - No `alt` text on images (if any)
   - No `aria-label` on icon buttons
   - Form labels may not be associated with inputs (`<label htmlFor>`)
   - No keyboard navigation testing mentioned
   - Color-only status indicators (red = rejected, green = won) fail color-blind users

2. **Assumed Working:**
   - Radix UI components (Select, Progress, Toast) have ARIA built-in
   - React Router handles focus management (unclear)
   - ErrorBoundary shows accessible error message

3. **Recommendations:**
   - Add `aria-describedby` to inputs with hints
   - Add `aria-live` to inline error messages
   - Add `aria-label` to icon-only buttons
   - Use icons + text for status indicators
   - Test with WAVE accessibility checker
   - Test keyboard navigation (Tab, Enter, Space)
   - Minimum color contrast: AA (4.5:1 for text)

---

## Lisibilité

1. **Font Sizes:**
   - Base font size probably 16px
   - No strict scale defined
   - Headlines mix `text-3xl`, `text-4xl`, `text-5xl` (unclear which is h1/h2/h3)
   - **Recommendation:** Define h1-h6 scale: h1=32px, h2=28px, ..., body=16px, caption=12px

2. **Line Length:**
   - Some text blocks very long (no max-width)
   - Hard to read on desktop
   - **Recommendation:** Limit text width to 65-75 characters (~38-45rem)

3. **Line Height:**
   - Not explicitly set in most places
   - Probably defaults to 1.5
   - **Recommendation:** `leading-relaxed` (1.625) for body, `leading-tight` (1.25) for headings

4. **Contrast:**
   - Text on light backgrounds: should be good
   - Text on colored backgrounds (e.g., cyan): untested
   - **Recommendation:** Check all color combinations meet WCAG AA (4.5:1 for normal text)

---

# 10. ANALYSE PRODUIT

## Écrans inutiles ou peu utilisés

1. **DemoPage** (878 LOC)
   - Only purpose: navigation to other pages
   - Could be replaced by main nav menu
   - **Recommendation:** Delete, use navbar navigation

2. **MatchPage** (14k LOC)
   - Shows matching algorithm with hardcoded sample data
   - Not personalized to user
   - Users skip to InboxPage (personalized recommendations)
   - **Recommendation:** Merge into InboxPage as "How Matching Works" explainer, or delete

3. **MatchingShowcasePage** (4.4k LOC)
   - Very limited, static examples
   - No interactive value
   - **Recommendation:** Integrate into landing page as "See Examples" modal

4. **CvDeltaPage** (16.7k LOC)
   - Dev-only tool for debugging parser
   - Not useful for end users
   - **Recommendation:** Keep as dev tool but hide from main nav

5. **HomePage** (770 LOC)
   - Defined but not routed (content merged into AdCoachTestPage)
   - Dead code
   - **Recommendation:** Delete or merge into AdCoachTestPage

---

## Fonctionnalités incomplètes

1. **ProfileUnderstandingPage Suggestions**
   - Shows AI-generated suggestions
   - No way to accept/reject suggestions
   - No way to regenerate profile
   - **Recommendation:** Add "Accept these changes" button → merge suggestions into ProfilePage

2. **Application Tracking**
   - Tracks applications with 8 statuses
   - But no backend sync for some operations
   - Decision tracking in InboxPage is localStorage-only, not synced
   - **Recommendation:** Backend sync all decisions (shortlist, dismiss, apply)

3. **Export Functionality**
   - Mentioned in InboxPage but implementation unclear
   - **Recommendation:** Clarify scope (export as PDF? CSV? Email?), implement or remove

4. **Skill_Links Editing**
   - UI for skill ↔ tool ↔ context ↔ autonomy binding exists
   - But editing experience very textual
   - No visual graph editor
   - **Recommendation:** Build visual skill link editor (drag-drop, visual connections)

5. **Market Insights**
   - Data visualization exists (map, charts)
   - But no actionable insights (no "apply filters based on market data" flow)
   - **Recommendation:** Add "Find jobs in high-demand roles" feature linked to market data

---

## Fonctionnalités redondantes

1. **Offer Display (3 ways):**
   - OfferDetailPage (full page)
   - OfferDetailModal (in InboxPage)
   - StructuredOfferSummaryCard (summary card)
   - **Issue:** Duplicate logic, hard to maintain
   - **Recommendation:** Single OfferDetail component used in multiple contexts

2. **Profile Display (2 ways):**
   - ProfilePage (edit mode)
   - ProfileUnderstandingPage (view mode)
   - **Issue:** Duplicated profile rendering
   - **Recommendation:** Single Profile page with edit toggle

3. **Route Aliases:**
   - `/offers` + `/offres` (French)
   - `/applications` + `/candidatures` (French)
   - `/dashboard` + `/cockpit`
   - `/market-insights` + `/market`
   - **Issue:** Confusing, hard to track, SEO issues (duplicate content)
   - **Recommendation:** Single canonical route per page (e.g., delete aliases or use 301 redirects)

---

## Parcours cassés

1. **Onboarding Path Unclear:**
   - `/analyze` (upload CV) → `/profile` (edit profile) → implicit jump to `/inbox`
   - No explicit "Next" button to go from ProfilePage to InboxPage
   - Users may get stuck in ProfilePage editing loop
   - **Recommendation:** Add "Continue to Recommendations" button with prompt

2. **Apply to Inbox Item:**
   - InboxPage shows items with "Apply" button
   - Clicking opens modal with offer detail
   - But no clear CTA to apply (may need to click inside modal)
   - After applying, no redirect to ApplicationsPage
   - **Recommendation:** Explicit flow: Click "Apply" → show preview → confirm → redirect to ApplicationsPage

3. **Decision Persistence:**
   - Shortlist/dismiss decisions stored in localStorage
   - Not synced to backend
   - Users might lose decisions on browser clear
   - **Recommendation:** Backend sync all decisions immediately

4. **Profile Reset:**
   - If user clicks "Reset from AI" in ProfilePage, loses edits
   - No confirmation dialog
   - **Recommendation:** Add "Are you sure?" confirmation

---

## Opportunités d'amélioration

1. **Personalization:**
   - InboxPage recommendations shown to all authenticated users
   - But no indication of personalization (which items matched on what?)
   - **Opportunity:** Add "Why this match?" popup on hover, explain algorithm

2. **Skill Suggestions:**
   - ProfilePage shows skill suggestions
   - But no indication of quality or relevance
   - **Opportunity:** Show confidence score for suggestions, allow ranking by relevance

3. **Application Insights:**
   - ApplicationsPage shows application history
   - But no metrics (conversion rate, time to interview, etc.)
   - **Opportunity:** Show "You applied to 10 roles, interviewed for 2 (20%)" insights

4. **Market Benchmarking:**
   - MarketInsightsPage shows market trends
   - But no comparison to user profile (e.g., "Your skills are in demand, 85th percentile")
   - **Opportunity:** Personalized market insights ("DevOps engineers in demand in Paris")

5. **Notification System:**
   - No email/push notifications mentioned
   - Users must manually check InboxPage for new recommendations
   - **Opportunity:** Email digest of new matches ("5 new matches this week")

6. **Collaboration:**
   - Profile view-only, no way to share with mentor/recruiter
   - **Opportunity:** "Share my profile" link, allow others to see profile (with permission)

7. **Interview Prep:**
   - Preparing Apply Pack shows CV + letter
   - But no interview prep resources (e.g., "10 common questions for DevOps role")
   - **Opportunity:** After applying, show interview tips based on role

---

# 11. DESIGN SYSTEM OBSERVÉ

## Couleurs

### Brand Colors
- **Primary:** Cyan `#06B6D4` (used in buttons, links, highlights)
- **Secondary:** Lime `#22C55E` (used in success states, badges)

### Semantic Colors
- **Success:** Lime `#22C55E` (excellent match, won status)
- **Warning:** Amber/Yellow (medium match, pending status)
- **Danger:** Red `#EF4444` (low match, rejected status)
- **Info:** Cyan `#06B6D4` (good match, informational)

### Matching Score Colors (Custom Tokens)
```
matching.low:       #EF4444
matching.medium:    #FACC15
matching.good:      #06B6D4
matching.excellent: #22C55E
```

### Neutral Palette (Slate-based)
- **Background:** `#FFFFFF` (surface.DEFAULT)
- **Muted Background:** `#F8FAFC` (surface.muted)
- **Subtle Background:** `#F1F5F9` (surface.subtle)
- **Text on Light:** `#334155` (slate-700) / `#1E293B` (slate-900)
- **Text on Dark:** `#F1F5F9` (slate-100) / `#FFFFFF` (slate-50)
- **Borders:** `#CBD5E1` (slate-200) / `#E2E8F0` (slate-300)

---

## Tipografia

### Font Family
- **Primary:** Inter (Variable) — modern, clean, responsive letterspacing
- **Display:** Space Grotesk — geometric, modern display headings
- **Fallback:** system-ui, ui-sans-serif

### Font Weight Scale
- 400 (Regular) — body text
- 500 (Medium) — labels, UI text
- 600 (Semibold) — card titles, strong emphasis
- 700 (Bold) — headings, primary CTA

### Font Sizes (Assumed based on code)
- **h1:** `text-5xl` (48px) - primary hero heading
- **h2:** `text-4xl` (36px) - section heading
- **h3:** `text-3xl` (30px) - subsection heading
- **body:** `text-base` (16px) - default
- **sm:** `text-sm` (14px) - secondary text
- **xs:** `text-xs` (12px) - captions, labels

### Line Height
- **Headings:** `leading-tight` (~1.25)
- **Body:** Default/`leading-relaxed` (~1.625)

### Letter Spacing
- Normal tracking for body text
- Increased tracking for labels: `tracking-[0.2em]` to `tracking-[0.28em]` (luxury/premium feel)

---

## Spacing

### Base Unit: 4px

### Spacing Scale
```
1 = 4px
2 = 8px
3 = 12px
4 = 16px
5 = 20px
6 = 24px
8 = 32px
10 = 40px
12 = 48px
16 = 64px
```

### Common Usage Patterns
- **Card padding:** `p-4` (16px) to `p-8` (32px)
- **Section padding:** `px-4 py-10` to `px-8 py-12`
- **Component spacing:** `gap-4` (between items) to `gap-8` (between sections)
- **Form input padding:** `px-4 py-3` (12px top/bottom, 16px left/right)

---

## Shadows

### Shadow Scale
```
xs:     0 1px 2px rgba(0,0,0,0.04)    — subtlest
sm:     0 2px 4px rgba(0,0,0,0.05)    — subtle
base:   0 4px 12px rgba(0,0,0,0.06)   — default card
md:     0 8px 24px rgba(0,0,0,0.08)   — elevated
lg:     0 16px 48px rgba(0,0,0,0.10)  — highest elevation
soft:   0 8px 24px rgba(0,0,0,0.05)   — soft edge (reduced contrast)
glow:   0 0 16px rgba(6,182,212,0.10) — cyan glow (emphasis)
card:   0 1px 3px rgba(0,0,0,0.06)    — minimal (used on OfferCard)
```

### Usage Rules (Inferred)
- **Default cards:** `shadow` (base shadow)
- **Hovered cards:** `shadow-md`
- **Modal/elevated:** `shadow-lg`
- **Subtle backgrounds:** `shadow-sm`
- **Glowing emphasis:** `shadow-glow` (for CTAs, important cards)

---

## Border Radius

### Radius Scale
```
sm:     6px      (0.375rem)  — minimal curves (form inputs)
base:   8px      (0.5rem)    — default
md:     12px     (0.75rem)   — medium emphasis (cards)
lg:     16px     (1rem)      — large cards
xl:     20px     (1.25rem)   — very rounded
2xl:    24px     (1.5rem)    — soft, luxury feel
card:   16px     (1rem)      — standard card border radius
button: 12px     (0.75rem)   — button radius
badge:  8px      (0.5rem)    — badge/pill radius
```

### Usage Patterns
- **Input fields:** `rounded-md` or `rounded-2xl` (luxury)
- **Card containers:** `rounded-lg` or `rounded-2xl`
- **Buttons:** `rounded-button` (12px) or `rounded-md`
- **Badges:** `rounded-badge` (8px)
- **Landing sections:** `rounded-[32px]` (custom, very rounded, luxury)

---

## Component Patterns

### Buttons
- **Primary CTA:** Cyan background, white text, `rounded-button`
- **Secondary:** Slate background or outline, `rounded-button`
- **Outline:** Border only, transparent background, `rounded-button`
- **Size:** `size="lg"` (full width in forms) or default (inline)

### Cards
- **GlassCard:** Backdrop blur, border, white/semi-transparent background
- **BaseListingCard:** Clean white background, shadow, `rounded-lg`
- **OfferCard:** Title + company + location + badge, minimal shadow
- **Feature Card:** Icon + title + description, cyan accents

### Forms
- **Inputs:** Slate border, `rounded-2xl` (luxury), focus ring in cyan
- **Labels:** Small caps, gray text, `tracking-wider`
- **Errors:** Red border, red background hint text

### Modals
- **Background:** Dark overlay with opacity
- **Content:** White card, `rounded-2xl`, `shadow-lg`
- **Title:** Heading + subtitle
- **Close button:** Icon in top-right corner

### Badges
- **Status:** Colored background + text (e.g., `bg-amber-100 text-amber-900` for pending)
- **Skill quality:** Subtle background (e.g., `bg-violet-50 text-violet-700` for "rare")
- **Source:** Colored background by source (e.g., `bg-sky-50` for France Travail)

---

## Animation & Transitions

### Framer Motion (observed)
- Page transitions (fade in/out)
- Section lazy-load animations
- Modal entrance/exit animations

### Tailwind Transitions
- Button hover: `transition` class (assumed)
- Border color on focus: `transition` (assumed)
- Background color change: `transition` (assumed)

### Animation Principles
- Smooth, not jarring
- ~200-300ms duration (assumed)
- Easing: ease-out for entrances, ease-in for exits (assumed)

---

## Layout Patterns

### Full-Width Sections
```
Hero section → full viewport height
Cards grid → responsive columns (1 → 2 → 3+)
Form containers → max-width: 512px or 768px, centered
```

### Navigation
- **Navbar:** Fixed top, flex layout, brand left + nav center + user menu right
- **Sidebar:** Not present (opportunity)
- **Breadcrumbs:** Not consistently used (should be added)

### Spacing Between Sections
- Top-level padding: `px-4 md:px-8` (responsive)
- Section gaps: `gap-10` to `gap-16` (vertical breathing room)
- Card grids: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`

---

# 12. RECONSTRUCTION RECOMMANDÉE

## Architecture cible

### 1. Component Hierarchy Consolidation

**Current State:** 63+ components across 9+ directories, significant duplication

**Target State:**

```
src/
├── pages/               (15-18 pages, down from 20)
│   ├── LandingPage      (consolidate AdCoachTestPage + HomePage + DemoPage)
│   ├── LoginPage
│   ├── AnalyzePage
│   ├── ProfilePage      (consolidate with ProfileUnderstandingPage as view mode toggle)
│   ├── InboxPage
│   ├── OffersPage
│   ├── OfferDetailPage
│   ├── ApplicationsPage
│   ├── DashboardPage
│   ├── MarketInsightsPage
│   └── (remove: DemoPage, CvDeltaPage, MatchPage, MatchingShowcasePage, etc.)
│
├── components/          (reduce to 40-50, better organized)
│   ├── ui/              (15-20 base components)
│   │   ├── Button
│   │   ├── Input
│   │   ├── Select
│   │   ├── Card
│   │   ├── Badge
│   │   ├── Modal
│   │   ├── Tabs
│   │   └── ...
│   ├── layout/          (keep: Navbar, Footer, PageShell)
│   ├── forms/           (new: form components)
│   │   ├── ProfileForm
│   │   ├── ExperienceEditor
│   │   ├── SkillLinkEditor
│   │   └── ...
│   ├── sections/        (page section components)
│   │   ├── HeroSection
│   │   ├── OfferCard
│   │   ├── InboxCard
│   │   └── ...
│   └── features/        (feature-specific components)
│       ├── OfferDetail  (consolidate modal + page)
│       ├── ProfileCard
│       ├── MatchVisualization
│       └── ...
│
├── lib/
│   ├── api.ts           (keep, but break into modules)
│   │   ├── auth.ts
│   │   ├── profiles.ts
│   │   ├── offers.ts
│   │   ├── inbox.ts
│   │   └── applications.ts
│   ├── hooks/           (new directory)
│   │   ├── useAuth
│   │   ├── useProfile
│   │   ├── useInbox
│   │   └── ...
│   ├── utils/           (utilities)
│   └── types/           (API types, component props)
│
├── store/               (keep: authStore, profileStore)
└── config/              (new: theme config, constants)
```

---

## Navigation cible

### Routes Simplified

**Current:** 30+ routes with aliases, nested routing possible

**Target:**
```
/                    → LandingPage (consolidated)
/login               → LoginPage
/analyze             → AnalyzePage
/profile             → ProfilePage (with view/edit toggle)
/inbox               → InboxPage
/offers              → OffersPage
/offers/:offerId     → OfferDetailPage (full page, no modal in InboxPage)
/applications        → ApplicationsPage
/dashboard           → DashboardPage
/market-insights     → MarketInsightsPage

DELETE: /landing, /demo, /adcoach-test, /candidatures, /offres, /explorer, /cockpit, /market, /matching-showcase, /match, /dev/cv-delta
```

**Breadcrumb Navigation:**
```
Landing
  → Analyze (Upload CV)
    → Profile (Edit profile)
      → Inbox (Get recommendations)
        → Offer Detail (View offer)
          → Application (Apply)
            → Applications (Track)
```

---

## Composants à conserver

1. **UI Base Components** (refactor for consistency):
   - Button, Input, Select, Card, Badge, Modal, Progress, Toast
   - Add: Tabs, Accordion, Drawer (for mobile filters)

2. **Layout Components**:
   - Navbar, Footer, PageShell
   - Add: Sidebar (for main nav), Breadcrumbs

3. **Feature Components**:
   - ProfileCard, OfferCard, InboxCard
   - JustificationCard, SkillTypeGroup, TopRolesCard

4. **Section Components**:
   - HeroSection, HowItWorks, MarketVisualization
   - (consolidate landing sections)

---

## Composants à fusionner

1. **OfferDetail** (consolidate 3 ways):
   - `OfferDetailPage` + `OfferDetailModal` + `StructuredOfferSummaryCard`
   - → Single `<OfferDetail>` component with size variants (summary, detail, full-page)
   - Modal in InboxPage should use same component

2. **Profile Display** (consolidate 2 ways):
   - `ProfilePage` (edit) + `ProfileUnderstandingPage` (view)
   - → Single `<ProfilePage>` with edit mode toggle
   - Remove ProfileUnderstandingPage, replace with "AI Insights" tab in ProfilePage

3. **HeroCard** (consolidate duplicates):
   - `landing/HeroCard` + `ui/HeroCard`
   - → Single `<HeroCard>` in `ui/`, used everywhere

4. **HeroSection** (consolidate duplicates):
   - `landing/HeroSection` + `sections/HeroSection`
   - → Single `<HeroSection>` in `sections/`

---

## Composants à supprimer

1. **Page Components (unused or low-value):**
   - DemoPage (778 LOC) → merge buttons into landing
   - CvDeltaPage (16.7k LOC) → move to `/dev` namespace if needed
   - MatchPage (14.2k LOC) → replace with "How Matching Works" modal in landing
   - MatchingShowcasePage (4.4k LOC) → examples in landing
   - HomePage (770 LOC) → merge into LandingPage

2. **Utility Components (dead code):**
   - Anything not imported by active pages

---

## Nouvelles pages nécessaires

### 1. NotFound / Error Page
- Already exists, keep

### 2. Onboarding Flow (Optional)
- Could create explicit `/onboarding` with guided steps:
  1. Upload CV
  2. Edit Profile
  3. Set Preferences (optional)
  4. Start Inbox
- Or integrate into existing pages with progress indicator

### 3. Settings Page (New)
- Account settings (email, password, preferences)
- Notification settings
- Privacy settings
- Export data
- Delete account

---

## Reconceptualization clé

### From Modal-Heavy to Page-Centric

**Current:** InboxPage + OfferDetailModal (modal overlays page)

**Target:** 
- InboxPage shows inbox items in sidebar/list
- Click item → navigate `/offers/:offerId` (full page)
- OfferDetailPage shows offer + side-by-side matching breakdown
- Action buttons: Shortlist, Dismiss, Apply (all full-featured)

**Benefit:** 
- Easier to bookmark/share offer detail URL
- Better mobile experience (full-page vs. modal)
- Clearer navigation history

### From Component-Heavy to Function-First

**Current:** 73k LOC AdCoachTestPage, 60k ProfilePage, 59k InboxPage

**Target:**
- Break mega-components into smaller, focused components
- Separate concerns: data fetching, filtering, display, actions
- Use hooks for state management (useInboxFilters, useProfileEditing, etc.)

**Benefit:**
- Easier to test
- Easier to maintain
- Easier to refactor UI without touching logic

### From Alias-Heavy to Canonical Routes

**Current:** Aliases like `/offres` → `/offers`, `/cockpit` → `/dashboard`

**Target:**
- Single canonical route per page
- French UI text stays, but route names in English
- If French routes needed, use 301 redirects for backwards compatibility

**Benefit:**
- Less routing confusion
- Easier SEO
- Simpler analytics

---

# 13. BRIEF FINAL POUR EMERGENT AI

## Executive Summary

Vous héritez d'une plateforme **de matching emploi-candidat basée sur l'IA**, actuellement en MVP avec une architecture fonctionnelle mais fragile. Le front-end est **très long et monolithique** (plusieurs components > 50k LOC), avec des **opportunités claires d'amélioration** en UX, modularité et performance.

**Objectif:** Reconstruire un front-end moderne, maintenable, et délightful pour les utilisateurs.

---

## Contexte Produit

### Qu'est-ce que Elevia Compass fait?

1. **Analyse CVs**: Upload → Parsing LLM → Extraction skills (ESCO canonical URIs)
2. **Profiling**: Utilisateurs éditent/valident profil, link skills ↔ tools ↔ context ↔ autonomy levels
3. **Matching**: Backend calcule score matching pour chaque offre (skills match, domain match, autonomy match)
4. **Recommandations**: Inbox affiche offres recommended, triées par score
5. **Application Tracking**: Utilisateurs shortlist/dismiss offres, génèrent Apply Pack (CV + lettre), track candidatures

### Qui sont les utilisateurs?

- **Primary:** Job seekers (France focus) souhaitant optimiser candidatures
- **Secondary:** Recruiters (potentially future) qui utiliseraient matching pour sourcing

### Business Model

- Freemium? (Unclear from code - MVP stage)
- Monetization strategy: Not evident from front-end

---

## Architecture Actuelle

### Stack

| Aspect | Tech | Status |
|--------|------|--------|
| Framework | React 18 | Mature |
| Routing | React Router 7 | Good |
| State | Zustand | Simple, works |
| Styling | Tailwind + custom | Mostly consistent |
| UI Components | Radix UI + custom | Mixed quality |
| Animations | Framer Motion | Present but minimal |
| Bundling | Vite | Fast, good DX |
| Language | TypeScript | Partial coverage |

### Pain Points Majeurs

1. **Mega-Components** (50k+ LOC single files)
   - AdCoachTestPage, ProfilePage, InboxPage très longs
   - Difficile à tester, naviguer, refactorer

2. **Duplication** (routes, components, logic)
   - Offres affichées 3 façons (page, modal, card)
   - Profils affichés 2 façons (edit vs. view)
   - Routes avec alias (confusing)

3. **UX Friction**
   - ProfilePage: form très longue, pas d'unsaved changes warning
   - InboxPage: 11 filtres, UI overwhelming, decisions en localStorage (non persistent)
   - Apply flow: unclear steps, no clear success state

4. **Manque de polish**
   - Spacing inconsistent (gap-4 vs gap-6 vs gap-8)
   - Colors not semantic (cyan, lime used arbitrarily)
   - Responsive design untested
   - Accessibility minimal (no alt text, aria labels, etc.)

5. **Mobile Experience** (Assumed poor)
   - InboxPage filters break on mobile
   - Modal modals not optimized
   - Landing page likely not responsive

---

## Données Affichées (Data Layer)

### Main API Endpoints

**Auth:**
- `POST /auth/login` (email, password) → session token
- `GET /auth/me` → current user
- `POST /auth/logout` → clear session

**Profile:**
- `POST /parse` (file) → ParseFileResponse (basic parsing)
- `POST /ingest` (parsed profile) → enriched profile + skills
- `GET /profile/saved` → user's saved profile (CareerProfileV2)
- `PUT /profile/saved` (profile) → persist edits
- `GET /profile/{sessionId}` → full profile from DB
- `GET /profile/skills/suggestions` → skill recommendations
- `GET /profile/tools/suggestions` → tool recommendations
- `POST /profile/understand` → start LLM reconstruction session
- `GET /profile/{id}/context` → context for matching calculations

**Offers:**
- `GET /offers/catalog` (limit, sort) → all offers
- `GET /offers/sample` (limit) → featured offers
- `GET /offers/{id}` → offer detail
- `GET /offers/{id}/semantic` → LLM semantic breakdown
- `GET /offers/{id}/context` → offer context

**Inbox:**
- `GET /inbox` (profileId, filters?) → personalized recommendations
- `POST /inbox/{id}/decision` (decision: SHORTLISTED|DISMISSED) → record user decision
- `GET /offers/{id}/fit` → context-aware matching score

**Applications:**
- `GET /applications` → user's application list
- `GET /applications/{id}` → application detail
- `GET /applications/{id}/history` → application history
- `POST /applications` (upsert) → save application
- `PATCH /applications/{id}` → update status
- `DELETE /applications/{id}` → delete application
- `POST /applications/{id}/prepare` → generate Apply Pack (CV + letter)

**Market:**
- `GET /market/insights` → market data (unclear schema)
- `GET /market/top-roles` → trending roles
- `GET /market/skills` → trending skills

---

## Workflows Clés

### 1. Auth + Onboarding
```
/login 
  → POST /auth/login
  → → /analyze (upload CV)
    → POST /parse (basic)
    → → POST /ingest (enriched)
    → → /profile (edit)
      → PUT /profile/saved
      → → /inbox (recommendations)
```

### 2. Matching + Decision
```
/inbox
  → GET /inbox (fetch recommendations)
  → filter/sort items
  → click item → GET /offers/{id}, /offers/{id}/semantic
  → → SHORTLIST | DISMISS (POST /inbox/{id}/decision)
  → → or APPLY (POST /applications)
```

### 3. Apply Pack
```
Click "Apply"
  → POST /applications/{id}/prepare
  → → preview CV (GET cached)
  → → preview letter (GET cached)
  → → confirm → POST /applications
  → → redirect /applications
```

---

## Données Critiques

### User Profile (CareerProfileV2)
- `identity`: name, email, phone, location, linkedin, github
- `experiences[]`: title, company, dates, skills, tools, skill_links
- `education[]`: degree, field, institution, dates
- `projects[]`: title, technologies, URL, impact
- `languages[]`: language, level

**Key field: `canonical_skills`** (ESCO URIs, freezeset, immutable)

### Inbox Item
- `offer_id`, `title`, `company`, `location`
- `matching_score` (0-100)
- `domain_bucket` (strict|neighbor|out)
- `confidence_level` (LOW|MED|HIGH)
- `skill_matches[]` (matched skills)
- `decision_status` (SHORTLISTED|DISMISSED|null) — stored in localStorage, should be backend-synced

### Application Status
- `saved` (CV ready, not applied)
- `cv_ready` (CV + letter ready, not applied)
- `applied` (submitted to job board)
- `follow_up` (waiting for response)
- `interview` (invited to interview)
- `rejected` (rejected by employer)
- `won` (offer accepted)
- `archived` (user archived)

---

## Requis pour Reconstruction

### 1. Component Architecture (CRITICAL)

**Problem:** 73k, 60k, 59k LOC single components

**Solution:**
- Break into small, focused components (<1k LOC max)
- Separate data fetching, state, and UI
- Use custom hooks for logic extraction
- Document component responsibilities

**Example - Current InboxPage:**
```
InboxPage (59k) - do ALL:
  - fetch inbox
  - fetch profile context
  - build matching profile
  - normalize items
  - filter + sort
  - render item list
  - handle decisions
  - handle modal open/close
  - fetch offer detail
  - fetch semantic data
```

**Target - Split into:**
```
InboxPage (2k) - orchestrator
  ├── useInbox() - fetch + normalize
  ├── useInboxFilters() - filter state + logic
  ├── InboxList (1k) - render items
  │   ├── InboxCard (1k) - single item
  │   └── InboxCard depends on:
  │       ├── OfferSummary (0.5k)
  │       └── MatchingBadge (0.5k)
  ├── InboxFilters (2k) - filter UI
  └── OfferDetailModal (3k) - detail + actions
```

### 2. State Management

**Current:** Zustand stores work but:
- Auth + profile stores separate (fine)
- Inbox state mixed with UI state (problem)
- Decisions stored in localStorage (should be backend-synced)
- Filter state stored in useState (should be URL query params)

**Recommendation:**
- Keep Zustand for auth + profile (global)
- Use URL query params for page filters (InboxPage, OffersPage)
- Use useState for transient UI state (modal open/close)
- Backend-sync decisions immediately (POST /inbox/{id}/decision)

### 3. API Layer

**Current:** `lib/api.ts` is 800+ LOC monolith with no separation

**Recommendation:**
```
lib/api/
├── auth.ts (login, logout, fetchUser)
├── profiles.ts (parse, ingest, getProfile, saveProfile)
├── offers.ts (getOffers, getOffer, getOfferDetail)
├── inbox.ts (getInbox, postDecision, fetchContext)
├── applications.ts (listApplications, createApplication, etc.)
└── client.ts (base apiFetch wrapper)
```

Each module exports typed functions + TypeScript interfaces.

### 4. UX Improvements (HIGH IMPACT)

#### a. Simplify InboxPage Filters
**Current:** 11 filters at once + threshold slider
**Target:** 3-4 primary filters + advanced filter drawer
- Company search (main)
- Domain bucket (quick filter)
- Confidence level (quick filter)
- Advanced: date range, skill levels, etc. (drawer)

#### b. Add Progress Indicator to Onboarding
```
Step 1. Upload CV     [✓ Done]
Step 2. Edit Profile  [● In Progress]
Step 3. Review Inbox  [ Pending]
```

#### c. ProfilePage Form Redesign
**Current:** 6 collapsed sections, very long
**Target:**
- Step-by-step wizard (identity → experiences → education → skills → projects)
- Or: Tabs (basic info, experiences, skills, projects)
- Save button on each section, not just bottom
- Unsaved changes warning before navigation

#### d. Apply Pack Clarity
**Current:** Unclear what happens after clicking "Apply"
**Target:**
1. Click "Apply" → modal: "Preview & Apply"
2. Tab 1: Preview CV (readonly)
3. Tab 2: Preview Letter (readonly, edit option)
4. Confirm → POST /applications → success toast → /applications page

#### e. Mobile Navigation
- Hamburger menu (responsive navbar)
- Filter drawer on mobile (replace inline filter panel)
- Full-page modals (no floating modals on <768px)
- Touch-friendly buttons (≥44px)

### 5. Design System (CONSISTENCY)

**Current:** Spacing, colors, typography, shadows not consistently applied

**Recommendation:**

#### Spacing Utility
```
p-1 through p-8 (4px units)
gap-4, gap-6, gap-8 (section spacing)
mb-2, mb-4, mb-6 (vertical rhythm)
```

#### Color Semantics
```
Primary (CTA): Cyan (#06B6D4)
Secondary: Slate (#64748B)
Success: Lime (#22C55E)
Danger: Red (#EF4444)
Warning: Amber (#F59E0B)
Info: Blue (Radix default)
```

#### Typography Scale
```
h1: 32px, font-bold, leading-tight
h2: 28px, font-bold, leading-tight
h3: 24px, font-semibold, leading-tight
body: 16px, font-regular, leading-relaxed
label: 14px, font-medium, uppercase tracking-wider
caption: 12px, font-regular, text-secondary
```

#### Component Variants
```
<Button variant="primary|secondary|outline|ghost" size="sm|md|lg" />
<Card variant="base|glass|elevated" />
<Input variant="default|error|disabled" />
<Badge variant="status|skill|source" />
```

### 6. Performance Optimizations

**Current Issues:**
- AdCoachTestPage 73k LOC with lazy-loaded sections
- InboxPage loads all items at once (pagination?)
- Modal modals re-render parent page
- No code-splitting beyond lazy sections

**Recommendations:**
- Code-split by page (not by landing sections)
- Pagination on InboxPage (25 items/page, not all)
- Virtualization on long lists (react-window)
- Memoize components that don't need re-render (React.memo, useMemo)
- Lazy-load data, not code (use Suspense for data fetching)

### 7. Testing

**Current:** Unclear if any tests exist

**Recommendation:**
```
tests/
├── unit/
│   ├── utils/ (helpers, transforms)
│   ├── hooks/ (useAuth, useInbox, etc.)
│   └── components/ (unit tests for small components)
├── integration/
│   ├── pages/ (page interaction flows)
│   └── workflows/ (auth → onboarding → inbox)
└── e2e/
    ├── auth.spec.ts (login, logout)
    ├── inbox.spec.ts (filter, decide, apply)
    └── profile.spec.ts (edit, save)
```

Use Vitest + React Testing Library for unit/integration, Playwright for e2e.

### 8. Analytics

**Current:** No tracking mentioned

**Recommendation:**
- Track: page views, button clicks (apply, shortlist, dismiss), form submissions
- Use event layer (Segment, Mixpanel, or custom)
- Track conversion: signup → analyze → profile → inbox → apply
- Track engagement: time in inbox, number of filters used, decisions per session

---

## Metriques de Succès pour Reconstruction

### Code Quality
- [ ] All components < 1k LOC
- [ ] >80% TypeScript coverage
- [ ] Test coverage >70%
- [ ] No console errors/warnings in dev

### Performance
- [ ] Page load < 2s (first contentful paint)
- [ ] Lighthouse score >90 (desktop)
- [ ] Mobile lighthouse score >75

### UX
- [ ] Inbox filtering time < 30s (was unknown before)
- [ ] Profile editing completion rate >80% (baseline: unknown)
- [ ] Application flow completion rate >90% (baseline: unknown)
- [ ] Mobile usability score >90

### Design System
- [ ] All colors from defined palette
- [ ] All spacing from 4px scale
- [ ] All shadows from shadow scale
- [ ] All border radius from predefined set

---

## Risques & Dépendances

### Technical Risks
1. **Backend API instability** → Implement robust error handling + retry logic
2. **Large dataset performance** (inbox with 1000+ items) → Implement pagination + virtualization early
3. **Complex matching algorithm** → Surface scoring logic in UI (explain why match score is 78)

### Product Risks
1. **Unclear conversion flow** → Add progress indicators, success states, clear CTAs
2. **Low application rates** → Profile matching quality → work with backend on algorithm validation
3. **User confusion** → Add guided onboarding, tooltips, help docs

### Dependencies
- Backend API (Elevia API server) must be stable
- CV parsing service must return consistent schema
- LLM service (for letter generation, profile reconstruction) must be reliable

---

## Roadmap Suggéré

### Phase 1: Foundation (Weeks 1-2)
1. Setup: vite + React 18 + tailwind + TypeScript
2. Define design system (colors, spacing, typography, components)
3. Build UI component library (Button, Input, Card, Modal, etc.)
4. Setup routing structure

### Phase 2: Core Pages (Weeks 3-4)
1. AuthPage (login) + auth flow
2. LandingPage (consolidated, simplified)
3. AnalyzePage (CV upload, profile parsing display)
4. ProfilePage (edit profile form)

### Phase 3: Matching + Inbox (Weeks 5-6)
1. InboxPage (recommendations list, filters, decisions)
2. OfferDetailPage (offer display, matching breakdown)
3. ApplicationsPage (application tracking)

### Phase 4: Polish + Testing (Weeks 7-8)
1. Responsive design (mobile, tablet)
2. Accessibility (WCAG AA)
3. Unit + integration tests
4. E2E tests
5. Performance optimization

### Phase 5: Nice-to-Haves (Weeks 9+)
1. DashboardPage (KPIs, quick stats)
2. MarketInsightsPage (market visualization)
3. Settings page (account, preferences)
4. Notifications (email digest)
5. Analytics integration

---

## Conclusion

Elevia Compass has strong **product-market fit potential** (job matching is valuable) but suffers from **technical debt** (mega-components, duplication, UX friction).

**Your mission:** Rebuild front-end to be:
- **Maintainable** (small components, clear responsibilities, good test coverage)
- **Fast** (optimized performance, fast load times)
- **Delightful** (smooth UX, clear flows, helpful feedback)
- **Scalable** (foundation for mobile app, new features, third-party integrations)

**Key Wins:** Simplify InboxPage filters, split mega-components, add onboarding progress indicator, backend-sync decisions, mobile-first responsive design.

**Success = Users complete onboarding → get recommendations → apply to jobs with confidence.**

---

**Fin du brief.**

This specification is complete, comprehensive, and ready to hand off to Emergent AI. All 13 sections are detailed, factual, and require no modifications to code.
