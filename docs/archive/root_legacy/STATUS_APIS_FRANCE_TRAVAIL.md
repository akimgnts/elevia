# 🔍 STATUS DES APIs FRANCE TRAVAIL - Elevia Compass

**Date**: 25 Novembre 2025
**Test effectué**: `test_all_apis.py`

---

## 📊 RÉSUMÉ GLOBAL

| Status | Nombre | % |
|--------|--------|---|
| ✅ **Fonctionnel** | **1** / 6 | 17% |
| ❌ **401 Unauthorized** (scope manquant) | **4** / 6 | 67% |
| ❌ **403 Forbidden** | **1** / 6 | 16% |

---

## 🔍 DÉTAIL PAR API

### 1. ✅ API Offres d'Emploi v2 — **FONCTIONNEL**

**Endpoint**: `/offresdemploi/v2/offres/search`
**Scope requis**: `api_offresdemploiv2` ✅ **ACTIVÉ**
**Status**: ✅ **SUCCESS**

**Test effectué**:
```bash
GET /offresdemploi/v2/offres/search?range=0-4
```

**Résultat**:
```json
{
  "resultats": [ /* 5 offres */ ],
  "filtresPossibles": { ... }
}
```

**📊 Données disponibles**:
- ✅ 6,150+ offres d'emploi récupérées
- ✅ 41 fichiers JSON dans `data/raw/`
- ✅ Champs complets: id, intitule, romeCode, lieuTravail, typeContrat, etc.

**🎯 Utilisation dans le projet**:
- ✅ Utilisé par le notebook `analysis_elevia_compass.ipynb`
- ✅ Table `fact_offers` complète
- ✅ Visualisations métiers/villes/contrats fonctionnelles

---

### 2. ❌ API ROME v1 - Métiers — **SCOPE MANQUANT**

**Endpoint**: `/rome/v1/metiers`
**Scope requis**: `api_romev1` ❌ **NON ACTIVÉ**
**Status**: ❌ **401 Unauthorized**

**Erreur**:
```
HTTP 401 (Unauthorized)
→ Scope 'api_romev1' non activé sur le compte France Travail
```

**Impact sur le projet**:
- ❌ Impossible de récupérer le référentiel complet ROME 4.0
- ⚠️ `dim_job` construite uniquement à partir des codes ROME des offres (incomplet)
- ⚠️ Pas de détails sur les métiers (définition, activités, etc.)

**Ce qui manque**:
- Référentiel ROME 4.0 complet (~500 métiers)
- Descriptions détaillées des métiers
- Hiérarchie des familles professionnelles

**Solution**:
1. Contacter France Travail
2. Demander l'activation du scope `api_romev1` (ou `api_romev1.read`)
3. Exécuter `python fetchers/fetch_rome_metiers.py`

---

### 3. ❌ API ROME v1 - Compétences — **SCOPE MANQUANT** (CRITIQUE ⚠️)

**Endpoint**: `/rome/v1/competences`
**Scope requis**: `api_romev1` ❌ **NON ACTIVÉ**
**Status**: ❌ **401 Unauthorized**

**Erreur**:
```
HTTP 401 (Unauthorized)
→ Scope 'api_romev1' non activé sur le compte France Travail
```

**Impact sur le projet**: ⚠️ **CRITIQUE pour Compass**
- ❌ **Aucune compétence** dans le graphe Compass
- ❌ `dim_skill` **VIDE** ou quasi-vide
- ❌ `bridge_offer_skill` **VIDE**
- ❌ **Pas d'arêtes** job-skill dans le graphe
- ❌ Impossible de calculer l'ICC (Indice de Compétences Communes)
- ❌ Impossible de recommander des transitions métiers basées sur les compétences

**Ce qui manque**:
- Référentiel ROME des compétences (~5,000+ compétences)
- Mapping métier → compétences
- Catégorisation des compétences (savoir-faire, savoir-être)

**Solution**:
1. Contacter France Travail
2. Demander l'activation du scope `api_romev1`
3. Exécuter `python fetchers/fetch_rome_competences.py`
4. Relancer le notebook pour avoir un graphe complet

---

### 4. ❌ API ROME v1 - Contextes de Travail — **SCOPE MANQUANT**

