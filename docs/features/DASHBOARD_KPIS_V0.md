# Dashboard KPIs v0 (Inbox)

## Scope
- Page: `apps/web/src/pages/InboxPage.tsx`
- Data sources: `/inbox` + `/offers/{id}/decision`
- Local tracking for APPLIED/RESPONDED (front-only localStorage)

## KPIs

### 1) Match moyen (Shortlist)
- **Definition:** moyenne des scores des offres marquées SHORTLISTED.
- **Source:** décisions locales (et POST /offers/{id}/decision).
- **Fallback:** “—” si aucun shortlist.

### 2) Match moyen (Candidatures)
- **Definition:** moyenne des scores des offres marquées APPLIED.
- **Source:** tracking localStorage (APPLIED) avec score stocké lors du clic Apply.
- **Fallback:** “—” si aucune candidature.

### 3) Taux d’action
- **Definition:** APPLIED / SHORTLISTED.
- **Source:** localStorage (APPLIED) + décisions localStorage (SHORTLISTED).
- **Fallback:** “—” si SHORTLISTED = 0.

### 4) Taux de réponse
- **Definition:** RESPONDED / APPLIED.
- **Source:** localStorage (RESPONDED, APPLIED).
- **Fallback:** “—” si APPLIED = 0.

### 5) Tendance du match moyen (line chart)
- **Definition:** moyenne des scores des offres NEW (non décidées / non appliquées) au moment du fetch Inbox.
- **Source:** localStorage `snapshots` (7 entrées max).
- **Construction:**
  - à chaque fetch inbox, stocke `{date, avgScoreNew, countNew}`.
  - chart lit les 7 dernières entrées.

### 6) Offres ≥ seuil (donut)
- **Definition:** % des 20 premières offres NEW avec score >= seuil.
- **Seuil:** UI (65 par défaut) stocké en localStorage.
- **Fallback:** “—” si 0 offre.

### 7) Compétences manquantes (proxy)
- **Definition:** top 3 mots-clés extraits des `reasons` des offres NEW.
- **Source:** reasons string → tokenisation simple + stopwords.

### 8) Relances / À faire
- **Definition:** offres APPLIED depuis ≥ 7 jours sans RESPONDED.
- **Source:** localStorage (APPLIED/RESPONDED + applied_at).
- **Action:** bouton “Marquer répondu”.

## Notes techniques
- LocalStorage keys: `elevia_inbox_<profileId>_applications`, `_decisions`, `_snapshots`.
- Aucun changement backend.
- Aucun changement de structure HTML: template conservé, labels/valeurs remplacés.
