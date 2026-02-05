# Workflow Scrum + Claude Code

## Rôles

| Rôle | Qui | Responsabilité |
|------|-----|----------------|
| Product Owner | Akim | Définit le Sprint Goal, priorise le backlog, décide |
| SCRUM Agent | Claude (mode SCRUM) | Protège le cadre, refuse les dérives, valide les sprints |
| DEV | Claude (mode DEV) | Exécute les tâches, code, teste |
| QA/FEAT/SEC/OBS | Claude (agents) | Vérifient qualité, contrats, sécurité, observabilité |

## Cycle de Sprint

### 1. Sprint Planning (5 min)

```
PO: Définit Sprint Goal + sélectionne 3-5 items du backlog
↓
SCRUM: Vérifie les critères (Goal clair, usage prévu, max 5 items)
       Si OK → Sprint démarre
       Si KO → Demande clarification
```

### 2. Exécution (durée du sprint)

```
Pour chaque item:
  PO: Décrit le besoin
  ↓
  Claude DEV: Implémente
  ↓
  Agents (QA/FEAT/SEC): Vérifient
  ↓
  SCRUM: Vérifie que ça sert le Sprint Goal
```

**Règle stricte** : Aucun nouvel item ajouté en cours de sprint (sauf P0).

### 3. Daily (optionnel, 2 min)

Si le sprint dure > 3 jours :
- Qu'est-ce qui a avancé vers le Goal ?
- Qu'est-ce qui va avancer aujourd'hui ?
- Blocage ?

### 4. Sprint Review (10 min)

```
SCRUM: Pose les 5 questions de REVIEW.md
PO: Répond
→ Décision pour le prochain sprint
```

### 5. Sprint Retro (5 min)

```
Garder / Supprimer / Changer (1 règle max)
→ Appliquer au prochain sprint
```

## Comment Invoquer les Modes

### Mode DEV (par défaut)

Claude exécute les tâches techniques. Prompt normal.

### Mode SCRUM

Préfixer le prompt avec :

```
[SCRUM] Vérifie que ce sprint est valide : docs/scrum/sprints/SPRINT_XX.md
```

ou

```
[SCRUM] Peut-on ajouter cette tâche au sprint en cours ?
```

SCRUM répondra avec son output standardisé (STATUS, SCOPE, etc.)

## Fichiers Clés

| Fichier | Usage |
|---------|-------|
| `.claude/agents/SCRUM.md` | Règles de l'agent SCRUM |
| `docs/scrum/BACKLOG.md` | Product Backlog trié |
| `docs/scrum/sprints/SPRINT_XX.md` | Sprint en cours |
| `docs/scrum/DAILY.md` | Template daily |
| `docs/scrum/REVIEW.md` | Questions sprint review |
| `docs/scrum/RETRO.md` | Template retro |

## Anti-Patterns (SCRUM refuse)

- "On ajoute juste cette petite tâche" → Non
- Sprint sans Sprint Goal → Non
- Sprint > 5 items → Non
- "On verra si c'est utile" → Non, définir l'usage avant
- Complexité sans valeur utilisateur → Non
