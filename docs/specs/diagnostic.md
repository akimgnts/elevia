# Spécifications Techniques — Sprint 9 : Matching Diagnostic

**Version :** 1.0 (Locked)
**Status :** Non-negotiable
**Objectif :** Produire un diagnostic factuel et lisible (OK / PARTIAL / KO) pour chaque offre, **sans modifier le calcul du score actuel**.

---

## 1. Principes Fondamentaux

1. **Immuabilité du Score**
   Le moteur de diagnostic tourne en parallèle du scoring.
   Il ne modifie ni les poids, ni le résultat final `score` (0–100).

2. **Atomicité des Verdicts**
   Chaque critère (Compétences, Langues, Éducation, etc.) rend un verdict unique et indépendant (`Verdict`).

3. **Max 3 Raisons**
   Le système ne renvoie jamais plus de 3 raisons bloquantes pour l'interface utilisateur.

4. **Hiérarchie Explicite**
   La gravité des verdicts est strictement définie :
   `KO > PARTIAL > OK`.
   Aucune comparaison implicite n'est autorisée.

---

## 2. Structure de Données (Contrat)

```python
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class Verdict(str, Enum):
    OK = "OK"           # Vert : Ne bloque rien
    PARTIAL = "PARTIAL" # Orange : Freine mais ne tue pas le match
    KO = "KO"           # Rouge : Bloque (ex: Visa, Langue, Compétence critique)

# Hiérarchie stricte pour l'agrégation
VERDICT_PRIORITY = {
    Verdict.KO: 3,
    Verdict.PARTIAL: 2,
    Verdict.OK: 1,
}

class CriterionResult(BaseModel):
    status: Verdict
    details: Optional[str] = None
    missing: List[str] = Field(default_factory=list)

class MatchingDiagnostic(BaseModel):
    # Piliers
    hard_skills: CriterionResult
    soft_skills: CriterionResult
    languages: CriterionResult
    education: CriterionResult
    vie_eligibility: CriterionResult

    # Synthèse
    global_verdict: Verdict
    top_blocking_reasons: List[str]  # Max 3 raisons formatées pour l'UI
```

---

## 3. Règles Métier & Seuils (Hardcoded)

### A. Constantes

```python
HARD_SKILL_KO_RATIO = 0.5  # Si > 50% des hard skills manquent → KO
```

---

### B. Logique par Critère

| Critère             | Règle du Verdict                                                                                    | Détails                                             |
| ------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| **Hard Skills**     | **KO** si `(missing / total) > HARD_SKILL_KO_RATIO`<br>**PARTIAL** si `missing > 0`<br>**OK** sinon | Comparaison stricte de compétences normalisées      |
| **Languages**       | **KO** si **au moins une** langue requise est manquante ou de niveau insuffisant<br>**OK** sinon    | Règle stricte : la langue est un prérequis bloquant |
| **Education**       | **PARTIAL** si `profile < required`<br>**OK** sinon                                                 | Jamais KO (expérience compensatoire possible)       |
| **Soft Skills**     | **PARTIAL** si manquants<br>**OK** sinon                                                            | **Jamais KO** (trop subjectif)                      |
| **VIE Eligibility** | **KO** si `age > 28` ou `nationalité hors UE`<br>**OK** sinon                                       | Règle légale Business France                        |

---

## 4. Logique d'Agrégation (Synthèse)

### A. Calcul du `global_verdict`

La hiérarchie doit être appliquée explicitement.

```python
def get_worst_verdict(verdicts: list[Verdict]) -> Verdict:
    return max(verdicts, key=lambda v: VERDICT_PRIORITY[v])
```

---

### B. Sélection des `top_blocking_reasons`

Contraintes :

* Maximum 3 raisons
* Les `KO` sont toujours prioritaires sur les `PARTIAL`
* L'ordre interne est **stable**, basé sur les piliers suivants :

```
VIE → Languages → Hard Skills → Education → Soft Skills
```

Algorithme :

1. Collecter tous les critères avec statut `KO` (dans l'ordre des piliers).
2. Ajouter leurs messages formatés.
3. Si moins de 3 raisons, ajouter les critères `PARTIAL` (même ordre).
4. Tronquer strictement à 3 éléments.

---

## 5. Règles d'Interprétation

* Un `global_verdict = KO` **n'implique pas** un score nul ou inférieur à un seuil.
* Le diagnostic sert à **expliquer** le score existant, pas à le justifier ni à le corriger.
* Les incohérences entre score et diagnostic sont **volontaires** et doivent être visibles.

---

## 6. Exemple de Sortie

```json
{
  "score": 72,
  "diagnostic": {
    "global_verdict": "KO",
    "top_blocking_reasons": [
      "Inéligible VIE : âge supérieur à 28 ans",
      "Langue requise manquante : Allemand (B2)",
      "Compétences clés manquantes : React, TypeScript"
    ],
    "languages": {
      "status": "KO",
      "missing": ["Allemand"],
      "details": "Niveau requis : B2"
    },
    "hard_skills": {
      "status": "PARTIAL",
      "missing": ["React", "TypeScript"],
      "details": "2 compétences manquantes sur 5"
    }
  }
}
```

---

**Fin de la spécification — toute implémentation doit s'y conformer strictement.**
