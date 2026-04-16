# Profile Wizard Enrichment Implementation

Date: 2026-04-16

## Executive Summary

Le wizard `/profile` consomme maintenant non seulement `structuring_report`, mais aussi `enrichment_report`.

Le résultat produit est le suivant:
- Step 1 montre ce que le système a compris et ce qu'il a complété automatiquement
- Step 2 affiche tous les `skill_links` d'une expérience, pas seulement le premier
- Step 3 fusionne les questions de structuration et d'enrichissement
- Step 4 ferme explicitement la boucle vers matching, CV et cockpit

Les enrichissements `auto_filled` sont:
- déjà appliqués
- visibles
- traçables
- éditables

Quand un utilisateur modifie un champ enrichi automatiquement, le champ est traité comme `user_validated`.

## Scope Implemented

### 1. Shared Wizard Types

File:
- `apps/web/src/components/profile/profileWizardTypes.ts`

Changes:
- ajout des types `EnrichmentReport`, `EnrichmentAutoFilled`, `EnrichmentTraceEntry`
- unification du type `WizardQuestion`
- support des champs cibles nécessaires au merge `structuring + enrichment`

### 2. Step 1: Understanding + Value

File:
- `apps/web/src/components/profile/AgentUnderstandingStep.tsx`

Changes:
- affichage des métriques de structuration
- ajout du bloc `Ce que ça change pour vous`
- affichage des enrichissements automatiques visibles
- exposition du volume de questions restantes et des signaux prioritaires

### 3. Step 2: Multi-Skill-Link Experience View

Files:
- `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
- `apps/web/src/pages/ProfilePage.tsx`

Changes:
- affichage de tous les `skill_links` par expérience
- sélection du `skill_link` actif par index
- correction ciblée par lien, au lieu d'un mode mono-lien
- badges de provenance:
  - `Ajouté automatiquement`
  - `user_validated`
- write-back direct dans `career_profile.experiences[*].skill_links`

### 4. Step 3: Merged Clarification Questions

Files:
- `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
- `apps/web/src/pages/ProfilePage.tsx`

Changes:
- fusion des questions issues de `structuring_report.questions_for_user`
- fusion des questions issues de `enrichment_report.questions`
- déduplication par `experience_index` + `target_field`
- conservation de la provenance (`structuring` ou `enrichment`)
- réponses écrites directement dans `career_profile`

### 5. Step 4: Final Validation Loop

File:
- `apps/web/src/components/profile/ProfileValidationStep.tsx`

Changes:
- fermeture explicite de la boucle produit
- rappel de l'usage du profil pour:
  - matching
  - CV
  - cockpit
- CTA de validation maintenu

## Files Modified

- [apps/web/src/components/profile/profileWizardTypes.ts](/Users/akimguentas/Dev/elevia-compass/apps/web/src/components/profile/profileWizardTypes.ts:1)
- [apps/web/src/components/profile/AgentUnderstandingStep.tsx](/Users/akimguentas/Dev/elevia-compass/apps/web/src/components/profile/AgentUnderstandingStep.tsx:1)
- [apps/web/src/components/profile/StructuredExperiencesStep.tsx](/Users/akimguentas/Dev/elevia-compass/apps/web/src/components/profile/StructuredExperiencesStep.tsx:1)
- [apps/web/src/components/profile/ClarificationQuestionsStep.tsx](/Users/akimguentas/Dev/elevia-compass/apps/web/src/components/profile/ClarificationQuestionsStep.tsx:1)
- [apps/web/src/components/profile/ProfileValidationStep.tsx](/Users/akimguentas/Dev/elevia-compass/apps/web/src/components/profile/ProfileValidationStep.tsx:1)
- [apps/web/src/pages/ProfilePage.tsx](/Users/akimguentas/Dev/elevia-compass/apps/web/src/pages/ProfilePage.tsx:1)
- [apps/web/tests/test_profile_wizard_flow.py](/Users/akimguentas/Dev/elevia-compass/apps/web/tests/test_profile_wizard_flow.py:1)

## Verification

Commands run:

```bash
./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q
cd apps/web && npm run build
graphify update .
```

Result:
- wizard guardrail tests pass
- frontend production build passes
- graphify knowledge graph updated

## Remaining Limits

- le test frontend ajouté reste un garde-fou structurel, pas un test comportemental e2e
- le bundle frontend principal reste volumineux, avec warning Vite sur la taille du chunk
- `enrichment_report` est maintenant branché au wizard, mais pas encore exploité plus largement dans le cockpit

## Next Logical Step

Priorité produit suivante:
- brancher `priority_signals` et les enrichissements visibles dans le cockpit
- renforcer les tests comportementaux du wizard
- unifier plus strictement la structuration backend autour d'une seule source métier si nécessaire
