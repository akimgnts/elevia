# OUTPUT_SCHEMA - Format de Sortie Obligatoire

Version: 1.0.0
Sprint: 21 - Agentic Setup

## Structure

Chaque agent DOIT produire une sortie suivant ce schéma exact:

```
STATUS: ok | warn | blocked
SCOPE: <zone analysée>
PLAN: <actions si warn/blocked, sinon "none">
PATCH: <diff unifié si correction proposée, sinon "none">
TESTS: <commandes de validation, sinon "none">
RISKS: <risques identifiés, sinon "none">
```

## Champs

### STATUS (obligatoire)
- `ok`: Aucun problème détecté. Merge autorisé.
- `warn`: Problème mineur. Merge possible avec justification.
- `blocked`: Problème critique. Merge interdit.

### SCOPE (obligatoire)
Zone de responsabilité de l'agent. Une ligne.
```
SCOPE: API routes - apps/api/src/api/routes/matching.py
```

### PLAN (conditionnel)
- Si `STATUS: ok` → `PLAN: none`
- Sinon → Liste à puces des actions correctives

```
PLAN:
- Ajouter validation d'entrée ligne 45
- Corriger injection SQL ligne 78
- Mettre à jour tests
```

### PATCH (conditionnel)
- Si correction proposée → Diff unifié
- Sinon → `PATCH: none`

```
PATCH:
--- a/src/api/routes/matching.py
+++ b/src/api/routes/matching.py
@@ -45,3 +45,5 @@
+    if not validate_input(data):
+        raise HTTPException(400, "Invalid input")
```

### TESTS (conditionnel)
- Si tests à exécuter → Commandes
- Sinon → `TESTS: none`

```
TESTS:
pytest tests/test_matching.py -v -k test_input_validation
```

### RISKS (conditionnel)
- Si risques identifiés → Liste à puces avec niveau (low/medium/high)
- Sinon → `RISKS: none`

```
RISKS:
- [high] Breaking change API v1/match
- [medium] Performance dégradée si >1000 offres
- [low] Edge case non couvert pour profils vides
```

## Exemples

### Agent OK (rien à signaler)
```
STATUS: ok
SCOPE: Security - apps/api/src/api/routes/matching.py
PLAN: none
PATCH: none
TESTS: none
RISKS: none
```

### Agent WARN (problème mineur)
```
STATUS: warn
SCOPE: Reliability - apps/api/scripts/run_ingestion.py
PLAN:
- Ajouter retry sur timeout ligne 156
PATCH:
--- a/scripts/run_ingestion.py
+++ b/scripts/run_ingestion.py
@@ -156,1 +156,3 @@
-    response = requests.get(url, timeout=30)
+    for attempt in range(3):
+        try:
+            response = requests.get(url, timeout=30)
+            break
+        except requests.Timeout:
+            if attempt == 2: raise
TESTS:
pytest tests/test_ingestion.py -v -k test_timeout_retry
RISKS:
- [low] Latence augmentée en cas de timeout répétés
```

### Agent BLOCKED (problème critique)
```
STATUS: blocked
SCOPE: Security - apps/api/src/api/routes/profile.py
PLAN:
- Corriger injection SQL ligne 42
- Ajouter parameterized query
- Ajouter test de sécurité
PATCH:
--- a/src/api/routes/profile.py
+++ b/src/api/routes/profile.py
@@ -42,1 +42,1 @@
-    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
+    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
TESTS:
pytest tests/test_security.py -v
RISKS:
- [high] Vulnérabilité SQL injection en production
```

## Validation

Un agent non conforme au schéma = sortie ignorée + erreur CI.
