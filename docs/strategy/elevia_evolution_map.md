# 🧭 ELEVIA — Carte d’Évolution Produit & Mathématique

> **Objectif du document**  
Figer une vision long terme d’Elevia **sans bloquer la V1**, en reliant chaque brique mathématique à :  
- une **feature produit concrète**,  
- des **pré-requis data clairs**,  
- une **condition d’activation explicite**.

Ce document sert de **mémoire stratégique** : rien n’est perdu, tout est **ordonné dans le temps**.

---

## 🟢 PHASE 0 — Socle V1 (Sprint 5–6)
### *"Matching vrai, explicable, sans IA"*

### 🎯 But
Tenir la promesse cœur d’Elevia :
> *Montrer les offres réellement cohérentes avec un profil, et expliquer pourquoi.*

### 🔧 Briques math / techniques actives
- Normalisation des données (offres + profils)
- Pondération par rareté (anti-générique)
- Graphe contextuel **utilisé uniquement comme pondération**
- Matching set-based (logique compétences dominante)
- Règles hard (éligibilité VIE, langues, pays, niveau)

### 📦 Features produit
- Liste d’offres alignées (≥ seuil)
- Score compréhensible
- 2–3 justifications lisibles

### ✅ Pré-requis
- Données offres propres
- Modèle profil minimal
- Aucun feedback utilisateur nécessaire

### 🚦 Condition GO
- Le moteur peut expliquer chaque résultat en une phrase

---

## 🟡 PHASE 1 — Delta Profil ↔ Marché
### *"Comprendre ce qui manque vraiment"*

### 🎯 But
Transformer l’écart entre le profil et les offres pertinentes en **axes d’amélioration clairs**.

### 🔧 Briques math
- Analyse de delta (skills manquantes fréquentes)
- Comptage pondéré sur le stock d’offres

### 📦 Features produit
- "Tu es à 72 %, voici ce qui te fait passer à 80 %"
- Top compétences à acquérir
- Estimation du gain en opportunités

### ✅ Pré-requis
- Volume d’offres suffisant
- Skills normalisées fiables

### 🚦 Condition GO
- Le delta est stable et cohérent sur plusieurs profils

---

## 🟠 PHASE 2 — Recommandation de formations
### *"Relier un manque à une action concrète"*

### 🎯 But
Proposer **la formation la plus utile**, pas une liste générique.

### 🔧 Briques math
- Mapping formation → compétences
- Croisement delta ↔ formations
- Estimation d’impact global (pas offre par offre)

### 📦 Features produit
- Recommandation de formations pertinentes
- "Cette formation comble X manques majeurs"
- Notion de ROI apprentissage (temps / gain)

### ✅ Pré-requis
- Référentiel formations propre (ex : Anotéa)
- Mapping formation–skills fiable

### 🚦 Condition GO
- Les formations recommandées sont traçables et justifiables

---

## 🔵 PHASE 3 — Apprentissage par l’usage
### *"Apprendre ce qui aide vraiment"*

### 🎯 But
Optimiser les recommandations à partir du comportement réel.

### 🔧 Briques math
- Feedback loop (clic, save, apply)
- Bandits bayésiens / optimisation adaptative

### 📦 Features produit
- Recommandations qui s’améliorent dans le temps
- Priorisation intelligente des suggestions

### ✅ Pré-requis
- Tracking d’événements propre
- Volume d’utilisateurs suffisant

### 🚦 Condition GO
- Données comportementales exploitables

---

## 🟣 PHASE 4 — Lecture du marché (Compass)
### *"Comprendre les tendances"*

### 🎯 But
Apporter une vision stratégique du marché de l’emploi.

### 🔧 Briques math
- Statistiques descriptives
- Tension marché / nowcasting
- Analyse temporelle

### 📦 Features produit
- Métiers et compétences en tension
- Signaux d’ouverture / fermeture

### ✅ Pré-requis
- Historique data fiable sur plusieurs mois

### 🚦 Condition GO
- Stabilité des signaux dans le temps

---

## 🔴 PHASE 5 — Trajectoires & simulations
### *"Explorer des chemins réalistes"*

### 🎯 But
Aider à projeter des parcours professionnels crédibles.

### 🔧 Briques math
- Graphe multi-niveaux
- Transitions métier / compétences
- Markov / Monte Carlo (encadrés)

### 📦 Features produit
- Simulation de trajectoires
- Plans en plusieurs étapes
- Alternatives réalistes

### ✅ Pré-requis
- Données de transitions fiables
- Garde-fous anti-fantasy

### 🚦 Condition GO
- Capacité à expliquer chaque trajectoire sans promesse irréaliste

---

## 🧠 Principe directeur (à ne jamais perdre)

> **Chaque brique mathématique n’est activée que si elle :**
> 1. repose sur des données fiables,
> 2. débloque une feature utilisateur claire,
> 3. reste explicable sans magie.

---

## 🏁 Conclusion
Elevia n’est pas un produit figé mais **un système évolutif par couches**.  
La V1 n’est pas une réduction de l’ambition : c’est **la condition pour qu’elle existe vraiment**.

