# ❌ CE QUI NE VA PAS - Elevia Compass

**Date**: 3 Décembre 2025
**Basé sur**: Test complet des APIs France Travail

---

## 🔴 PROBLÈME #1 - CRITIQUE: API ROME Compétences MANQUANTE

### Le problème

**5 APIs sur 6 sont BLOQUÉES** (erreur 401 Unauthorized)

```
❌ API ROME Métiers         → 401 (scope api_romev1 manquant)
❌ API ROME Compétences     → 401 (scope api_romev1 manquant) 🔴 CRITIQUE
❌ API ROME Contextes       → 401 (scope api_romev1 manquant)
❌ API Marché du Travail    → 401 (scope api_marchetravailv1 manquant)
❌ API Anotéa               → 403 (Forbidden - API probablement dépréciée)
✅ API Offres d'emploi      → OK (6,150 offres récupérées)
```

### Impact sur le projet

#### ❌ Ce qui ne marchera PAS

1. **Le graphe métiers-compétences sera VIDE**
   ```
   Graphe Compass:
   - Nœuds job: ✅ OK (~100 métiers ROME des offres)
   - Nœuds skill: ❌ VIDE (0 compétences)
   - Arêtes job-skill: ❌ VIDE (0 connexions)
   ```

2. **dim_skill sera VIDE**
   - Les offres d'emploi n'ont PRESQUE PAS de compétences renseignées
   - Test effectué: Sur 6,150 offres, moins de 1% ont des compétences
   - Les compétences DOIVENT venir de l'API ROME

3. **bridge_offer_skill sera VIDE**
   - Aucune association offre → compétence possible

4. **Impossible de calculer l'ICC (Indice de Compétences Communes)**
   ```python
   # Cette fonction retournera toujours 0
   def compute_icc(job1, job2):
       skills1 = get_skills_for_job(job1)  # []
       skills2 = get_skills_for_job(job2)  # []
       common = set(skills1) & set(skills2)  # set()
       return len(common) / ...  # 0
   ```

5. **Impossible de recommander des transitions métiers**
   - Le cœur du projet Compass repose sur les compétences communes
   - Sans compétences = Pas de recommandations possibles

---

## 🔴 PROBLÈME #2: Graphe Inutilisable

### Ce que le notebook va produire

```
Graphe Compass V0:
├── Nœuds: ~100 (métiers ROME uniquement)
├── Arêtes: 0 (aucune connexion)
├── Composantes connexes: 100 (chaque nœud est isolé)
└── Utilité: NULLE
```

### Conséquences

```python
# Toutes ces fonctions seront inutilisables:

def find_similar_jobs(job_id):
    # Retourne toujours []
    return []

def recommend_transitions(current_job):
    # Retourne toujours []
    return []

def monte_carlo_simulation(start_job, n_steps):
    # Impossible de bouger, bloqué sur start_job
    return [start_job] * n_steps
```

---

## 🔴 PROBLÈME #3: ITM (Indice Tension Marché) Impossible à Calculer

### Le problème

L'API Marché du Travail v1 est bloquée (erreur 401)

### Impact

```python
# Cette fonction ne pourra pas fonctionner
def compute_itm(job_id, location_id):
    # Besoin de:
    # - Nombre d'offres par métier/zone (✅ disponible)
    # - Nombre de demandeurs d'emploi (❌ API Marché manquante)
    # → ITM impossible à calculer
    return None
```

---

## 🔴 PROBLÈME #4: Matrice de Transition Basique

### Ce que le notebook va produire

Sans compétences, la matrice de transition sera une **matrice identité**:

```python
P = np.eye(n_jobs)  # Matrice identité
# Signification: probabilité 1 de rester dans son métier
#                 probabilité 0 de transitionner
```

### Monte Carlo sera inutile

```python
# Simulation sur 10 ans = toujours le même métier
trajectory = monte_carlo(start_job="D1101", n_steps=10)
# Résultat: ["D1101", "D1101", "D1101", ..., "D1101"]
```

---

## ✅ CE QUI VA QUAND MÊME MARCHER

### Tables

| Table | Status | Contenu |
|-------|--------|---------|
| `fact_offers` | ✅ | 6,150 offres complètes |
| `dim_location` | ✅ | ~200 villes/départements |
| `dim_job` | ✅ | ~100 métiers ROME (depuis offres) |
| `dim_skill` | ❌ | **VIDE** |
| `bridge_offer_skill` | ❌ | **VIDE** |
| `bridge_job_skill` | ❌ | **VIDE** |

### Visualisations

```
✅ Top 20 métiers (codes ROME)
✅ Top 20 villes
✅ Top 20 départements
✅ Distribution types de contrats (CDI, CDD, etc.)
⚠️  Distribution salaires (beaucoup de NaN)
❌ Top compétences demandées (vide)
❌ Clusters de métiers similaires (impossible)
❌ Graphe interactif (nœuds isolés)
```

---

## 🎯 RÉSULTAT FINAL

### Si tu lances le notebook MAINTENANT

```bash
source .venv/bin/activate
jupyter notebook analysis_elevia_compass.ipynb
```

**Ce qui va se passer**:

1. ✅ Le notebook **va s'exécuter SANS ERREUR**
2. ✅ Les cellules vont toutes fonctionner
3. ⚠️  Mais le graphe sera **VIDE**
4. ⚠️  Les recommandations seront **IMPOSSIBLES**
5. ⚠️  L'objectif du projet Compass sera **NON ATTEINT**

