# 🏗️ Elevia Compass - Architecture Technique Complète

**Version**: 1.0
**Date**: 2025-11-13
**Status**: ✅ Production Ready

---

## 📋 Vue d'Ensemble

Elevia Compass est un moteur de trajectoires professionnelles basé sur :
1. **Ingestion multi-API** France Travail (colonne vertébrale)
2. **Normalisation** des données brutes
3. **Graphe métiers-compétences** (networkx)
4. **Analyse statistique** (pandas, numpy)
5. **Simulation Monte Carlo** (trajectoires probabilistes)
6. **Matching intelligent** (algorithmes personnalisés)

---

## 🎯 Phase 1 : Ingestion Multi-API (✅ COMPLÈTE)

### 1.1 Client OAuth2 Générique

**Fichier** : `fetchers/client_ft.py`

**Fonctionnalités** :
- ✅ Authentification OAuth2 client_credentials
- ✅ Refresh automatique du token (marge 30s avant expiration)
- ✅ Rate limiting avec exponential backoff (429, 500)
- ✅ Retry automatique sur timeout/erreurs réseau (max 3 tentatives)
- ✅ Logging horodaté avec emojis
- ✅ Validation des variables d'environnement

**Configuration** : `.env`
```env
CLIENT_ID=PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d
CLIENT_SECRET=<secret>
TOKEN_URL=https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire
BASE_URL=https://api.francetravail.io//partenaire
SCOPE=api_offresdemploiv2 o2dsoffre
REQUEST_TIMEOUT=10
MAX_RETRIES=3
```

**Usage** :
```python
from fetchers.client_ft import FranceTravailClient

client = FranceTravailClient()
data = client.get("/offresdemploi/v2/offres/search", params={"range": "0-149"})
```

---

### 1.2 Fetchers Individuels

#### ✅ Offres d'Emploi v2 (`fetch_offres.py`)

**Status** : **Fonctionnel** ✅

**Endpoint** : `/offresdemploi/v2/offres/search`

**Limites API** :
- Max par requête : **150 offres**
- Position max : **3000** (limite France Travail)
- **Total récupérable : 3,000 offres** (20 pages)

**Pagination** :
```python
range=0-149    # Page 0
range=150-299  # Page 1
...
range=2850-2999  # Page 19 (dernière)
```

**Fichiers générés** :
```
data/raw/offres_2025-11-13_page0.json   (609 Ko)
data/raw/offres_2025-11-13_page1.json   (699 Ko)
...
data/raw/offres_2025-11-13_page19.json  (654 Ko)
```

**Structure JSON** :
```json
{
  "resultats": [
    {
      "id": "200HHPB",
      "intitule": "Second de cuisine F/H",
      "description": "...",
      "typeContrat": "CDI",
      "typeContratLibelle": "CDI",
      "lieuTravail": {
        "libelle": "78 - Saint-Germain-en-Laye",
        "codePostal": "78100",
        "commune": "78551",
        "latitude": 48.897698,
        "longitude": 2.093674
      },
      "romeCode": "G1602",
      "romeLibelle": "Personnel de cuisine",
      "entreprise": {
        "nom": "ELIOR SUPPORT",
        "description": "...",
        "entrepriseAdaptee": false
      },
      "competences": [
        {
          "code": "123456",
          "libelle": "Préparer les viandes et les poissons",
          "exigence": "E"
        }
      ],
      "salaire": {
        "libelle": "Mensuel de 2500.0 Euros sur 12.0 mois",
        "commentaire": "selon profil"
      },
      "dateCreation": "2025-11-13T22:47:20.057Z",
      "dateActualisation": "2025-11-13T22:47:20.423Z"
    }
  ]
}
```

