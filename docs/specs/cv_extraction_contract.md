# Contrat d'Extraction CV — Sprint 12

## Objectif

Transformer un CV brut en un profil **observable, corrigeable et débuggable**, sans casser le moteur existant (Sprint 9-11).

## Endpoint

```
POST /profile/ingest_cv
```

### Request

```json
{
  "cv_text": "...",
  "source": "paste|upload"
}
```

| Champ | Type | Requis | Validation |
|-------|------|--------|------------|
| `cv_text` | string | Oui | 10-50000 caractères |
| `source` | string | Non | Défaut: "paste" |

### Response (200 OK)

```json
{
  "candidate_info": {
    "first_name": "Jean",
    "last_name": "Dupont",
    "email": "jean.dupont@example.com",
    "years_of_experience": 5
  },
  "detected_capabilities": [
    {
      "name": "programming_scripting",
      "level": "expert",
      "score": 85,
      "proofs": ["5 ans d'expérience Python"],
      "tools_detected": ["Python", "SQL"]
    }
  ],
  "languages": [
    { "code": "fr", "level": "C2", "raw_text": "Français natif" }
  ],
  "education_summary": {
    "level": "BAC+5",
    "raw_text": "Master Data Science"
  },
  "unmapped_skills_high_confidence": [
    {
      "raw_skill": "SEO",
      "confidence": 0.92,
      "proof": "Expert SEO/SEM avec 5 ans d'expérience"
    }
  ]
}
```

## Référentiel Capacités V0.1 (SOURCE DE VÉRITÉ)

**5 capacités UNIQUEMENT** — Toute autre valeur est rejetée par Pydantic.

| Nom | Outils mappés |
|-----|---------------|
| `data_visualization` | PowerBI, Tableau, Looker, Qlik, Dataviz |
| `spreadsheet_logic` | Excel, VBA, Google Sheets, TCD, formules |
| `crm_management` | Salesforce, HubSpot, Zoho, Pipedrive |
| `programming_scripting` | Python, R, JavaScript, SQL, automatisation |
| `project_management` | Jira, Asana, Trello, Notion, Agile, Scrum |

## Règle Clé

```
detected_capabilities = SEULEMENT les 5 capacités V0.1
unmapped_skills_high_confidence = compétences hors référentiel (observabilité)
```

**Les unmapped NE SERVENT PAS AU MATCHING.** Elles servent à observer ce qu'on perd pour améliorer itérativement le référentiel.

## Schémas Pydantic

### CapabilityEnum

```python
class CapabilityEnum(str, Enum):
    DATA_VISUALIZATION = "data_visualization"
    SPREADSHEET_LOGIC = "spreadsheet_logic"
    CRM_MANAGEMENT = "crm_management"
    PROGRAMMING_SCRIPTING = "programming_scripting"
    PROJECT_MANAGEMENT = "project_management"
```

### DetectedCapability

| Champ | Type | Validation |
|-------|------|------------|
| `name` | CapabilityEnum | Obligatoire, doit être une des 5 valeurs |
| `level` | beginner\|intermediate\|expert | Obligatoire |
| `score` | int | 0-100 |
| `proofs` | List[str] | Min 1 élément |
| `tools_detected` | List[str] | Optionnel |

### UnmappedSkill

| Champ | Type | Validation |
|-------|------|------------|
| `raw_skill` | str | Min 1 caractère |
| `confidence` | float | 0.0-1.0 |
| `proof` | str | Min 1 caractère |

## Stratégie LLM

### Principe

```
L'IA extrait → Le backend valide → Le moteur utilise → L'utilisateur corrige
```

**L'IA ne décide jamais.** Pydantic est la barrière anti-hallucination.

### Gestion des erreurs

1. Appel LLM normal
2. Si JSON invalide → retry avec prompt de correction
3. Si encore invalide → raise `ExtractionError` + log + retour 422

### Scores d'extraction

| Score | Signification |
|-------|---------------|
| < 40 | Mention simple / débutant |
| 40-70 | Utilisation professionnelle / intermédiaire |
| > 70 | Expert / certification / projets complexes |

### Confidence (unmapped)

Seules les compétences avec `confidence >= 0.7` sont incluses dans `unmapped_skills_high_confidence`.

## Codes d'erreur

| Code | Signification |
|------|---------------|
| 200 | Extraction réussie |
| 422 | Validation échouée (CV vide, JSON invalide, capability hors référentiel) |
| 503 | Provider LLM non disponible |

## Interdictions

- Pas de matching dans cet endpoint
- Pas de scoring produit
- Pas de règles métier
- Pas de "nettoyage intelligent"
- Pas de suppression silencieuse

**Tout ce qui est ambigu doit être visible, pas corrigé.**

## Philosophie

> Un moteur juste peut produire un résultat injuste si l'entrée est mauvaise.
> Ce sprint rend l'entrée observable.

## Fichiers

| Fichier | Rôle |
|---------|------|
| `apps/api/src/profile/schemas.py` | Schémas Pydantic (barrière) |
| `apps/api/src/profile/llm_client.py` | Abstraction LLM + retry |
| `apps/api/src/api/routes/profile.py` | Endpoint FastAPI |
| `apps/api/src/profile/capabilities_v01.json` | Référentiel capacités |
| `apps/api/tests/test_profile_ingest_cv_contract.py` | Tests du contrat |