### Affichage attendu

```
📊 Chargement des données...
✅ 6,150 offres chargées

📊 Création des tables...
✅ fact_offers: (6150, 15)
✅ dim_job: (98, 2)
✅ dim_location: (203, 2)
⚠️  dim_skill: (0, 3)  ← VIDE!

📊 Construction du graphe Compass...
⚠️  ATTENTION: Aucune compétence trouvée dans les offres.
   → Activer le scope api_romev1 pour obtenir le référentiel complet
✅ Graphe créé: 98 nœuds, 0 arêtes  ← INUTILISABLE!

📊 Calcul de la matrice de transition...
⚠️  Matrice identité (pas de transitions possibles)

📊 Simulation Monte Carlo...
⚠️  Trajectoire bloquée (pas de transitions disponibles)
```

---

## 💡 LA SOLUTION

### Court terme: Voir ce qui marche

```bash
# 1. Lance quand même le notebook pour voir les analyses partielles
cd /Users/akimguentas/Documents/elevia-compass
source .venv/bin/activate
jupyter notebook analysis_elevia_compass.ipynb

# 2. Tu pourras voir:
#    - Analyses des métiers
#    - Analyses des localisations
#    - Types de contrats
```

**Mais Compass ne fonctionnera pas.**

---

### Long terme: Débloquer le projet (OBLIGATOIRE)

#### Étape 1: Contacter France Travail

**Email**: support-api@francetravail.fr (à confirmer sur francetravail.io)

**Objet**: Demande d'activation scope api_romev1

**Message**:
```
Bonjour,

Je développe un projet d'orientation professionnelle (Elevia Compass)
utilisant les APIs France Travail.

Actuellement, j'ai accès à :
• api_offresdemploiv2 ✅
• o2dsoffre ✅

Je souhaiterais activer les scopes suivants :
• api_romev1 (CRITIQUE pour mon projet)
• api_marchetravailv1 (important)

CLIENT_ID: PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d

Le projet nécessite le référentiel ROME complet (métiers et compétences)
pour construire un graphe de transitions professionnelles.

Merci d'avance,
[Ton nom]
```

#### Étape 2: Une fois les scopes activés

```bash
# 1. Mettre à jour .env
FT_SCOPES=api_offresdemploiv2 o2dsoffre api_romev1 api_marchetravailv1

# 2. Récupérer les données ROME
python fetchers/fetch_rome_metiers.py
python fetchers/fetch_rome_competences.py
python fetchers/fetch_rome_fiches_metiers.py

# 3. Retester les APIs
python test_all_apis.py

# 4. Relancer le notebook
jupyter notebook analysis_elevia_compass.ipynb
```

#### Étape 3: Vérifier que tout fonctionne

```bash
# Le notebook devrait afficher:
✅ dim_skill: (5000+, 3)  ← Compétences chargées!
✅ Graphe: 5098 nœuds, 15000+ arêtes  ← Utilisable!
✅ ICC moyen: 0.23
✅ Recommandations: 10 transitions proposées
```

---

## 📊 TABLEAU COMPARATIF

| Fonctionnalité | SANS api_romev1 | AVEC api_romev1 |
|----------------|-----------------|-----------------|
| Chargement offres | ✅ 6,150 offres | ✅ 6,150 offres |
| dim_job | ✅ ~100 métiers | ✅ ~500 métiers ROME complets |
| dim_skill | ❌ VIDE | ✅ ~5,000 compétences |
| bridge_job_skill | ❌ VIDE | ✅ ~50,000 associations |
| Graphe Compass | ❌ 0 arêtes | ✅ 15,000+ arêtes |
| ICC (similarité) | ❌ Toujours 0 | ✅ Fonctionnel |
| Recommandations | ❌ Impossibles | ✅ Fonctionnelles |
| Monte Carlo | ❌ Bloqué | ✅ Trajectoires réalistes |
| Projet Compass | ❌ **BLOQUÉ** | ✅ **FONCTIONNEL** |

---

## 🎯 CONCLUSION

### État actuel du projet

```
🟢 Environnement technique: OK
🟢 Récupération des offres: OK
🟢 Analyses basiques: OK
🔴 Graphe Compass: BLOQUÉ
🔴 Recommandations: BLOQUÉ
🔴 Objectif du projet: NON ATTEINT
```

### Action OBLIGATOIRE

**Tu DOIS activer le scope `api_romev1` pour que le projet fonctionne.**

Sans ce scope, Elevia Compass ne peut PAS:
- Construire un graphe métiers-compétences
- Calculer des similarités entre métiers
- Recommander des transitions professionnelles
- Simuler des trajectoires réalistes

**Le scope `api_romev1` n'est pas optionnel, c'est le CŒUR du projet.**

---

**📧 Prochaine étape**: Contacter France Travail pour activer `api_romev1`

**⏱️ En attendant**: Tu peux lancer le notebook pour voir les analyses partielles,
mais sache que l'objectif principal (Compass) ne sera pas atteint.

---

**✅ Diagnostic effectué**: 3 Décembre 2025
**🤖 Par**: Claude Code
**🎯 Statut**: Projet BLOQUÉ sans api_romev1
