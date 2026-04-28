# Scoring Decomposition v1

> Audit report — décomposition produit du scoring V1 actuel et proposition d'une architecture parallèle `fit_score_v2`. **Aucun changement runtime.**

---

## 1. Executive summary

Le scoring V1 actuel est une **formule unique 4 piliers** centralisée dans [matching_v1.py](apps/api/src/matching/matching_v1.py) :

```
score = round(100 * (0.70 * skills + 0.15 * lang + 0.10 * edu + 0.05 * country))
```

Cette formule mélange dans un seul nombre trois rôles produit distincts :

1. **Fit métier** (skills_uri intersection — 70 % du poids) : seul signal réellement variable.
2. **Préférences** (langues, éducation, pays préférés — 30 %) : retournent **par défaut 1.0** quand la profile n'a pas l'info → 30 points "offerts" gratuitement à toutes les offres.
3. **Éligibilité** (hard filter `is_vie / country_present / title_present / company_present`) : binaire, sort de la même méthode `score_offer` que la note de fit.

Conséquences mesurées dans [audit_report.md](../../tmp/audit_report.md) :
- CV1 (généraliste, 62 skills_uri) plafonne à **70** sur 66 offres DATA — aucune ≥ 80.
- CV2 (data analyst clean, 23 skills_uri) plafonne à **66**.
- 3 récents layers produit (`domain_affinity`, `career_intelligence`, `offer_domain_enrichment`) sont **payload-only** : enrichissent l'UI mais ne pèsent rien dans la note.
- Des features mortes existent : `IDF` calculée mais jamais consommée par la formule, `context_coeffs` jamais appelé, `weighted_store.contextual_weight=1.0` neutralise la classification CORE/SECONDARY (R29).

**Recommandation produit** : ne pas toucher V1 (gel R1, R2, R3, R29). Construire en parallèle un pipeline `fit_score_v2` qui sépare explicitement `eligibility_status / fit_score_v2 / preference_score / explainability` et qui consomme les signaux déjà disponibles mais inertes (domain_affinity, target_title, CORE vs SECONDARY, career_intelligence). Validation sur un panel de 6 archétypes CV avant tout routage runtime.

---

## 2. Current score factors

