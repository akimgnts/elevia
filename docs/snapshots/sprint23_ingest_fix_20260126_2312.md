# Sprint 23 Ingest Fix Snapshot (2026-01-26 23:12)

## Context
- Endpoint ciblé: POST /profile/ingest_cv
- Frontend: /analyze → clic "Trouver mes offres"
- Backend attendu: uvicorn (port 8000)

## Frontend reproduction
- Non reproduit ici (UI locale non accessible depuis cet environnement).
- Erreur utilisateur rapportée: "Le service d’extraction n’est pas disponible".

## Curl reproduction
```bash
curl -i -X POST http://127.0.0.1:8000/profile/ingest_cv \
  -H "Content-Type: application/json" \
  -d '{"cv_text":"Prospection, négociation, closing. Gestion portefeuille clients."}'
```

### Curl output
```
curl: (7) Failed to connect to 127.0.0.1 port 8000 after 0 ms: Couldn't connect to server
```

## Backend logs
- Tentative de démarrage local (sandbox) :
```
ERROR: [Errno 1] error while attempting to bind on address ('127.0.0.1', 8000): [errno 1] operation not permitted
```

## Hypothèse de cause
- Provider LLM configuré sur OpenAI sans dépendance `openai` installée (requirements manquant).
