# 📊 RÉSUMÉ DES ERREURS DU NOTEBOOK - Elevia Compass

**Date**: 25 Novembre 2025
**Notebook**: `analysis_elevia_compass.ipynb`
**Status**: ⚠️ **FONCTIONNE AVEC AVERTISSEMENTS**

---

## ✅ CE QUI FONCTIONNE

### 1. Environnement Python ✅
- **Python**: 3.14 (venv activé dans `.venv/`)
- **Librairies installées**:
  - ✅ `pandas`
  - ✅ `numpy`
  - ✅ `networkx`
  - ✅ `matplotlib` (mais lent à importer)

### 2. Données Disponibles ✅
- **Fichiers d'offres**: 41 fichiers JSON dans `data/raw/`
- **Total d'offres**: ~6,150 offres d'emploi France Travail
- **Structure JSON**: Conforme à l'API Offres d'emploi v2

### 3. Structure des Offres ✅
Champs présents dans les offres :
- ✅ `id` : Identifiant unique (ex: "200HHPB")
- ✅ `intitule` : Titre du poste (ex: "Second de cuisine F/H")
- ✅ `romeCode` : Code ROME (ex: "G1609")
- ✅ `romeLibelle` : Libellé métier ROME
- ✅ `typeContrat` : Type de contrat (CDI, CDD, etc.)
- ✅ `lieuTravail` : Localisation complète
  - `libelle` : Ex: "78 - Saint-Germain-en-Laye"
  - `commune` : Code INSEE (ex: "78551")
  - `latitude` / `longitude` (si disponible)

---

## ⚠️ PROBLÈMES IDENTIFIÉS

### 1. ⚠️ Compétences Manquantes (CRITIQUE pour Compass)

**Problème**:
```json
"competences": []  // ❌ Vide dans la plupart des offres
```

**Impact**:
- Le graphe métiers-compétences sera **incomplet**
- Les fonctions du notebook qui utilisent `competences` vont retourner des résultats vides :
  - `extract_skills_from_offer()` → liste vide
  - `dim_skill` → table vide
  - `bridge_offer_skill` → table vide
  - **Graphe Compass** → arêtes job-skill manquantes

**Pourquoi ?**
D'après l'architecture technique :
- L'API Offres d'emploi v2 **peut** contenir des compétences
- Mais dans la pratique, **très peu d'offres** ont ce champ renseigné
- Les compétences détaillées viennent normalement de l'**API ROME Compétences** (scope manquant)

**Solution**:
1. **Court terme** (sans scope ROME):
   - Parser le champ `description` des offres pour extraire des compétences (NLP)
   - Inférer des compétences à partir du `romeCode` (mapping manuel)
   - Accepter que le graphe soit incomplet

2. **Long terme** (avec scope ROME):
   - Activer le scope `api_romev1` auprès de France Travail
   - Récupérer le référentiel ROME complet
   - Créer `dim_skill` à partir de `/rome/v1/competences`
   - Créer le bridge job-skill à partir de `/rome/v1/fiches-metiers/{code}`

---

### 2. ⚠️ Salaire Souvent Manquant

**Problème**:
```json
"salaire": null  // ou clé manquante
```

**Impact**:
- Les analyses de salaire (`salary_min`, `salary_max`) auront beaucoup de `NaN`
- Les histogrammes de salaires seront peu représentatifs

**Solution**:
- Filtrer les offres avec salaire pour ces analyses
- Indiquer clairement dans les visualisations le % d'offres sans salaire

---

### 3. ⚠️ Matplotlib Lent à Charger

**Problème**:
- L'import `import matplotlib.pyplot as plt` prend 10-15 secondes

**Impact**:
- Le notebook prendra du temps à exécuter les cellules avec visualisation

**Solution**:
- Normal pour matplotlib sur macOS
- Utiliser `%matplotlib inline` dans le notebook
- Pas de correction nécessaire

---

## 🔧 CORRECTIONS À APPORTER AU NOTEBOOK

### Cell id="cell-8" - `extract_skills_from_offer()`

**Problème**: Cette fonction retournera une liste vide pour la majorité des offres.

**Correction recommandée**:
```python
def extract_skills_from_offer(offer: Dict[str, Any]) -> List[str]:
    """
    Extrait une liste d'identifiants ou labels de compétences depuis l'offre.
    ⚠️ ATTENTION: Très peu d'offres ont ce champ renseigné.
    """
    competences = offer.get("competences", [])
    skills = []

    if isinstance(competences, list):
        for c in competences:
            if isinstance(c, dict):
                skill_id = c.get("code") or c.get("libelle")
                if skill_id:
                    skills.append(str(skill_id).strip())
            elif isinstance(c, str):
                skills.append(c.strip())

    # ⚠️ Si vide, on pourrait extraire depuis la description (TODO)
    # if not skills and "description" in offer:
    #     skills = extract_skills_from_description(offer["description"])

    return skills
```

---

### Cell id="cell-13" - `build_dim_skill_placeholder()`

**Correction recommandée**: Ajouter un avertissement

```python
def build_dim_skill_placeholder(fact_offers: pd.DataFrame) -> pd.DataFrame:
    """
    Placeholder : extrait les skills à partir des listes 'skills' présentes dans fact_offers.
    ⚠️ ATTENTION: Cette table sera VIDE ou très pauvre sans les données ROME.
    À remplacer par la vraie dim_skill basée sur l'API ROME competences.
    """
    all_skills = set()
    for skills in fact_offers["skills"]:
        if isinstance(skills, list):
            for s in skills:
                all_skills.add(s)

    dim_skill = pd.DataFrame(
        [{"skill_id": s, "skill_label": s, "skill_category": None} for s in sorted(all_skills)]
    )

    # ⚠️ Avertissement si vide
    if len(dim_skill) == 0:
        print("⚠️  ATTENTION: Aucune compétence trouvée dans les offres.")
        print("   → Activer le scope api_romev1 pour obtenir le référentiel complet")

    return dim_skill
```