| factor | current_role | current_weight_or_effect | real_product_role | decision |
|---|---|---|---|---|
| `skills_score` (intersection skills_uri matched_weight / total_weight) | composante 70 % de la note finale | 0.70 | **FIT_METIER** | garder, mais raffiner CORE vs SECONDARY (cf. v2) |
| `languages_score` (max ratio sur required_languages) | composante 15 % | 0.15, **default 1.0** si profile sans langues OU offre sans required_languages | **ELIGIBILITY** (langue requise) + **PREFERENCE** (bonus) | sortir de la note de fit ; binariser en eligibility (langue requise présente oui/non) + préférence séparée |
| `education_score` (degree.value ≥ requirement) | composante 10 % | 0.10, **default 1.0** si profile/offre sans niveau | **PREFERENCE** | sortir de la note de fit ; afficher comme préférence/explainability |
| `country_score` (intersection profile.preferred_countries ∩ offer.country) | composante 5 % | 0.05, **default 1.0** si profile sans préférences | **PREFERENCE** | sortir de la note de fit ; ne pas confondre "offre éligible V.I.E" avec "pays préféré candidat" |
| `is_vie == True` hard filter | rejet → score=0 si non | binaire | **ELIGIBILITY** | garder en eligibility, mais **hors de `score_offer`** |
| `country` present hard filter | rejet → score=0 si manquant | binaire | **ELIGIBILITY** (data quality) | garder en eligibility |
| `title` / `company` present hard filter | rejet → score=0 si manquant | binaire | **ELIGIBILITY** (data quality) | garder en eligibility |
| `partial_score` clamp (PARTIAL_MAX_SCORE=30) | plafond si match score < 0.30 | clamp ≤ 30 | **DEBUG_ONLY** | conserver pour V1 ; non porté en v2 (la classification éligibilité/fit/préférence remplace ce signal) |
| `weighted_store.contextual_weight` (CORE/SECONDARY/CONTEXT) | classification calculée mais multipliée par 1.0 (R29) | **0** effet sur le score | **DEBUG_ONLY aujourd'hui** ; **FIT_METIER** en v2 | activer en v2 avec `w_core > w_secondary` |
| `IDF` table (`compute_idf` au boot) | calculée à l'init engine | **0** effet sur le score | **NOISE** (dead code dans le scoring) | ne pas porter en v2 — si rareté souhaitée, recalculer sur la sous-population offer-fit |
| `context_coeffs` field | jamais appelé | **0** effet | **NOISE** (dead code) | supprimer de la signature v2 |
| `generic_skills_filter` offer-side (HARD_GENERIC_URIS) | retire les URIs trop génériques de l'offre avant intersection | filtrage offre amont | **FIT_METIER pre-processing** | conserver en v2, recalibrer (cf. limite L1) |
| `match_debug.skills.matched_core / matched_secondary / missing_core` | renvoyé en payload | aucun effet sur la note | **DEBUG_ONLY aujourd'hui** ; **FIT_METIER** en v2 | exposer en explainability ET pondérer en v2 |
| `domain_affinity` (aligned/adjacent/distant/neutral) | enrichissement payload `/api/inbox` | **0** effet (R26 frozen) | **FIT_METIER booster** + **EXPLAINABILITY** | brancher comme multiplicateur soft en v2 |
| `career_intelligence` (strengths/gaps) | rendu UI OfferDetailModal | **0** effet (R9, R12) | **EXPLAINABILITY** | rester explainability, pas de scoring direct |
| `target_title` / `offer.title` similarité | non calculée dans la note | **0** effet | **FIT_METIER booster** | brancher en v2 (title-boost) |
| `offer_domain_enrichment.domain_tag` | lu seulement par audit & affinity | **0** effet sur `/v1/match` | **FIT_METIER input** (pour booster) | consommer en v2 via affinity multiplier |

---

## 3. Misplaced factors

Facteurs aujourd'hui dans la note de fit qui devraient en sortir :

1. **`country_score` (5 %)**
   - Mélange "le candidat aime ce pays" et "l'offre est compatible V.I.E ce pays".
   - 5 % gratuits dès que la profile n'a pas de `preferred_countries` (cas majoritaire).
   - **À déplacer** : `preference_score`.

2. **`languages_score` (15 %)**
   - Si l'offre **exige** une langue, c'est une éligibilité binaire (FR natif candidat applique sur poste 100 % anglais → la note ne doit pas être "presque bonne", elle doit être "non éligible" + explainability).
   - Si l'offre n'exige pas de langue → 15 % gratuits.
   - **À scinder** : `eligibility.required_languages_ok` + `preference.language_match`.

3. **`education_score` (10 %)**
   - Aujourd'hui défaut 1.0 quand soit la profile soit l'offre n'a pas de niveau précis. Ce 10 % est quasi toujours offert.
   - Pas un signal de fit métier — un candidat Bac+5 vs Bac+3 ne change pas son adéquation skills.
   - **À déplacer** : `preference_score` (avec affichage explicite "niveau requis vs niveau profile").

4. **Hard filter `is_vie / country / title / company` mélangé à la note**
   - Aujourd'hui : `score=0` retourné par `score_offer` quand l'offre n'est pas V.I.E ou champs absents.
   - "Score 0" ≠ "non éligible" : un produit doit pouvoir afficher "offre filtrée pour cause d'éligibilité" avec son raison code (V.I.E only, missing country) **distinctement** d'une offre faiblement matchée.
   - **À séparer** : `eligibility_status: { ok: bool, reasons: [...] }` calculé **avant** le scoring.

5. **Secondary skills mises au même poids que CORE skills**
   - `weighted_store` produit un classement CORE/SECONDARY/CONTEXT, mais `contextual_weight=1.0` partout (R29 frozen).
   - Conséquence : un match sur "Excel" pèse autant qu'un match sur "Power BI" pour une offre Data Analyst.
   - **À porter en v2** : `w_core ≥ 1.0`, `w_secondary < 1.0`, ratio à calibrer.

