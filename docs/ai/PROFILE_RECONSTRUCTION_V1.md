# PROFILE RECONSTRUCTION V1 — Elevia

> Étape cadrée uniquement. Ne pas implémenter sans décision de surface et validation produit explicite.

## Objectif

Lire un CV texte + profil partiel et produire une reconstruction structurée, propre et exploitable du profil.

Profile Reconstruction V1 doit :
- nettoyer ;
- structurer ;
- regrouper ;
- reformuler légèrement ;
- produire des suggestions.

Profile Reconstruction V1 ne doit pas :
- modifier les données existantes ;
- enrichir avec des sources externes ;
- inventer des informations ;
- créer des URIs ;
- modifier le scoring.

## Input

```json
{
  "cv_text": "...",
  "career_profile": {},
  "experiences": [],
  "selected_skills": [],
  "structured_signal_units": [],
  "validated_items": [],
  "canonical_skills": []
}
```

Tous les champs peuvent être partiels ou absents.

## Output strict

La sortie doit être un JSON strict, sans texte hors JSON :

```json
{
  "suggested_summary": {
    "text": "...",
    "confidence": 0.0,
    "evidence": ["..."]
  },
  "suggested_experiences": [
    {
      "title": "...",
      "organization": "...",
      "start_date": "...",
      "end_date": "...",
      "missions": ["..."],
      "tools": ["..."],
      "skills": ["..."],
      "signals": {
        "autonomy": "...",
        "impact": ["..."]
      },
      "confidence": 0.0,
      "evidence": ["..."]
    }
  ],
  "suggested_skills": [
    {
      "label": "...",
      "type": "hard|tool|domain",
      "confidence": 0.0,
      "evidence": ["..."]
    }
  ],
  "suggested_projects": [
    {
      "name": "...",
      "description": "...",
      "tools": ["..."],
      "confidence": 0.0,
      "evidence": ["..."]
    }
  ],
  "suggested_certifications": [
    {
      "name": "...",
      "issuer": "...",
      "confidence": 0.0,
      "evidence": ["..."]
    }
  ],
  "suggested_languages": [
    {
      "language": "...",
      "level": "...",
      "confidence": 0.0,
      "evidence": ["..."]
    }
  ]
}
```

## Règles

### Zéro invention
- Si ce n'est pas dans le CV ou le profil fourni, ne pas l'ajouter.
- Si c'est ambigu, baisser la confidence.
- En cas de doute, ne pas ajouter.

### Evidence obligatoire
Chaque élément doit contenir :
- un extrait du CV ;
- ou une référence claire au contenu fourni.

### Confidence
- `0.9` : explicite dans le CV.
- `0.7` : fortement suggéré.
- `0.5` : inféré raisonnablement.
- `<0.5` : éviter sauf si utile et clairement marqué.

### Expériences
Faire :
- regrouper les missions propres ;
- supprimer les répétitions ;
- structurer clairement.

Ne pas faire :
- réécrire complètement le CV ;
- ajouter des missions fictives.

### Skills
Faire :
- dédupliquer ;
- regrouper les variantes simples (`powerbi` → `power bi`) si elles sont présentes ;
- distinguer `tool`, `hard`, `domain`.

Ne pas faire :
- ajouter une compétence absente du texte ;
- créer une URI ;
- utiliser ESCO/O*NET externe.

### Résumé
Le résumé doit être :
- clair ;
- orienté métier ;
- basé uniquement sur les expériences et signaux fournis.

### Langues / certifications / projets
- Extraire uniquement si présents.
- Sinon laisser les tableaux vides.

## Interdits

- Appeler une API.
- Utiliser O*NET / ESCO externe.
- Créer des IDs / URIs.
- Modifier les champs d'entrée.
- Produire autre chose que du JSON.
- Modifier scoring, ranking, filtrage ou canonicalisation backend.

## Intention

Profile Reconstruction V1 n'est pas un moteur de matching.
Profile Reconstruction V1 n'est pas un enrichisseur externe.

Rôle : lecteur intelligent de CV qui transforme un document bruité en suggestions de profil structuré.
