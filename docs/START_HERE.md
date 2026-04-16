# START HERE — Elevia Compass

> **Repo canonique unique :** `~/Dev/elevia-compass`
> Ne jamais utiliser `~/Documents/elevia-compass` (iCloud, imports lents, hangs pytest).

## Lancer proprement

Canonique:

```bash
make dev-up
```

Ça démarre l’API avec le bon `.venv` et le frontend sur le bon port.

## Lancer manuellement si nécessaire

```bash
# Terminal 1 — API
make api
# → http://localhost:8000  (ELEVIA_DEV_TOOLS=1, reload activé)

# Terminal 2 — Frontend
make web
# → http://localhost:3001

# Page Dev Tools
open http://localhost:3001/dev/cv-delta
# Depuis un téléphone :
open http://$(ipconfig getifaddr en0):3001/dev/cv-delta
```

## Premier démarrage (une seule fois)

```bash
make venv
source .venv/bin/activate
make install
```

## Tests

```bash
# Tests cv-delta uniquement (rapides)
make test-cvdelta

# Suite complète
make test
```

## Dépannage

| Symptôme | Cause | Fix |
|----------|-------|-----|
| `POST /dev/cv-delta` → 403 | `ELEVIA_DEV_TOOLS` non défini | `make api` le définit automatiquement |
| `POST /dev/cv-delta` → 404 | FE appelle le mauvais port | Proxy Vite configuré dans `vite.config.ts` — vérifier que `make web` est lancé |
| pytest hang à l'import | Repo dans iCloud / Documents | Utiliser `~/Dev/elevia-compass` — voir [docs/infra/PYTEST_IMPORT_HANG_FIX.md](infra/PYTEST_IMPORT_HANG_FIX.md) |
| `OPENAI_API_KEY` manquant | LLM désactivé silencieusement | Normal — mode A actif, `warning` dans la réponse |
| `Form data requires "python-multipart"` au lancement API | mauvais `uvicorn` / mauvais Python | utiliser `make api` ou `make dev-up`, jamais `uvicorn api.main:app` en global |

## Architecture en 30 secondes

```
Browser (3001)
  └─ Vite proxy /dev/* ──► FastAPI (8000)
                                └─ POST /dev/cv-delta
                                      └─ ELEVIA_DEV_TOOLS=1 (gating)
                                      └─ cv_parsing_delta_report.build_report()
```

Voir [docs/ARCHITECTURE_STABLE.md](ARCHITECTURE_STABLE.md) pour le détail.