---

### Cell id="cell-21" - `build_compass_graph()`

**Correction recommandée**: Gérer le cas où il n'y a pas d'arêtes

```python
def build_compass_graph(...) -> nx.Graph:
    """
    Construit un graphe bipartite (jobs / skills).
    ⚠️ ATTENTION: Graphe incomplet sans données ROME.
    """
    G = nx.Graph()

    # ... (code existant)

    # ⚠️ Vérification finale
    if G.number_of_edges() == 0:
        print("⚠️  ATTENTION: Graphe sans arêtes job-skill.")
        print("   → Aucune compétence trouvée dans les offres.")
        print("   → Le graphe ne contient que des nœuds isolés.")

    print(f"✅ Graphe Compass V0 : {G.number_of_nodes()} nœuds, {G.number_of_edges()} arêtes")
    return G
```

---

## 🎯 RÉSULTAT ATTENDU DU NOTEBOOK (Version Actuelle)

### Ce qui va fonctionner ✅
1. **Chargement des données** : 6,150 offres chargées
2. **Table `fact_offers`** : Complète (6,150 lignes)
3. **Table `dim_location`** : Complète (localisation OK)
4. **Table `dim_job`** : Complète (codes ROME extraits des offres)
5. **Visualisations** :
   - ✅ Top 20 métiers (ROME)
   - ✅ Top 20 villes
   - ✅ Types de contrat
   - ⚠️ Distribution salaires (beaucoup de NaN)

### Ce qui sera incomplet ⚠️
1. **Table `dim_skill`** : **VIDE** ou presque
2. **Table `bridge_offer_skill`** : **VIDE** ou presque
3. **Graphe Compass** : Seulement des nœuds job, **PAS d'arêtes job-skill**
4. **Métriques du graphe** : Degré = 0 pour la plupart des nœuds
5. **Matrice de transition** : Basique (identité)

---

## 📝 RECOMMANDATIONS

### Option 1 : Exécuter le Notebook Tel Quel
```bash
# Activer venv
cd /Users/akimguentas/Documents/elevia-compass
source .venv/bin/activate

# Lancer Jupyter
jupyter notebook analysis_elevia_compass.ipynb
```

**Résultat**:
- ✅ Notebook s'exécute sans erreur
- ⚠️ Graphe incomplet (pas de compétences)
- ⚠️ Beaucoup d'avertissements sur les données manquantes

---

### Option 2 : Activer les Scopes ROME (RECOMMANDÉ)

**Actions**:
1. Contacter France Travail pour activer :
   - `api_romev1`
   - `api_romev1.read`

2. Mettre à jour `.env` :
   ```env
   FT_SCOPES=api_offresdemploiv2 o2dsoffre api_romev1
   ```

3. Récupérer les données ROME :
   ```bash
   python fetchers/fetch_rome_metiers.py
   python fetchers/fetch_rome_competences.py
   python fetchers/fetch_rome_fiches_metiers.py
   ```

4. Relancer le notebook avec données complètes

**Résultat**:
- ✅ `dim_skill` complète (référentiel ROME)
- ✅ `bridge_offer_skill` complète
- ✅ Graphe Compass complet avec arêtes job-skill
- ✅ Métriques du graphe pertinentes

---

## 🚀 COMMANDES POUR LANCER LE NOTEBOOK

```bash
# 1. Aller dans le répertoire
cd /Users/akimguentas/Documents/elevia-compass

# 2. Activer l'environnement virtuel
source .venv/bin/activate

# 3. Vérifier que Jupyter est installé
jupyter --version

# 4. Si Jupyter n'est pas installé :
pip install jupyter notebook ipykernel

# 5. Lancer Jupyter
jupyter notebook analysis_elevia_compass.ipynb

# 6. Dans le navigateur, exécuter toutes les cellules :
#    Menu → Cell → Run All
```

---

## 📊 TABLEAU RÉCAPITULATIF

| Composant | Status | Remarque |
|-----------|--------|----------|
| **Environnement Python** | ✅ OK | venv avec toutes les dépendances |
| **Données offres** | ✅ OK | 6,150 offres disponibles |
| **fact_offers** | ✅ OK | Table complète |
| **dim_location** | ✅ OK | Localisation complète |
| **dim_job** | ✅ OK | Codes ROME extraits |
| **dim_skill** | ❌ VIDE | Scope ROME manquant |
| **bridge_offer_skill** | ❌ VIDE | Scope ROME manquant |
| **Graphe Compass** | ⚠️ INCOMPLET | Nœuds OK, arêtes manquantes |
| **Visualisations** | ⚠️ PARTIELLES | Métiers/villes OK, compétences KO |
| **Monte Carlo** | ⚠️ BASIQUE | Matrice identité uniquement |

---

## 🎯 CONCLUSION

**Le notebook VA FONCTIONNER** mais produira des résultats **incomplets** en raison de l'absence des données ROME (compétences).

**Actions immédiates**:
1. ✅ Tu peux exécuter le notebook maintenant pour voir les premières analyses
2. ⚠️ Activer les scopes ROME pour avoir un graphe Compass complet
3. 🔄 Relancer le notebook après avoir récupéré les données ROME

**Commande finale**:
```bash
cd /Users/akimguentas/Documents/elevia-compass
source .venv/bin/activate
jupyter notebook analysis_elevia_compass.ipynb
```

---

**✅ Diagnostic effectué par Claude Code**
**📅 25 Novembre 2025**
