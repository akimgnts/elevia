# User Profile V0 — Documentation Technique

## Schéma UserProfile (pour le matching)

Le moteur `extract_profile()` attend un dict avec ces champs :

```typescript
interface UserProfile {
  id: string;                    // Identifiant unique
  skills: string[];              // Liste de compétences normalisées
  languages: string[];           // Liste de langues
  education: string;             // Niveau d'études (bac+5, master, etc.)
  preferred_countries: string[]; // Liste de pays (vide = tous acceptés)
}
```

## Mapping Profil → Matching

| Champ | Poids | Signal | Calcul |
|-------|-------|--------|--------|
| `skills` | 70% | Principal | `|skills_profil ∩ skills_offre| / |skills_offre|` |
| `languages` | 15% | Secondaire | `|langues_profil ∩ langues_offre| / |langues_offre|` |
| `education` | 10% | Secondaire | `1.0` si niveau ≥ requis, `0.0` sinon |
| `preferred_countries` | 5% | Bonus | `1.0` si pays dans liste, `0.5` sinon |

## Profil Akim Guentas V0

### Fichiers

| Fichier | Usage |
|---------|-------|
| `apps/api/fixtures/profiles/akim_guentas.json` | Profil complet avec métadonnées |
| `apps/api/fixtures/profiles/akim_guentas_matching.json` | Profil simplifié pour le matching |
| `apps/web/src/fixtures/seedProfile.ts` | Export TypeScript pour le frontend |

### Skills (23 entrées)

**Signal fort** (cœur de métier) :
- `analyse de données`, `data analysis`, `data analyst`, `analyst`
- `normalisation`, `indicateurs`, `kpi`
- `reporting`, `aide à la décision`, `business intelligence`, `bi`

**Outils** :
- `power bi`, `powerbi`, `tableau`, `excel`, `tableur`

**Tech** :
- `python`, `sql`, `api`, `json`, `csv`

**Automatisation** :
- `automatisation`, `make`

### Langues

- `français`, `anglais`

### Éducation

- `bac+5` → niveau ordinal 4 (Master)

### Pays préférés

- Vide → accepte tous les pays (score pays = 1.0)

## Comportement Attendu du Matching

### Offres à haut score (≥80%)

- Data Analyst / Business Analyst
- Reporting / BI
- Analyste décisionnel
- Chargé d'études data

**Pourquoi** : Intersection skills élevée (≥75%)

### Offres à score moyen (50-79%)

- Data Analyst avec stack technique spécifique (Spark, AWS)
- Business Analyst avec CRM/Salesforce
- Analyst dans domaine sectoriel spécifique

**Pourquoi** : Intersection skills partielle

### Offres à score bas (<50%)

- Software Engineer / Développeur
- Data Scientist ML/DL
- Marketing opérationnel
- Chef de projet généraliste

**Pourquoi** : Skills absentes → skills_score ≈ 0-20% → score total plafonné à ~30%

## Plafonds Explicables

| Scénario | Score max | Explication |
|----------|-----------|-------------|
| Aucune skill match | 30% | langues(15%) + études(10%) + pays(5%) |
| 1 skill sur 5 match | 44% | 14% skills + 30% reste |
| 3 skills sur 4 match | 82% | 52% skills + 30% reste |
| Toutes skills match | 100% | 70% skills + 30% reste |

## Utilisation

### Backend (Python)

```python
from matching import MatchingEngine, extract_profile

profile = {
    "id": "akim_guentas_v0",
    "skills": ["data analysis", "power bi", "sql", ...],
    "languages": ["français", "anglais"],
    "education": "bac+5",
    "preferred_countries": []
}

extracted = extract_profile(profile)
engine = MatchingEngine(offers=catalog)
result = engine.score_offer(extracted, offer)
```

### Frontend (TypeScript)

```typescript
import { SEED_PROFILE } from '../fixtures/seedProfile';
import { useProfileStore } from '../store/profileStore';

// Charger le profil seed
useProfileStore.getState().setUserProfile(SEED_PROFILE);
```

### Via l'interface

1. Ouvrir http://localhost:5173/analyze
2. Coller le CV texte
3. Le profil est extrait et stocké dans le store
4. Naviguer vers /inbox pour voir les offres matchées

## Évolutions Futures (V1, V2)

- **V1** : Ajouter `experience_years` au scoring
- **V1** : Mapper skills vers ESCO URIs pour matching sémantique
- **V2** : Pondération dynamique des skills (IDF)
- **V2** : Prise en compte des exclusions explicites