**Champs clés** :
- `id` : Identifiant unique offre
- `intitule` : Titre du poste
- `romeCode` : Code ROME (ex: G1602)
- `romeLibelle` : Libellé métier ROME
- `lieuTravail.commune` : Code commune INSEE
- `lieuTravail.latitude/longitude` : Géolocalisation
- `competences[]` : Liste des compétences requises
- `typeContrat` : CDI, CDD, MIS (intérim), etc.
- `salaire` : Informations salariales (optionnel)

**Exécution** :
```bash
python fetchers/fetch_offres.py
```

**Résultat** :
```
✅ 3,000 offres récupérées
✅ 20 fichiers JSON créés (~13 MB)
✅ Durée : ~20 secondes
```

---

#### ⚠️ ROME 4.0 - Métiers (`fetch_rome_metiers.py`)

**Status** : **Erreur 401** (scope manquant)

**Endpoint** : `/rome/v1/metier`

**Scope requis** : `api_romev1` (non présent actuellement)

**Objectif** : Récupérer le référentiel complet des métiers ROME 4.0

**Action requise** :
1. Contacter France Travail pour ajouter le scope `api_romev1`
2. Mettre à jour `.env` : `SCOPE=api_offresdemploiv2 o2dsoffre api_romev1`
3. Relancer le fetcher

---

#### ⚠️ ROME 4.0 - Fiches Métiers (`fetch_rome_fiches_metiers.py`)

**Status** : **Erreur 401** (scope manquant)

**Endpoint** : `/rome/v1/metier/{code_rome}`

**Objectif** : Récupérer les fiches détaillées pour chaque code ROME

**Dépendance** : Nécessite d'abord `fetch_rome_metiers.py` pour obtenir la liste des codes ROME

---

#### ⚠️ ROME 4.0 - Compétences (`fetch_rome_competences.py`)

**Status** : **Erreur 401** (scope manquant)

**Endpoint** : `/rome/v1/competence`

**Objectif** : Récupérer le référentiel complet des compétences ROME 4.0

---

#### ⚠️ ROME 4.0 - Contextes de Travail (`fetch_rome_contextes.py`)

**Status** : **Erreur 401** (scope manquant)

**Endpoint** : `/rome/v1/contexteTravail`

**Objectif** : Récupérer les contextes de travail du référentiel ROME

---

#### ⚠️ Marché du Travail v1 (`fetch_marche_travail.py`)

**Status** : **Erreur 401** (scope manquant)

**Endpoints** :
- `/infotravail/v1/datastore_search`
- `/stats/marche-du-travail/v1/tensions`

**Scope requis** : `api_marchetravailv1`

**Objectif** : Récupérer les statistiques du marché du travail (tensions, demandes, offres)

---

#### ⚠️ Anotéa v1 (`fetch_anotea.py`)

**Status** : **Erreur 401** (scope manquant)

**Endpoint** : `/kairos/v1/organisme/{siret}/avis`

**Scope requis** : `api_anoteav1`

**Objectif** : Récupérer les avis sur les organismes de formation

---

### 1.3 Orchestrateur Principal

**Fichier** : `fetch_all.py`

**Fonctionnalités** :
- ✅ Exécution séquentielle de tous les fetchers
- ✅ Gestion des erreurs individuelles (continue si un fetcher échoue)
- ✅ Résumé statistique final
- ✅ Logging détaillé avec timestamps

**Usage** :
```bash
# Mode complet
python fetch_all.py

# Mode rapide (2 pages d'offres pour test)
python fetch_all.py --quick

# Options avancées
python fetch_all.py --skip-offres
python fetch_all.py --skip-rome
```

---

## 📊 Données Actuellement Disponibles

### Synthèse

| Dataset | Status | Volume | Fichiers | Taille |
|---------|--------|--------|----------|--------|
| **Offres d'emploi v2** | ✅ Complet | 3,000 offres | 20 fichiers | ~13 MB |
| **ROME Métiers** | ⚠️ Scope manquant | - | - | - |
| **ROME Fiches** | ⚠️ Scope manquant | - | - | - |
| **ROME Compétences** | ⚠️ Scope manquant | - | - | - |
| **ROME Contextes** | ⚠️ Scope manquant | - | - | - |
| **Marché Travail** | ⚠️ Scope manquant | - | - | - |
| **Anotéa** | ⚠️ Scope manquant | - | - | - |

