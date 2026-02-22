# Architecture Stable — Elevia Compass

> Snapshot stabilisé — ne pas modifier le scoring core sans revue.

## Ports et services

| Service | Port | Commande |
|---------|------|---------|
| FastAPI (API) | 8000 | `make api` |
| Vite (Frontend) | 3001 | `make web` |

## Variables d'environnement clés

| Var | Valeur | Effet |
|-----|--------|-------|
| `ELEVIA_DEV_TOOLS` | `1` | Active `POST /dev/cv-delta` (sinon 403) |
| `OPENAI_API_KEY` | `sk-…` | Active LLM enrichment (mode A+B). Absent → mode A + warning |
| `ELEVIA_TRACE_PROFILE_PIPELINE` | `1` | Active `POST /debug/profile-pipeline` |
| `ENV` ou `DEBUG` | `dev` / `1` | Active `POST /debug/match` |

## Proxy Vite (dev uniquement)

`apps/web/vite.config.ts` — toutes les routes API sont proxifiées vers `http://localhost:8000` :
```
/dev, /v1, /debug, /profile, /offers, /inbox, /metrics, /apply-pack, /applications, /health
```
Pas de `VITE_API_BASE_URL` requis en dev local. En LAN/téléphone, le proxy suffit si `--host 0.0.0.0`.

## Routes FastAPI (résumé)

```
GET  /                     → root info
GET  /health               → {"status": "ok"}
POST /v1/match             → matching engine
POST /profile/ingest_cv    → CV parsing → profil structuré
POST /inbox                → matching profil vs catalog
POST /offers/sample        → offres VIE
POST /debug/match          → trace matching (ENV=dev)
POST /debug/profile-pipeline → trace pipeline (ELEVIA_TRACE_PROFILE_PIPELINE=1)
POST /dev/cv-delta         → delta A vs A+B (ELEVIA_DEV_TOOLS=1) ← DEV TOOL
GET  /dev/cv-delta         → 405 (POST uniquement)
```

## Structure fichiers critiques

```
apps/api/
  src/api/
    main.py                     ← montage des routers + OBS startup log
    routes/
      dev_tools.py              ← POST /dev/cv-delta (gated)
      debug_match.py            ← /debug/* (gated ENV=dev)
      matching.py               ← /v1/match (NE PAS TOUCHER)
  scripts/
    cv_parsing_delta_report.py  ← build_report() appelé par dev_tools.py
  tests/
    test_dev_cv_delta_endpoint.py  ← contrat endpoint
    test_cv_parsing_delta_report.py ← contrat script

apps/web/
  vite.config.ts               ← proxy /dev → :8000
  src/
    App.tsx                    ← route /dev/cv-delta → DevCvDeltaPage
    pages/DevCvDeltaPage.tsx   ← UI upload + résultats
    lib/api/cvDelta.ts         ← runCvDelta(file, withLlm)

docs/
  START_HERE.md               ← point d'entrée unique
  ARCHITECTURE_STABLE.md      ← ce fichier
  pipelines/CV_PARSING_LLM_DELTA_STEP4.md ← runbook détaillé
  infra/PYTEST_IMPORT_HANG_FIX.md
```

## Conventions

- **Scoring core frozen** : `matching_v1.py`, `weights_*`, `idf.py`, formule, normalisation, canonicalisation pipeline A→F — aucune modification sans revue explicite.
- **Gating dev** : tout endpoint DEV-only retourne 403 sans l'env var appropriée. Jamais de clé API dans le repo.
- **Proxy Vite** : en dev, le FE appelle des chemins relatifs (`/dev/cv-delta`), le proxy redirige. Pas d'IP hardcodée dans le code.
- **pytest** : toujours lancer depuis `apps/api/` ou via `make test-cvdelta`. Ne pas lancer depuis `~/Documents/`.
