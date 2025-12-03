# 🔥 Elevia Compass - Pipeline d'Ingestion France Travail

Pipeline complet d'ingestion multi-API France Travail pour le projet **Elevia Compass**.

## 📋 Vue d'ensemble

Ce pipeline récupère automatiquement toutes les données disponibles via l'API France Travail :

- ✅ **Offres d'emploi v2** - Pagination automatique (max 3150 offres)
- ⚠️ **ROME 4.0 - Métiers** - Référentiel complet des métiers
- ⚠️ **ROME 4.0 - Fiches métiers** - Fiches détaillées par code ROME
- ⚠️ **ROME 4.0 - Compétences** - Référentiel des compétences
- ⚠️ **ROME 4.0 - Contextes de travail** - Contextes professionnels
- ⚠️ **Marché du travail v1** - Statistiques et tensions
- ⚠️ **Anotéa v1** - Avis sur les formations

> **Note** : Les APIs ROME, Marché du Travail et Anotéa nécessitent des scopes supplémentaires. Seule l'API Offres d'emploi est fonctionnelle.

---

## 🚀 Installation

### 1. Prérequis

```bash
Python 3.11+
pip
virtualenv (optionnel)
```

### 2. Configuration

Créer un fichier `.env` à la racine :

```env
CLIENT_ID=PAR_elevia1_edccae836bbd05b5bb1eb4de5f91a9c10866abbf0a15dd89a90d96cc8f78b94d
CLIENT_SECRET=<votre_secret>
TOKEN_URL=https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire
BASE_URL=https://api.francetravail.io//partenaire
SCOPE=api_offresdemploiv2 o2dsoffre
REQUEST_TIMEOUT=10
MAX_RETRIES=3
```

### 3. Installation des dépendances

```bash
pip install requests python-dotenv
```

---

## 📁 Structure du Projet

```
elevia-compass/
├── fetch_all.py                    # 🎯 Script principal
├── .env                            # Configuration
├── fetchers/                       # 📦 Modules
│   ├── client_ft.py                #    Client OAuth2
│   ├── fetch_offres.py             #    Offres d'emploi
│   ├── fetch_rome_metiers.py       #    Métiers ROME
│   ├── fetch_rome_fiches_metiers.py#    Fiches métiers
│   ├── fetch_rome_competences.py   #    Compétences
│   ├── fetch_rome_contextes.py     #    Contextes travail
│   ├── fetch_marche_travail.py     #    Marché du travail
│   └── fetch_anotea.py             #    Avis formations
└── data/
    └── raw/                        # 💾 Données JSON
        ├── offres_2025-11-13_page0.json
        └── ...
```

---

## 🎯 Usage

### Mode complet

```bash
python fetch_all.py
```

### Mode rapide (test)

```bash
python fetch_all.py --quick
```

### Fetchers individuels

```bash
python fetchers/fetch_offres.py
python fetchers/fetch_rome_metiers.py
```

---

## 📊 Résultats

### Données récupérées

| API | Statut | Volume | Fichiers |
|-----|--------|--------|----------|
| **Offres d'emploi** | ✅ Fonctionnel | 3,150 offres | 21 fichiers (~14 MB) |
| **ROME Métiers** | ⚠️ Scope manquant | - | - |
| **ROME Fiches** | ⚠️ Scope manquant | - | - |

---

## 📊 Analyse des Données

### Notebook Jupyter

Un notebook complet d'analyse est disponible : [analysis_elevia_compass.ipynb](analysis_elevia_compass.ipynb)

**Fonctionnalités :**
- Construction des tables analytiques (fact_offers, dim_location, dim_job, dim_skill)
- EDA (Exploratory Data Analysis) avec visualisations
- Graphe Compass V0 (NetworkX) - réseau jobs-skills
- Préparation structure Monte Carlo pour simulations de trajectoires

**Installation :**

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer Jupyter
jupyter notebook analysis_elevia_compass.ipynb
```

**Guide complet :** Voir [NOTEBOOK_GUIDE.md](NOTEBOOK_GUIDE.md)

---

## 📄 Licence

Propriétaire - Elevia Compass © 2025

---

**⚡ Made with Claude Code & France Travail API**
