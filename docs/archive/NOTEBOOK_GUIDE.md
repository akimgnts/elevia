# 🧭 Guide d'utilisation - Notebook Elevia Compass

Guide complet pour exécuter et exploiter le notebook d'analyse Elevia Compass.

---

## 📋 Vue d'ensemble

Le notebook `analysis_elevia_compass.ipynb` réalise :

1. **Chargement des données** - Import des 3,150 offres d'emploi France Travail
2. **Construction des tables analytiques** - fact_offers, dim_location, dim_job, dim_skill, bridges
3. **EDA (Exploratory Data Analysis)** - Distributions, visualisations, insights
4. **Graphe Compass V0** - Réseau bipartite jobs-skills avec NetworkX
5. **Préparation Monte Carlo** - Structure pour simulations de trajectoires

---

## 🚀 Installation & Setup

### 1. Créer un environnement virtuel (recommandé)

```bash
cd /Users/akimguentas/Documents/elevia-compass

# Créer l'environnement
python3 -m venv .venv

# Activer l'environnement
source .venv/bin/activate  # macOS/Linux
# ou
.venv\Scripts\activate  # Windows
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

**Dépendances installées :**
- `pandas`, `numpy`, `pyarrow` - Data processing
- `networkx` - Graph analysis
- `matplotlib`, `seaborn` - Visualisations
- `jupyter`, `notebook` - Notebook environment

### 3. Vérifier les données brutes

Assurez-vous que les offres d'emploi sont présentes :

```bash
ls -lh data/raw/offres_*.json | wc -l
# Doit afficher 21-24 fichiers
```

---

## 📊 Exécution du Notebook

### Lancer Jupyter Notebook

```bash
jupyter notebook analysis_elevia_compass.ipynb
```

Le notebook s'ouvrira dans votre navigateur à `http://localhost:8888`.

### Exécution cellule par cellule

**Recommandé pour la première fois :**
1. Exécuter les cellules séquentiellement (`Shift + Enter`)
2. Vérifier les outputs après chaque section
3. Inspecter les DataFrames générés

**Sections du notebook :**

| Section | Description | Outputs clés |
|---------|-------------|--------------|
| **0. Configuration** | Import librairies, définition chemins | Confirmation chemins |
| **1. Chargement RAW** | Load 3,150 offres JSON | `raw_offers` list |
| **2. DataFrames analytiques** | Construction fact/dim tables | `fact_offers`, `dim_location`, `dim_job`, `dim_skill` |
| **2.3 Sauvegarde** | Export CSV + Parquet | Fichiers dans `data/processed/` |
| **3. EDA** | Visualisations & distributions | Graphiques PNG dans `reports/figures/` |
| **4. Graphe Compass** | Construction réseau NetworkX | `G_compass_v0.gpickle` |
| **4.1 Métriques** | Centralité, degrés | `graph_metrics.csv` |
| **5. Monte Carlo** | Structure simulations | `transition_matrix_baseline.csv` |

---

## 📁 Structure des données générées

Après exécution complète :

```
elevia-compass/
├── data/
│   ├── raw/                          # Données brutes (21 fichiers JSON)
│   │   └── offres_2025-11-13_page*.json
│   ├── processed/                    # Tables normalisées
│   │   ├── fact_offers.csv
│   │   ├── fact_offers.parquet
│   │   ├── dim_location.csv
│   │   ├── dim_job.csv
│   │   ├── dim_skill.csv
│   │   ├── bridge_offer_skill.csv
│   │   ├── graph_metrics.csv
│   │   └── transition_matrix_baseline.csv
│   └── intermediate/                 # Objets Python sérialisés
│       └── G_compass_v0.gpickle
└── reports/
    └── figures/                      # Visualisations PNG
        ├── top_rome_code.png
        ├── top_cities.png
        ├── contract_type_distribution.png
        ├── salary_min_distribution.png
        └── salary_max_distribution.png
```

---

## 🔍 Analyses disponibles

### 1. fact_offers - Table principale

**Colonnes principales :**
- `offer_id` - Identifiant unique offre
- `title` - Intitulé du poste
- `company_name` - Nom entreprise
- `contract_type` - Type contrat (CDI, CDD, etc.)
- `date_creation` - Date publication
- `city`, `department`, `postal_code` - Localisation
- `rome_code`, `rome_label` - Code métier ROME
- `salary_min`, `salary_max` - Fourchettes salariales
- `skills` - Liste compétences (placeholder)

**Requêtes SQL-like avec pandas :**

```python
# Top 10 métiers
fact_offers['rome_code'].value_counts().head(10)

# Offres CDI à Paris
fact_offers[
    (fact_offers['contract_type'] == 'CDI') &
    (fact_offers['city'] == 'Paris')
]

# Salaire moyen par métier
fact_offers.groupby('rome_code')['salary_min'].mean().sort_values(ascending=False)
```

### 2. Graphe Compass V0

**Chargement du graphe :**

```python
import networkx as nx
from pathlib import Path

G = nx.read_gpickle("data/intermediate/G_compass_v0.gpickle")

print(f"Nœuds: {G.number_of_nodes()}")
print(f"Arêtes: {G.number_of_edges()}")

# Jobs les plus connectés
job_nodes = [n for n, d in G.nodes(data=True) if d['node_type'] == 'job']
job_degrees = [(n, G.degree(n)) for n in job_nodes]
sorted(job_degrees, key=lambda x: x[1], reverse=True)[:10]
```

