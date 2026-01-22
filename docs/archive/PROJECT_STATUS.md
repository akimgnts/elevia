# 🔥 ELEVIA COMPASS - État du Projet

**Date:** 13 Novembre 2025
**Phase:** Phase 2 - Analyse & Modélisation (READY)
**Statut:** ✅ Fondation complète + Notebook d'analyse opérationnel

---

## 📊 Vue d'ensemble

Elevia Compass est un moteur de trajectoires professionnelles basé sur :
- Données France Travail (API Offres d'emploi v2)
- Référentiel ROME 4.0 (en attente de scopes OAuth)
- Graphe de carrières (NetworkX)
- Simulations Monte Carlo

---

## ✅ Phase 1 : Ingestion de Données - COMPLÈTE

### Infrastructure

| Composant | Fichier | Statut |
|-----------|---------|--------|
| **Client OAuth2** | `fetchers/client_ft.py` | ✅ Production-ready |
| **Fetcher Offres** | `fetchers/fetch_offres.py` | ✅ Fonctionnel (3,150 offres) |
| **Fetcher ROME Métiers** | `fetchers/fetch_rome_metiers.py` | ⚠️ Scope manquant |
| **Fetcher ROME Fiches** | `fetchers/fetch_rome_fiches_metiers.py` | ⚠️ Scope manquant |
| **Fetcher ROME Compétences** | `fetchers/fetch_rome_competences.py` | ⚠️ Scope manquant |
| **Fetcher ROME Contextes** | `fetchers/fetch_rome_contextes.py` | ⚠️ Scope manquant |
| **Fetcher Marché Travail** | `fetchers/fetch_marche_travail.py` | ⚠️ Scope manquant |
| **Fetcher Anotéa** | `fetchers/fetch_anotea.py` | ⚠️ Scope manquant |
| **Orchestrateur** | `fetch_all.py` | ✅ Prêt |

### Données Récupérées

```
data/raw/
├── offres_2025-11-13_page0.json  (150 offres)
├── offres_2025-11-13_page1.json  (150 offres)
├── ...
└── offres_2025-11-13_page20.json (150 offres)

Total : 21 fichiers, ~14 MB, 3,150 offres
```

### Statistiques Clés

- **Volume total:** 3,150 offres d'emploi
- **Types de contrat:** CDI (43.6%), MIS (37.4%), CDD (17.1%)
- **Top métiers (ROME):**
  - K1304 - Services domestiques (91 offres, 2.9%)
  - K1311 - Assistance auprès d'enfants (79 offres, 2.5%)
  - N4101 - Conduite de transport de marchandises (64 offres, 2.0%)
- **Top départements:** 33-Gironde (117), 59-Nord (105), 44-Loire-Atlantique (105)
- **Top entreprises:** PROMAN (6.7%), ADECCO (4.2%), CRIT (3.6%)

---

## ✅ Phase 2 : Analyse & Modélisation - READY

### Notebook Jupyter

**Fichier:** `analysis_elevia_compass.ipynb`

**Sections implémentées:**

1. **Configuration & Imports** ✅
   - Pandas, NumPy, NetworkX, Matplotlib
   - Définition des chemins (raw, processed, intermediate, figures)

2. **Chargement & Inspection RAW** ✅
   - `load_all_offers_json()` - Charge les 21 fichiers JSON
   - `inspect_example_structure()` - Validation format

3. **Construction DataFrames Analytiques** ✅
   - `fact_offers` - Table principale (3,150 lignes)
   - `dim_location` - Normalisation lieux
   - `dim_job` - Placeholder métiers ROME
   - `dim_skill` - Placeholder compétences
   - `bridge_offer_skill` - Liens offres-compétences

4. **EDA (Exploratory Data Analysis)** ✅
   - Distributions métiers, villes, contrats
   - Visualisations (barplot, histogrammes)
   - Export PNG dans `reports/figures/`

5. **Graphe Compass V0** ✅
   - `build_compass_graph()` - NetworkX bipartite graph
   - Nœuds: jobs + skills
   - Arêtes: job-skill avec poids
   - Export: `G_compass_v0.gpickle`

6. **Métriques de Graphe** ✅
   - Degree centrality
   - Top hubs (jobs les plus connectés)
   - Export: `graph_metrics.csv`

7. **Préparation Monte Carlo** ✅
   - `build_job_transition_matrix()` - Matrice baseline (identité)
   - `run_monte_carlo()` - Simulations de trajectoires
   - Export: `transition_matrix_baseline.csv`

### Scripts Utilitaires

| Script | Description | Usage |
|--------|-------------|-------|
| `quick_analysis.py` | Analyse rapide CLI | `python3 quick_analysis.py` |
| `fetch_all.py` | Orchestrateur complet | `python fetch_all.py [--quick]` |

### Documentation

| Fichier | Contenu |
|---------|---------|
| `README.md` | Guide utilisateur |
| `ARCHITECTURE_TECHNIQUE.md` | Architecture complète 6 phases |
| `NOTEBOOK_GUIDE.md` | Guide notebook Jupyter |
| `PROJECT_STATUS.md` | État du projet (ce fichier) |

---

## 📦 Outputs Générés

### Tables Normalisées (`data/processed/`)

- `fact_offers.csv` / `.parquet` - Table principale offres
- `dim_location.csv` / `.parquet` - Dimension localisation
- `dim_job.csv` / `.parquet` - Dimension métiers (placeholder)
- `dim_skill.csv` / `.parquet` - Dimension compétences (placeholder)
- `bridge_offer_skill.csv` / `.parquet` - Bridge offres-skills
- `graph_metrics.csv` / `.parquet` - Métriques du graphe
- `transition_matrix_baseline.csv` / `.parquet` - Matrice Monte Carlo

### Graphes (`data/intermediate/`)

- `G_compass_v0.gpickle` - Graphe NetworkX bipartite jobs-skills

### Visualisations (`reports/figures/`)

- `top_rome_code.png` - Top 20 métiers
- `top_cities.png` - Top 20 villes
- `contract_type_distribution.png` - Types de contrat
- `salary_min_distribution.png` - Distribution salaires min
- `salary_max_distribution.png` - Distribution salaires max

---

## 🔜 Prochaines Étapes

### Phase 2bis : Intégration ROME Complète

**Prérequis:** Obtenir les scopes OAuth manquants
- `api_romev1` - Pour métiers, fiches, compétences, contextes
- `api_marchetravailv1` - Pour statistiques marché
- `api_anoteav1` - Pour avis formations

**Actions:**
1. Contacter France Travail pour ajout des scopes
2. Relancer `python fetch_all.py` pour récupérer données ROME
3. Remplacer placeholders dans le notebook :
   ```python
   # Au lieu de build_dim_job_placeholder()
   dim_job = build_dim_job_from_rome(rome_metiers_data)
   dim_skill = build_dim_skill_from_rome(rome_competences_data)
   ```

### Phase 3 : Graph de Carrière

**Objectif:** Enrichir le graphe avec relations métier-métier

**Tâches:**
- [ ] Ajouter nœuds "activités" à partir des fiches ROME
- [ ] Créer arêtes job-job basées sur similarité compétences
- [ ] Implémenter mesures de proximité (Jaccard, cosine)
- [ ] Visualiser le graphe avec Plotly/Cytoscape

**Fichier:** Nouvelle section dans `analysis_elevia_compass.ipynb`

### Phase 4 : Métriques Compass

**Objectif:** Implémenter les 4 indicateurs clés

**Métriques à développer:**

1. **ICC - Indice de Compatibilité des Compétences**
   ```python
   def compute_icc(job_source, job_target, G_compass):
       # Jaccard similarity entre skills requis
       pass
   ```

2. **ITM - Indice de Tension du Marché**
   ```python
   def compute_itm(job_code, marche_travail_data):
       # Ratio offres/demandes
       pass
   ```

3. **IET - Indice d'Évolution Temporelle**
   ```python
   def compute_iet(job_code, historical_data):
       # Taux de croissance des offres
       pass
   ```

4. **IIF - Indice d'Impact sur les Formations**
   ```python
   def compute_iif(job_target, anotea_data):
       # Accessibilité via formations
       pass
   ```

### Phase 5 : Monte Carlo Avancé

**Objectif:** Simulations réalistes de trajectoires

**Améliorations:**
- [ ] Matrice de transition basée sur ICC + ITM
- [ ] Contraintes temporelles (durée transitions)
- [ ] Contraintes géographiques (mobilité)
- [ ] Prise en compte formations nécessaires
- [ ] Visualisation trajectoires avec Sankey diagram

### Phase 6 : Algorithme de Matching

**Objectif:** Recommandations personnalisées

**Inputs utilisateur:**
- Profil actuel (job, skills, localisation)
- Préférences (salaire, contrat, mobilité)
- Horizon temporel (court/moyen/long terme)

**Outputs:**
- Top N métiers cibles recommandés
- Parcours de transition optimaux
- Formations à suivre
- Score de faisabilité par parcours

---

## 🐛 Limitations Connues

### API France Travail

1. **Scopes manquants** - ROME/Marché/Anotéa retournent 401
   - **Impact:** Placeholders utilisés pour dim_job et dim_skill
   - **Solution:** Demander scopes à France Travail

2. **Limite position 3000** - API Offres v2
   - **Impact:** Maximum 3,000 offres récupérables par requête générique
   - **Solution:** Utiliser filtres (localisation, métier) pour cibler

3. **Pas de champ "compétences"** - API Offres v2
   - **Impact:** `bridge_offer_skill` vide actuellement
   - **Solution:** Utiliser ROME Fiches Métiers pour inférer skills par job

### Données

1. **Salaires non renseignés** - 0% des offres ont salary_min/max
   - **Impact:** Impossible d'analyser distributions salariales
   - **Solution:** Enrichir avec données externes (INSEE, APEC)

2. **Localisation incomplète** - Villes souvent en code INSEE
   - **Impact:** Difficulté à mapper géographiquement
   - **Solution:** Référentiel communes (API geo.api.gouv.fr)

---

## 🚀 Quick Start

### Installation

```bash
cd /Users/akimguentas/Documents/elevia-compass

# 1. Installer dépendances
pip install -r requirements.txt

# 2. Vérifier données
python3 quick_analysis.py

# 3. Lancer Jupyter
jupyter notebook analysis_elevia_compass.ipynb
```

### Exécution Fetchers

```bash
# Mode complet (toutes APIs)
python fetch_all.py

# Mode rapide (2 pages offres)
python fetch_all.py --quick

# Fetcher individuel
python fetchers/fetch_offres.py
```

---

## 📚 Ressources

### Documentation Projet

- [README.md](README.md) - Guide principal
- [ARCHITECTURE_TECHNIQUE.md](ARCHITECTURE_TECHNIQUE.md) - Architecture 6 phases
- [NOTEBOOK_GUIDE.md](NOTEBOOK_GUIDE.md) - Guide notebook Jupyter

### APIs & Référentiels

- [France Travail API](https://francetravail.io/data) - Documentation officielle
- [ROME 4.0](https://www.francetravail.fr/employeur/vos-recrutements/le-rome-et-les-fiches-metiers.html) - Référentiel métiers
- [NetworkX](https://networkx.org/documentation/stable/) - Graph analysis
- [Pandas](https://pandas.pydata.org/docs/) - Data manipulation

---

## ✅ Checklist de Validation

### Phase 1 - Ingestion ✅

- [x] Client OAuth2 fonctionnel avec auto-refresh
- [x] 8 fetchers créés (offres + 7 ROME/autres)
- [x] Orchestrateur `fetch_all.py` opérationnel
- [x] 3,150 offres récupérées et validées
- [x] Documentation complète (README, ARCHITECTURE)

### Phase 2 - Analyse ✅

- [x] Notebook Jupyter créé et structuré
- [x] Tables analytiques (fact/dim/bridge) construites
- [x] EDA avec visualisations (5+ graphiques)
- [x] Graphe Compass V0 (NetworkX) sauvegardé
- [x] Métriques de graphe calculées
- [x] Structure Monte Carlo implémentée
- [x] Script `quick_analysis.py` fonctionnel
- [x] Guide notebook (`NOTEBOOK_GUIDE.md`)

### Phase 2bis - ROME ⏳ (En attente scopes)

- [ ] Scopes OAuth obtenus
- [ ] Données ROME récupérées
- [ ] Placeholders remplacés par vraies dims
- [ ] Graphe enrichi avec relations ROME

### Phase 3 - Graph ⏳

- [ ] Nœuds activités ajoutés
- [ ] Arêtes job-job créées
- [ ] Mesures de proximité implémentées
- [ ] Visualisation interactive

### Phase 4 - Métriques ⏳

- [ ] ICC implémenté
- [ ] ITM implémenté
- [ ] IET implémenté
- [ ] IIF implémenté

### Phase 5 - Monte Carlo ⏳

- [ ] Matrice transition réelle
- [ ] Contraintes temporelles/géo
- [ ] Visualisation trajectoires

### Phase 6 - Matching ⏳

- [ ] API input profil utilisateur
- [ ] Algorithme recommandation
- [ ] Scoring parcours
- [ ] Interface utilisateur

---

## 👥 Contributeurs

- **Claude Code** - Ingestion pipeline, Notebook analysis, Documentation
- **Akim Guentas** - Product Owner, Specifications

---

## 📄 Licence

Propriétaire - Elevia Compass © 2025

---

**🔥 Made with Claude Code & France Travail API**
