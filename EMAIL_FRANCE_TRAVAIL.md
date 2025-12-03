# Email pour France Travail - Demande d'Activation de Scopes API

---

**À :** support-api@francetravail.fr
**Objet :** Demande d'activation scopes api_romev1 et api_marchetravailv1 - Projet Elevia Compass

---

Bonjour,

Je développe actuellement **Elevia Compass**, un projet d'analyse du marché de l'emploi et d'orientation professionnelle basé sur un graphe métiers-compétences.

## Situation actuelle

Mon application utilise les APIs France Travail avec les identifiants suivants :
- **CLIENT_ID** : `PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d`
- **Scopes actuellement activés** : `api_offresdemploiv2`, `o2dsoffre`

## Tests effectués

J'ai testé l'accès aux différentes APIs France Travail et voici les résultats :

| API | Status | Code erreur |
|-----|--------|-------------|
| API Offres d'emploi v2 | ✅ Fonctionne | 200 OK |
| API ROME Métiers | ❌ Bloqué | 401 Unauthorized |
| API ROME Compétences | ❌ Bloqué | 401 Unauthorized |
| API ROME Contextes | ❌ Bloqué | 401 Unauthorized |
| API Marché du Travail | ❌ Bloqué | 401 Unauthorized |

Les erreurs 401 indiquent que mon compte n'a pas les scopes nécessaires pour accéder à ces APIs.

## Objectif du projet

Elevia Compass a pour but de :
1. **Construire un graphe métiers-compétences** à partir du référentiel ROME
2. **Calculer des similarités** entre métiers basées sur les compétences communes
3. **Recommander des transitions professionnelles** aux demandeurs d'emploi
4. **Analyser les tensions du marché** par zone géographique et métier

Pour réaliser ces objectifs, j'ai besoin d'accéder :
- Au **référentiel ROME complet** (métiers et compétences) → API ROME
- Aux **statistiques du marché du travail** (indicateurs de tension) → API Marché du Travail

## Demande

Je souhaiterais activer les scopes suivants sur mon compte :

### 1. **api_romev1** (CRITIQUE pour le projet)
- Nécessaire pour accéder aux endpoints :
  - `/rome/v1/metiers` (référentiel des métiers ROME)
  - `/rome/v1/competences` (référentiel des compétences)
  - `/rome/v1/contextes-travail` (contextes de travail)
  - `/rome/v1/fiches-metiers/{code}` (détails métier avec compétences)

- **Sans ce scope** : Le graphe métiers-compétences reste vide car les offres d'emploi ne contiennent presque pas de compétences détaillées.

### 2. **api_marchetravailv1** (Important)
- Nécessaire pour accéder aux statistiques du marché du travail
- Permet d'obtenir les indicateurs de tension par métier et zone géographique

## Configuration souhaitée

```
FT_SCOPES=api_offresdemploiv2 o2dsoffre api_romev1 api_marchetravailv1
```

## Prochaines étapes

Une fois les scopes activés, je pourrai :
1. Récupérer le référentiel ROME complet
2. Construire le graphe Compass opérationnel
3. Fournir des recommandations de reconversion basées sur les compétences
4. Intégrer les données de tension du marché

## Informations complémentaires

- **Type de projet** : Recherche et développement, orientation professionnelle
- **Utilisation** : Analyse de données, pas de revente commerciale directe
- **Volume estimé** : ~1000 appels API/jour (récupération initiale + mises à jour)

Je reste disponible pour toute information complémentaire concernant le projet ou son cadre d'utilisation.

Merci d'avance pour votre aide.

Cordialement,

[Ton nom]
[Ton organisation/entreprise si applicable]
[Ton email]
[Ton téléphone si applicable]

---

**Pièces jointes suggérées** :
- Fichier de test : `test_all_apis.py` (preuve des erreurs 401)
- Rapport technique : `STATUS_APIS_FRANCE_TRAVAIL.md`
