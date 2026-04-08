# Apply Pack CV Engine

## Objectif
Construire un moteur déterministe de CV miroir par offre pour Elevia.

## Entrée
- `job_offer`
- `profile.experiences`
- `profile.skills`
- `profile.education`

## Pipeline
1. Parse offer
2. Ranking des expériences
3. Sélection des verbes d'action
4. Réécriture des bullets sous forme de preuve
5. Tri des compétences
6. Rendu final markdown + HTML ATS
7. Sortie debug

## Règles produit
- une seule colonne
- pas de section profil
- maximum 5 expériences
- verbes à l'infinitif
- priorité aux preuves et à la quantification
- suppression du bruit et des expériences hors cible

## Debug attendu
- score détaillé de chaque expérience
- décision `keep|compress|drop`
- verbes sélectionnés
- données manquantes ou trop faibles

## Fichiers sources
- `data/action_verbs.json`
- `templates/resume_finance.html`
- `apps/api/src/documents/apply_pack_cv_engine.py`