6. **`partial_score` clamp** (PARTIAL_MAX_SCORE=30) traite tous les profils à très petit `match_score` de la même façon — il sert de filet, mais il efface le signal "ce candidat a 1 skill très core" vs "ce candidat a 5 skills CONTEXT". À ne pas porter tel quel en v2.

---

## 4. Underused signals

Signaux **calculés mais inutilisés** par la note de fit V1 :

1. **`domain_affinity` (aligned/adjacent/distant/neutral)**
   - Calculé runtime dans `/api/inbox` ([apps/api/src/api/utils/domain_affinity.py](apps/api/src/api/utils/domain_affinity.py)).
   - Score 0/1/2 (`affinity_score`) déjà disponible.
   - Frozen rule R26 : pas d'impact ranking. **Conséquence audit** : offres distant peuvent dominer le top 10 si leurs skills sont très intersectées avec une CV généraliste.

2. **`domain_affinity_score` (numeric 0/1/2)**
   - Émis sur chaque InboxItem mais ignoré pour le tri.

3. **`offer_domain_enrichment.domain_tag` (DB)**
   - Joint à l'inférence d'affinity uniquement. Pas vu par `score_offer`.

4. **`target_title` profile vs `offer.title` (similarité titre)**
   - Pas calculé du tout dans le scoring V1.
   - L'audit a montré : sur CV2 (data analyst), les top scores incluent des offres "Mechanical Engineer", "Operations Coordinator" alors qu'aucun signal titre n'est utilisé.

5. **`matched_core` vs `matched_secondary` (différentiel)**
   - Présent dans `match_debug.skills` mais non pondéré (cf. R29).
   - Un candidat qui matche 8 SECONDARY a la même note qu'un candidat qui matche 4 CORE + 4 SECONDARY.

6. **`career_intelligence.strengths / gaps / generic_ignored / positioning`**
   - Affichés dans OfferDetailModal (R12), aucun retour vers le scoring.
   - Utilisable comme **explainability** structuré (pas comme scoring direct — risque de double-comptage des skills).

7. **Bruit dans `offer_skills`**
   - Le générique offer-side filter retire les `HARD_GENERIC_URIS`, mais des skills très larges (`management`, `team_work`) demeurent et boostent artificiellement le numérateur d'intersection sur les CV généralistes — limite L1 documentée.

8. **`preferred_countries` de la profile**
   - Aujourd'hui un signal de fit (5 %), devrait être un filtre de préférence configurable côté UI ("voir uniquement mes pays") et non un signal de score.

---

## 5. Proposed `fit_score_v2` architecture (parallel, no V1 mutation)

V2 vit **à côté** de V1, derrière un flag (suivant R3). V1 reste source of truth tant que V2 n'est pas validé sur le panel CV.

### 5.1 Quatre couches explicites