### 3. Visualisations interactives

**Exemple : Distribution géographique**

```python
import matplotlib.pyplot as plt
import seaborn as sns

# Top départements
dept_counts = fact_offers['department'].value_counts().head(15)

plt.figure(figsize=(12, 6))
sns.barplot(x=dept_counts.values, y=dept_counts.index)
plt.title("Top 15 départements - Volume d'offres")
plt.xlabel("Nombre d'offres")
plt.tight_layout()
plt.show()
```

---

## 🔧 Personnalisation & Extensions

### Adapter les chemins

Si le notebook est dans un autre répertoire :

```python
# Cellule 0 - Configuration
PROJECT_ROOT = Path("/votre/chemin/elevia-compass").resolve()
```

### Ajouter de nouvelles métriques

**Exemple : Taux de salaire renseigné**

```python
# Nouvelle cellule après section 3
salary_info_rate = (
    fact_offers['salary_min'].notna().sum() / len(fact_offers) * 100
)
print(f"Taux d'offres avec salaire renseigné : {salary_info_rate:.1f}%")
```

### Enrichir le graphe

Quand les données ROME seront disponibles :

```python
# Remplacer dim_job placeholder
dim_job_rome = pd.read_csv("data/raw/rome_metiers_2025-11-13.csv")

# Enrichir les nœuds jobs
for _, row in dim_job_rome.iterrows():
    node_id = f"job::{row['code_rome']}"
    if G.has_node(node_id):
        G.nodes[node_id]['rome_domain'] = row['domaine']
        G.nodes[node_id]['rome_category'] = row['categorie']
```

---

## 📈 Prochaines étapes

### Phase 2 : Intégration ROME complète

Une fois les scopes API obtenus :

1. **Remplacer `dim_job` placeholder**
   ```python
   # Charger ROME métiers
   rome_metiers = pd.read_json("data/raw/rome_metiers_YYYY-MM-DD.json")
   dim_job = build_dim_job_from_rome(rome_metiers)
   ```

2. **Remplacer `dim_skill` placeholder**
   ```python
   rome_competences = pd.read_json("data/raw/rome_competences_YYYY-MM-DD.json")
   dim_skill = build_dim_skill_from_rome(rome_competences)
   ```

3. **Bridge job-skill réel**
   ```python
   # À partir des fiches métiers ROME
   rome_fiches = pd.read_json("data/raw/rome_fiches_metiers_YYYY-MM-DD.json")
   bridge_job_skill = extract_job_skill_from_fiches(rome_fiches)
   ```

### Phase 3 : Métriques Compass

Implémenter les 4 métriques dans de nouvelles cellules :

- **ICC** (Indice de Compatibilité des Compétences)
- **ITM** (Indice de Tension du Marché)
- **IET** (Indice d'Évolution Temporelle)
- **IIF** (Indice d'Impact sur les Formations)

### Phase 4 : Monte Carlo avancé

```python
def build_real_transition_matrix(G_compass, dim_job):
    """
    Matrice basée sur :
    - Similarité de compétences (Jaccard)
    - Proximité graphe (shortest path)
    - Patterns historiques
    """
    # Implementation à venir
```

---

## 🐛 Troubleshooting

### Erreur : Module not found

```bash
# Vérifier l'environnement virtuel est activé
which python
# Doit pointer vers .venv/bin/python

# Réinstaller les dépendances
pip install -r requirements.txt --upgrade
```

### Erreur : FileNotFoundError data/raw

```bash
# Vérifier que les données sont présentes
ls data/raw/offres_*.json

# Si manquant, relancer le fetcher
python fetchers/fetch_offres.py
```

### Graphe vide (0 nœuds, 0 arêtes)

Cela signifie que les offres n'ont pas de compétences renseignées.
C'est **normal** avec les données actuelles (API Offres v2 ne retourne pas de compétences détaillées).

**Solution :** Attendre l'intégration des données ROME Compétences.

### Jupyter kernel crash

```bash
# Augmenter la mémoire disponible
export PYDEVD_WARN_SLOW_RESOLVE_TIMEOUT=2
jupyter notebook --NotebookApp.max_buffer_size=1000000000
```

---

## 📚 Ressources

- **Documentation pandas** : https://pandas.pydata.org/docs/
- **NetworkX Tutorial** : https://networkx.org/documentation/stable/tutorial.html
- **Matplotlib Gallery** : https://matplotlib.org/stable/gallery/index.html
- **API France Travail** : https://francetravail.io/data

---

## ✅ Checklist finale

Avant de passer à la phase suivante :

- [ ] Toutes les cellules s'exécutent sans erreur
- [ ] `fact_offers` contient 3,000+ lignes
- [ ] Fichiers CSV/Parquet créés dans `data/processed/`
- [ ] Visualisations générées dans `reports/figures/`
- [ ] Graphe `G_compass_v0.gpickle` sauvegardé
- [ ] `graph_metrics.csv` exporté avec degree centrality
- [ ] Matrice de transition baseline créée

**Ce notebook constitue la fondation Phase 2 du pipeline Elevia Compass.**

---

**🔥 Made with Claude Code - Elevia Compass © 2025**
