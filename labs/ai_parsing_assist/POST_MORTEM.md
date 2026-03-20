# AI Parsing Assist — Post-Mortem

## Objectif
Tester si une couche AI bornée, avant la consolidation structurée, pouvait améliorer la compréhension des segments CV ambigus sans toucher au moteur déterministe.

## Hypothèse
Des segments faibles ou narratifs contiennent un signal métier récupérable par un modèle contraint, puis validable par gating déterministe.

## Architecture testée
- parser déterministe = source de vérité
- AI = sidecar segment par segment
- entrée courte et structurée
- sortie JSON stricte
- gating dur avant toute acceptation
- aucun effet sur canonical, matching, scoring, ou sortie finale par défaut

## Protocole
- baseline vs assisted
- benchmark synthétique
- validation CV réels
- mesure des hit rates, top-signal relevance, faux positifs, cas aidés / dégradés

## Résultats
- aucun gain métrique
- aucune amélioration sur les CV hybrides réels
- `0` enrichissement accepté
- `0` régression
- coût ajouté: complexité + latence

## Pourquoi ça n'a pas marché
- les segments envoyés étaient surtout pauvres, pas seulement ambigus
- l'AI a surtout paraphrasé le texte
- les propositions restaient trop faibles pour passer le gate
- les couches déterministes récupéraient déjà l'essentiel du signal utile
- le vrai bottleneck est la structure d'entrée, pas l'interprétation sémantique

## Décision
`REJECTED`

## Ce qu'on garde en labo
- contrat de prompt
- logique de gating
- harness d'évaluation
- résultats d'expérience

## Ce qu'on retire du runtime
- tout wiring pipeline
- toute exposition API
- toute exécution derrière flag dans la parsing pipeline produit

## Prochaine direction
Structured Extraction v2:
- segmentation des bullets narratifs
- split multi-actions
- extraction action/object plus robuste
- réduction des objets vagues
- couverture non-tech renforcée