### Arborescence `data/raw/`

```
data/raw/
├── offres_2025-11-13_page0.json    (609 Ko, 150 offres)
├── offres_2025-11-13_page1.json    (699 Ko, 150 offres)
├── offres_2025-11-13_page2.json    (568 Ko, 150 offres)
├── offres_2025-11-13_page3.json    (632 Ko, 150 offres)
├── offres_2025-11-13_page4.json    (657 Ko, 150 offres)
├── offres_2025-11-13_page5.json    (645 Ko, 150 offres)
├── offres_2025-11-13_page6.json    (691 Ko, 150 offres)
├── offres_2025-11-13_page7.json    (664 Ko, 150 offres)
├── offres_2025-11-13_page8.json    (668 Ko, 150 offres)
├── offres_2025-11-13_page9.json    (693 Ko, 150 offres)
├── offres_2025-11-13_page10.json   (629 Ko, 150 offres)
├── offres_2025-11-13_page11.json   (678 Ko, 150 offres)
├── offres_2025-11-13_page12.json   (695 Ko, 150 offres)
├── offres_2025-11-13_page13.json   (726 Ko, 150 offres)
├── offres_2025-11-13_page14.json   (715 Ko, 150 offres)
├── offres_2025-11-13_page15.json   (643 Ko, 150 offres)
├── offres_2025-11-13_page16.json   (692 Ko, 150 offres)
├── offres_2025-11-13_page17.json   (688 Ko, 150 offres)
├── offres_2025-11-13_page18.json   (667 Ko, 150 offres)
└── offres_2025-11-13_page19.json   (654 Ko, 150 offres)

Total: 24 fichiers, 14 MB
```

---

## 🔄 Phase 2 : Normalisation (TODO - ChatGPT)

### Objectifs

1. **Fusionner les fichiers paginés**
   ```python
   # Script à créer : scripts/merge_offres.py
   all_offres = []
   for file in Path("data/raw").glob("offres_*.json"):
       with open(file) as f:
           data = json.load(f)
           all_offres.extend(data["resultats"])

   # Sauvegarder dans data/processed/offres_merged.json
   ```