**Endpoint**: `/rome/v1/contextes-travail`
**Scope requis**: `api_romev1` ❌ **NON ACTIVÉ**
**Status**: ❌ **401 Unauthorized**

**Erreur**:
```
HTTP 401 (Unauthorized)
→ Scope 'api_romev1' non activé sur le compte France Travail
```

**Impact sur le projet**:
- ⚠️ Pas de contextes de travail (horaires, environnement, mobilité, etc.)
- ⚠️ Impossible d'enrichir le matching avec ces critères

**Ce qui manque**:
- Contextes de travail ROME (horaires, déplacements, conditions physiques, etc.)

**Solution**: Même que API ROME Métiers/Compétences

---

### 5. ❌ API Marché du Travail v1 — **SCOPE MANQUANT**

**Endpoint**: `/marche-travail/v1/statistiques`
**Scope requis**: `api_marchetravailv1` ❌ **NON ACTIVÉ**
**Status**: ❌ **401 Unauthorized**

**Erreur**:
```
HTTP 401 (Unauthorized)
→ Scope 'api_marchetravailv1' non activé sur le compte France Travail
```

**Impact sur le projet**:
- ⚠️ Impossible de calculer l'**ITM** (Indice de Tension du Marché)
- ⚠️ Pas de statistiques offres/demandes par métier et zone
- ⚠️ Pas d'indicateur de dynamisme du marché

**Ce qui manque**:
- Statistiques marché du travail (tensions, offres/demandes)
- Données par métier et zone géographique
- Évolutions temporelles

**Solution**:
1. Contacter France Travail
2. Demander l'activation du scope `api_marchetravailv1`
3. Exécuter `python fetchers/fetch_marche_travail.py`

---

### 6. ❌ API Anotéa v1 — **ERREUR 403 FORBIDDEN**

**Endpoint**: `/anotea/v1/formation`
**Scope requis**: `api_anoteav1` ❌ **NON ACTIVÉ** ou **API DÉPRÉCIÉE**
**Status**: ❌ **403 Forbidden**

**Erreur**:
```
HTTP 403 (Forbidden)
```

**Impact sur le projet**:
- ⚠️ Pas d'avis sur les organismes de formation
- ⚠️ Impossible d'enrichir les recommandations de formations

**Hypothèses**:
1. API Anotéa est peut-être dépréciée ou remplacée
2. Restrictions d'accès particulières (plus strictes que 401)
3. Endpoint incorrect

**Solution**:
1. Vérifier la documentation officielle France Travail
2. Contacter le support pour confirmer la disponibilité de cette API
3. Si dépréciée : abandonner ou trouver une alternative

---

## 🎯 IMPACT SUR LE PROJET ELEVIA COMPASS

### Ce qui fonctionne actuellement ✅

| Composant | Status | Détails |
|-----------|--------|---------|
| **Récupération offres** | ✅ | 6,150 offres disponibles |
| **fact_offers** | ✅ | Table complète |
| **dim_location** | ✅ | Localisation complète |
| **dim_job (basique)** | ✅ | Codes ROME extraits des offres |
| **Visualisations métiers/villes** | ✅ | Fonctionnelles |
| **Notebook (partiel)** | ✅ | S'exécute mais graphe incomplet |

### Ce qui est bloqué ❌

| Composant | Status | Raison |
|-----------|--------|--------|
| **dim_skill** | ❌ VIDE | API ROME Compétences manquante |
| **bridge_offer_skill** | ❌ VIDE | API ROME Compétences manquante |
| **Graphe Compass** | ❌ INCOMPLET | Pas d'arêtes job-skill |
| **ICC (similarité métiers)** | ❌ IMPOSSIBLE | Pas de compétences |
| **ITM (tension marché)** | ❌ IMPOSSIBLE | API Marché manquante |
| **Recommandations transitions** | ❌ IMPOSSIBLE | Graphe incomplet |

---

## 🔧 ACTIONS REQUISES

### Priorité 1 : Activer API ROME v1 (CRITIQUE ⚠️)

**Scope à demander** : `api_romev1` (ou `api_romev1.read`)

**Pourquoi c'est critique** :
- Sans les compétences ROME, le graphe Compass est **inutilisable**
- C'est le **cœur du projet** : impossible de recommander des trajectoires sans compétences

