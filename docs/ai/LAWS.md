# LAWS - Règles Fondamentales Agentic

Version: 1.0.0
Sprint: 21 - Agentic Setup

## Règles Non-Négociables

### L1. Patch ou Silence
> Un agent qui n'a rien à corriger NE PRODUIT PAS de sortie verbeuse.
> Sortie = `STATUS: ok` + résumé 1 ligne max.

### L2. Schéma de Sortie Obligatoire
> Toute réponse agent DOIT suivre OUTPUT_SCHEMA.md.
> Pas de prose libre. Pas d'exception.

### L3. Scope Strict
> Chaque agent traite UNIQUEMENT sa zone de responsabilité.
> Un agent FEAT ne commente pas la sécurité. Un agent SEC ne propose pas de features.

### L4. Evidence Over Opinion
> Les observations doivent être factuelles et vérifiables.
> `"Ligne 42: SQL injection possible"` > `"Le code semble vulnérable"`

### L5. Backward Compatibility First
> Aucune modification ne casse les contrats API existants.
> Nouveaux champs = additifs. Suppressions = migration obligatoire.

### L6. Tests ou Reject
> Pas de merge sans tests. Un agent QA DOIT valider la couverture.
> Exception: docs-only (validation markdown uniquement).

### L7. Rollback Ready
> Chaque PR doit documenter sa procédure de rollback.
> Si rollback impossible → flag RISKS: high.

### L8. Human Final Call
> Les agents recommandent. L'humain décide.
> Aucun agent n'a autorité de merge automatique.

## Hiérarchie des Verdicts

```
BLOCKED > WARN > OK
```

- `BLOCKED`: Merge interdit jusqu'à correction
- `WARN`: Merge possible avec justification humaine
- `OK`: Aucun problème détecté

## Application

Ces règles s'appliquent à:
- Tous les agents définis dans `.continue/agents/`
- Toutes les reviews automatisées
- Toutes les PR vers `main`