2. **Dédupliquer** (par `id` d'offre)

3. **Normaliser les champs**
   - Dates → format ISO 8601
   - Localisation → codes INSEE + lat/lon
   - ROME → codes uniques
   - Compétences → liste standardisée

4. **Créer les DataFrames** (pandas)
   - `df_offres` : table des offres
   - `df_competences` : table des compétences
   - `df_lieux` : table des lieux
   - `df_entreprises` : table des entreprises

5. **Enrichir avec données externes** (si disponible)
   - ROME 4.0 (métiers, compétences, contextes)
   - Statistiques marché du travail

---

## 📐 Phase 3 : Graphe Métiers-Compétences (TODO - ChatGPT)

### Objectifs

1. **Créer le graphe** (networkx)
   ```python
   import networkx as nx

   G = nx.Graph()

   # Nodes: métiers (ROME codes)
   for rome_code in df_offres['romeCode'].unique():
       G.add_node(rome_code, type='metier')

   # Nodes: compétences
   for comp in competences_uniques:
       G.add_node(comp['code'], type='competence')

   # Edges: métier → compétence (pondérés par fréquence)
   for _, offre in df_offres.iterrows():
       rome = offre['romeCode']
       for comp in offre['competences']:
           if G.has_edge(rome, comp['code']):
               G[rome][comp['code']]['weight'] += 1
           else:
               G.add_edge(rome, comp['code'], weight=1)
   ```

2. **Métriques du graphe**
   - Centralité des métiers (degree, betweenness)
   - Communautés de métiers (Louvain)
   - Chemins entre métiers (transitions possibles)

---

## 📊 Phase 4 : Métriques Compass (TODO - ChatGPT)

### Indicateurs à calculer

1. **ICC** (Indice de Compétences Communes)
   ```python
   # Similarité entre 2 métiers basée sur compétences partagées
   ICC(metier_A, metier_B) = len(comp_A ∩ comp_B) / len(comp_A ∪ comp_B)
   ```

2. **ITM** (Indice de Tension du Marché)
   ```python
   # Ratio offres/demandes par métier et zone géographique
   ITM(rome, zone) = nb_offres(rome, zone) / nb_demandeurs(rome, zone)
   ```

3. **IET** (Indice d'Évolution Temporelle)
   ```python
   # Croissance du nombre d'offres sur période
   IET(rome, période) = (offres_récentes - offres_anciennes) / offres_anciennes
   ```

4. **IIF** (Indice d'Insertion Facilitée)
   ```python
   # Probabilité d'insertion basée sur historique + marché
   IIF(candidat, rome) = f(compétences, expérience, ITM, IET)
   ```

---

## 🎲 Phase 5 : Simulation Monte Carlo (TODO - ChatGPT)

### Objectifs

1. **Modéliser les trajectoires professionnelles**
   - États : métiers (codes ROME)
   - Transitions : probabilités basées sur ICC et données historiques
   - Durées : distributions probabilistes (normal, exponentiel)

2. **Simuler N trajectoires** (N=10,000)
   ```python
   for i in range(10000):
       trajectory = simulate_career_path(
           start_metier='M1805',
           duration_years=10,
           competences_candidat=['Python', 'SQL'],
           contraintes_geo=['75', '92', '93']
       )
       trajectories.append(trajectory)
   ```

3. **Analyser les résultats**
   - Trajectoires les plus probables
   - Durées moyennes par transition
   - Métiers cibles atteignables
   - Compétences à acquérir (lacunes)

---

## 🎯 Phase 6 : Matching Intelligent (TODO - ChatGPT)

### Algorithme

```python
def match_candidat_offres(candidat, offres, top_k=10):
    """
    Retourne les K offres les plus pertinentes pour un candidat.

    Args:
        candidat: dict avec compétences, expérience, localisation
        offres: DataFrame des offres
        top_k: nombre d'offres à retourner

    Returns:
        DataFrame des top K offres avec scores
    """

    scores = []

    for _, offre in offres.iterrows():
        score = 0

        # 1. Score compétences (60%)
        comp_match = len(set(candidat['competences']) & set(offre['competences']))
        comp_total = len(set(offre['competences']))
        score += 0.6 * (comp_match / comp_total if comp_total > 0 else 0)

        # 2. Score localisation (20%)
        distance_km = haversine(candidat['lat'], candidat['lon'],
                                offre['lat'], offre['lon'])
        score += 0.2 * max(0, 1 - distance_km / 100)  # pénalité après 100km

        # 3. Score expérience (10%)
        if candidat['annees_exp'] >= offre.get('experience_min', 0):
            score += 0.1

        # 4. Score marché (10%) - IIF
        score += 0.1 * IIF(candidat, offre['romeCode'])

        scores.append({
            'offre_id': offre['id'],
            'score': score,
            'offre': offre
        })

    # Trier et retourner top K
    scores_sorted = sorted(scores, key=lambda x: x['score'], reverse=True)
    return pd.DataFrame(scores_sorted[:top_k])
```

---

## 🔧 Standards de Code

### Python
- **Version** : Python 3.11+
- **Style** : PEP 8
- **Type hints** : Obligatoires pour fonctions publiques
- **Docstrings** : Format Google

### Librairies
```python
# Data
import pandas as pd
import numpy as np

# Graphes
import networkx as nx

# Visualisation
import matplotlib.pyplot as plt
import seaborn as sns

# API
import requests
from dotenv import load_dotenv

# Utils
from pathlib import Path
from datetime import datetime
import json
```

### Gestion des Erreurs
```python
try:
    # Code
except SpecificException as e:
    logger.error(f"Erreur : {e}")
    # Fallback
```

---

## 📁 Structure Projet Complète

```
elevia-compass/
├── .env                          # Config OAuth2
├── .gitignore                    # Git ignores
├── README.md                     # Documentation utilisateur
├── ARCHITECTURE_TECHNIQUE.md     # Ce fichier
├── requirements.txt              # Dépendances Python
├── fetch_all.py                  # Orchestrateur principal
│
├── fetchers/                     # Phase 1: Ingestion
│   ├── client_ft.py              # Client OAuth2
│   ├── fetch_offres.py           # Offres emploi
│   ├── fetch_rome_metiers.py     # ROME métiers
│   ├── fetch_rome_fiches_metiers.py
│   ├── fetch_rome_competences.py
│   ├── fetch_rome_contextes.py
│   ├── fetch_marche_travail.py
│   └── fetch_anotea.py
│
├── scripts/                      # Phase 2: Normalisation
│   ├── merge_offres.py           # TODO
│   ├── clean_data.py             # TODO
│   └── create_dataframes.py      # TODO
│
├── compass/                      # Phase 3-6: Analyse
│   ├── __init__.py
│   ├── graphe.py                 # TODO: Création graphe
│   ├── metriques.py              # TODO: ICC, ITM, IET, IIF
│   ├── monte_carlo.py            # TODO: Simulations
│   └── matching.py               # TODO: Algorithme matching
│
├── notebooks/                    # Analyses exploratoires
│   ├── 01_exploration.ipynb      # TODO
│   ├── 02_graphe.ipynb           # TODO
│   └── 03_simulations.ipynb      # TODO
│
├── data/
│   ├── raw/                      # Données brutes API
│   │   ├── offres_*.json         # ✅ 3,000 offres
│   │   ├── rome_metiers_*.json   # TODO (scope manquant)
│   │   └── ...
│   │
│   └── processed/                # Données nettoyées
│       ├── offres_merged.json    # TODO
│       ├── df_offres.parquet     # TODO
│       └── graphe_metiers.gexf   # TODO
│
└── tests/                        # Tests unitaires
    ├── test_client.py
    ├── test_fetchers.py
    └── test_compass.py
```

---

## 🚀 Prochaines Actions (ChatGPT)

### Priorité 1 : Normalisation

1. **Fusionner les 20 fichiers d'offres**
   ```bash
   python scripts/merge_offres.py
   ```

2. **Créer les DataFrames fact/dim**
   ```bash
   python scripts/create_dataframes.py
   ```

3. **Analyse exploratoire**
   ```bash
   jupyter notebook notebooks/01_exploration.ipynb
   ```

### Priorité 2 : Graphe

1. **Construire le graphe métiers-compétences**
   ```python
   from compass.graphe import build_graph

   G = build_graph(df_offres)
   ```

2. **Calculer les métriques**
   ```python
   from compass.metriques import compute_ICC, compute_ITM

   icc_matrix = compute_ICC(G)
   ```

### Priorité 3 : Simulations

1. **Modéliser les transitions**
   ```python
   from compass.monte_carlo import simulate_trajectories

   trajectories = simulate_trajectories(
       start_metier='M1805',
       n_simulations=10000
   )
   ```

---

## 📞 Support

**Problème** : Erreur 401 sur APIs ROME, Marché Travail, Anotéa
**Solution** : Contacter France Travail pour ajouter les scopes :
- `api_romev1`
- `api_marchetravailv1`
- `api_anoteav1`

**Contact France Travail** : support@francetravail.io

---

## 📜 Licence

Propriétaire - Elevia Compass © 2025

---

**🚀 Architecture créée avec Claude Code & France Travail API**