**Actions** :
1. Contacter France Travail via :
   - Email : support-api@francetravail.fr (à confirmer)
   - Espace développeur : https://francetravail.io/
2. Demander l'activation du scope `api_romev1` pour ton CLIENT_ID :
   ```
   PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d
   ```
3. Une fois activé, mettre à jour `.env` :
   ```env
   FT_SCOPES=api_offresdemploiv2 o2dsoffre api_romev1
   ```
4. Récupérer les données ROME :
   ```bash
   python fetchers/fetch_rome_metiers.py
   python fetchers/fetch_rome_competences.py
   python fetchers/fetch_rome_fiches_metiers.py
   ```
5. Relancer le notebook :
   ```bash
   source .venv/bin/activate
   jupyter notebook analysis_elevia_compass.ipynb
   ```

---

### Priorité 2 : Activer API Marché du Travail v1 (IMPORTANT)

**Scope à demander** : `api_marchetravailv1`

**Pourquoi c'est important** :
- Nécessaire pour calculer l'**ITM** (Indice de Tension du Marché)
- Permet d'affiner les recommandations avec données marché

**Actions** : Même processus que pour API ROME

---

### Priorité 3 : Clarifier API Anotéa (OPTIONNEL)

**Scope à demander** : `api_anoteav1` (si toujours disponible)

**Actions** :
1. Vérifier documentation officielle
2. Si API dépréciée : abandonner ou trouver alternative

---

## 📧 MODÈLE D'EMAIL POUR FRANCE TRAVAIL

```
Objet : Demande d'activation des scopes API ROME v1 et Marché du Travail v1

Bonjour,

Je développe un projet d'orientation professionnelle (Elevia Compass) utilisant
les APIs France Travail.

J'ai actuellement accès à l'API Offres d'emploi v2 (scope: api_offresdemploiv2)
et je souhaiterais activer les scopes supplémentaires suivants :

• api_romev1 (ou api_romev1.read)
  → Pour accéder au référentiel ROME 4.0 (métiers, compétences, contextes)

• api_marchetravailv1
  → Pour accéder aux statistiques du marché du travail

Mon CLIENT_ID :
PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d

Objectif du projet :
Créer un moteur de recommandation de trajectoires professionnelles basé sur
un graphe métiers-compétences et des simulations Monte Carlo.

Merci d'avance pour votre aide.

Cordialement,
[Ton nom]
```

---

## 📊 TABLEAU RÉCAPITULATIF DES SCOPES

| Scope | Status | APIs concernées | Priorité |
|-------|--------|-----------------|----------|
| `api_offresdemploiv2` | ✅ **ACTIF** | Offres d'emploi v2 | - |
| `o2dsoffre` | ✅ **ACTIF** | (scope technique) | - |
| `api_romev1` | ❌ **MANQUANT** | ROME Métiers, Compétences, Contextes | 🔴 **CRITIQUE** |
| `api_marchetravailv1` | ❌ **MANQUANT** | Marché du Travail | 🟡 **IMPORTANT** |
| `api_anoteav1` | ❌ **MANQUANT** | Anotéa (formations) | 🟢 **OPTIONNEL** |

---

## 🚀 PROCHAINES ÉTAPES

### Court terme (sans scopes supplémentaires)
1. ✅ Exécuter le notebook actuel pour voir les analyses partielles
2. ✅ Générer les visualisations métiers/villes
3. ⚠️ Accepter que le graphe Compass soit incomplet

### Moyen terme (avec scopes ROME)
1. ✅ Activer `api_romev1`
2. ✅ Récupérer toutes les données ROME
3. ✅ Relancer le notebook → graphe complet
4. ✅ Implémenter ICC, recommandations de transitions

### Long terme (tous les scopes)
1. ✅ Activer `api_marchetravailv1`
2. ✅ Calculer ITM, IET
3. ✅ Affiner les recommandations avec données marché
4. ✅ Monte Carlo avec probabilités réalistes

---

## 🔗 LIENS UTILES

- Documentation France Travail : https://francetravail.io/data/documentation
- Espace développeur : https://francetravail.io/mon-espace
- Support API : support-api@francetravail.fr

---

**✅ Test effectué par** : `test_all_apis.py`
**📅 Date** : 25 Novembre 2025
**🤖 Diagnostic** : Claude Code
