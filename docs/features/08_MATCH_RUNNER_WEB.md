# Sprint 8 - Match Runner Web

## Démarrage

### 1. Lancer l'API (terminal 1)

```bash
cd apps/api
PYTHONPATH=./src ../../.venv/bin/uvicorn src.api.main:app --reload --port 8000
```

### 2. Lancer le front (terminal 2)

```bash
cd apps/web
npm run dev
```

## URLs

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Accueil |
| http://localhost:3000/match | Match Runner |
| http://localhost:8000/docs | Swagger API |

## Fonctionnement

1. Ouvrir http://localhost:3000/match
2. Cliquer "Lancer le match"
3. Le front charge les fixtures locales (`/fixtures/profile_demo.json`, `/fixtures/offers_demo.json`)
4. POST vers `/v1/match` (proxy Vite → API :8000)
5. Affiche les résultats

## Format de réponse

```json
{
  "profile_id": "candidate_demo",
  "threshold": 80,
  "results": [
    {
      "offer_id": "offer_vie_001",
      "score": 92,
      "breakdown": { "skills": 1.0, "languages": 1.0, "education": 1.0, "country": 1.0 },
      "reasons": [
        "Compétences clés alignées : python, sql, excel",
        "Langue requise compatible",
        "Niveau d'études cohérent"
      ]
    }
  ],
  "message": null
}
```

## Fichiers créés

```
apps/web/
├── src/
│   ├── App.tsx           (router)
│   ├── index.css         (styles minimaux)
│   └── pages/
│       ├── HomePage.tsx
│       └── MatchPage.tsx
├── public/fixtures/
│   ├── profile_demo.json
│   └── offers_demo.json
└── vite.config.ts        (proxy /v1 → :8000)
```

## Conformité UX Audit

- Une seule question par page : "Quelles offres matchent ?"
- Fond blanc, pas de gradient
- Zéro animation décorative
- Max 3 reasons affichées (contrat API)
- Page courte, utile