```
┌──────────────────────────────────────────────────────────────┐
│ INPUT: profile (extracted) + offer                           │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. eligibility_status                                        │
│    bool ok + reasons[]                                       │
│    - is_vie == True                                          │
│    - country present                                         │
│    - title present                                           │
│    - company present                                         │
│    - required_languages satisfied (si offre exige)           │
│    short-circuit: si not ok → renvoyer { ok: false, ... }    │
│                  pas de scoring, juste explainability        │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. fit_score_v2 (0..100)                                     │
│    = base_skill_fit                                          │
│      × domain_multiplier                                     │
│      × title_multiplier                                      │
│                                                              │
│    base_skill_fit = sum(w_core * matched_core_weight,       │
│                          w_sec  * matched_secondary_weight)  │
│                     / sum(w_core * total_core_weight,        │
│                            w_sec  * total_secondary_weight)  │
│                                                              │
│    domain_multiplier:                                        │
│      aligned   → 1.10                                        │
│      adjacent  → 1.00                                        │
│      distant   → 0.85                                        │
│      neutral   → 1.00                                        │
│                                                              │
│    title_multiplier:                                         │
│      target_title ≈ offer.title → 1.05                       │
│      else                       → 1.00                       │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. preference_score (0..100, soft, displayed separately)     │
│    - language_match (nice-to-have, not required)             │
│    - education_match (degree.value vs requirement)           │
│    - country_preference (profile.preferred_countries)        │
│    - contract_type (V.I.E vs internship vs CDI)              │
└──────────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. explainability                                            │
│    - matched_core / matched_secondary / missing_core         │
│    - domain_affinity (aligned/adjacent/distant)              │
│    - career_intelligence.strengths / gaps                    │
│    - eligibility.reasons                                     │
│    - preference breakdown                                    │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Outputs

```jsonc
{
  "eligibility_status": { "ok": true, "reasons": [] },
  "fit_score_v2": 78,
  "preference_score": 65,
  "score_v1_legacy": 70,        // gardé pour comparaison shadow
  "explainability": { ... }
}
```

### 5.3 Contrats (R1, R2, R3, R29 respectés)

- **Pas une seule ligne** de [matching_v1.py](apps/api/src/matching/matching_v1.py), [idf.py](apps/api/src/matching/idf.py), `weights_*` modifiée.
- V2 vit dans un nouveau module `apps/api/src/matching/fit_score_v2/` sans toucher l'engine V1.
- `extract_profile` réutilisé tel quel (frozen R2).
- Routes `/v1/match`, `/api/inbox`, `/dev/metrics`, `/debug/match` continuent de servir V1. V2 exposé en shadow uniquement (header `X-Scoring-V2: shadow`).

### 5.4 Calibration des coefficients

À déterminer empiriquement sur le panel CV (section 6) :
- `w_core / w_secondary` ratio : essayer `(1.0, 0.5)`, `(1.0, 0.33)`, `(1.0, 0.25)`.
- `domain_multiplier` valeurs : essayer aligned `[1.05, 1.10, 1.15]`, distant `[0.85, 0.80, 0.75]`.
- `title_multiplier` : flat 1.05 pour commencer.

Critères d'acceptation (cf. section 6).

---

## 6. Validation protocol — 6-CV panel

Pas de runtime, pas d'utilisateur final exposé tant que les seuils ne sont pas atteints.

### 6.1 Panel

| CV | profil | source |
|---|---|---|
| C1 | data analyst spécialisé (CV2 audit_report) | déjà disponible |
| C2 | RH / talent acquisition | à fournir ou échantillon BF |
| C3 | sales B2B / business development | à fournir ou échantillon BF |
| C4 | finance / contrôle de gestion | à fournir ou échantillon BF |
| C5 | marketing / growth | à fournir ou échantillon BF |
| C6 | généraliste (CV1 audit_report — WECKER) | déjà disponible |

### 6.2 Mesures par CV (V1 vs V2 sur les mêmes ~900 offres catalog)

1. **Distribution de scores** : nb d'offres par bucket `[0–40, 40–55, 55–70, 70–80, 80–90, 90–100]`.
2. **Top-10 overlap V1 ∩ V2** (Jaccard).
3. **Domain-aligned ratio in top-10** : `count(domain_affinity == aligned) / 10`.
4. **Precision@10** (manuel) : pour chaque top-10, label binaire "fit acceptable pour ce candidat" → ratio.
5. **Above-threshold count** (`fit_score_v2 ≥ 70`) — vise à ne plus avoir le plafond observé V1.
6. **Breadth-over-precision flag** : pour CV1 généraliste, fraction des top-10 qui sont des offres avec ≥ 8 skills d'intersection mais 0 CORE matched.

### 6.3 Critères d'acceptation v2

- C1 (data analyst) : domain-aligned ratio in top-10 ≥ 0.7 (V1 actuel : ~0.4 selon audit).
- C2..C5 : domain-aligned ratio ≥ 0.6.
- C6 (généraliste) : breadth flag ≤ 0.3 (V1 actuel : élevé selon audit).
- Precision@10 V2 ≥ Precision@10 V1 sur 5 / 6 CV.
- **Pas de régression** : pour chaque CV, `eligibility_status` doit retourner `ok=true` exactement pour les offres qui passent le hard filter V1.

---

## 7. Risks / non-goals

### 7.1 Risques

- **Calibration peu robuste sur petit panel** : 6 CV n'est pas un benchmark complet ; v2 doit rester en shadow tant qu'on n'a pas de validation manuelle plus large (≥ 30 CV idéalement).
- **Double-comptage** si `career_intelligence` est utilisé à la fois comme signal de score ET comme explainability. Garder strict : explainability uniquement.
- **Regression sur CV2 (data analyst clean)** si `w_secondary` est trop bas — l'audit montre que CV2 n'a quasi pas de SECONDARY mais tape juste sur CORE. Vérifier que `fit_score_v2` ne plafonne pas plus bas que V1 sur ce profil.
- **Drift d'éligibilité** : sortir le hard filter de `score_offer` change la sémantique des routes `/v1/match` (auj. `score=0` = filtré). Côté V2 : nouveau payload, pas de breakage.

### 7.2 Non-goals

- **Pas** de modification de [matching_v1.py](apps/api/src/matching/matching_v1.py), [idf.py](apps/api/src/matching/idf.py), `weights_*` (R1, frozen).
- **Pas** de modification de `extract_profile` ni de la sémantique `skills_uri` (R2, frozen).
- **Pas** de nouveau provider IA dans la boucle de scoring.
- **Pas** de modification de schéma DB.
- **Pas** de couplage frontend en sprint v2 — la route shadow expose le payload, le rendu UI vient en sprint suivant si v2 est validé.
- **Pas** de re-ranking ML, **pas** de graph embeddings (non-goals DECISIONS.md).
- **Pas** de filtrage profile-side, **pas** de WEAK skills dans le scoring (non-goals DECISIONS.md).

---

## 8. Next recommended sprint

**Sprint name** : `fit_score_v2_shadow_v1`

**Scope** :
1. Créer `apps/api/src/matching/fit_score_v2/` (nouveau module isolé).
2. Implémenter les 4 couches (eligibility / fit / preference / explainability) sans toucher V1.
3. Brancher en shadow sur `/v1/match` et `/api/inbox` :
   - V1 reste l'autorité (réponse identique).
   - Ajouter en payload optionnel : `fit_score_v2`, `eligibility_status`, `preference_score` quand le flag `ELEVIA_FIT_SCORE_V2_SHADOW=1` est actif (R3).
4. Outil de comparaison hors-ligne : `scripts/compare_v1_v2_panel.py` qui prend les 6 profils du panel + le catalog 903 offres et émet le rapport (distribution, top-10 overlap, domain-aligned ratio, precision@10 placeholder).
5. **Pas** de routage runtime ni de bascule UI tant que les critères d'acceptation (§6.3) ne sont pas validés.

**Deliverables** :
- Module `fit_score_v2/` + tests unitaires.
- Script `compare_v1_v2_panel.py`.
- Rapport `docs/ai/reports/fit_score_v2_calibration_v1.md` avec mesures par CV.
- Décision Go / No-Go documentée dans DECISIONS.md (nouvelle entrée datée).

**Non-scope sprint suivant** :
- Pas de remplacement V1 → V2.
- Pas de changement frontend.
- Pas de DB migration.

---

## Files read

- `docs/ai/STATE.json` (lectures partielles)
- `docs/ai/HANDOFF.md`
- `docs/ai/DECISIONS.md`
- `docs/ai/WORKLOG.md` (entrées récentes)
- `/tmp/audit_report.md`
- (contexte mémorisé) `/tmp/scoring_core_audit_v1.md`

## Files created

- `docs/ai/reports/scoring_decomposition_v1.md` (ce rapport)

## Files modified

- (aucun)

---

**AUDIT ONLY — NO RUNTIME CHANGE**
