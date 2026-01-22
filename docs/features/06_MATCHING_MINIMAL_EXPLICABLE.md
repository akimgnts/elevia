```markdown
# SPRINT 6 — MATCHING MINIMAL EXPLICABLE (VERSION FINALE)
**Projet : Elevia**  
**Destiné à : Claude Code**  
**Statut : VERROUILLÉ / PRODUCTION-READY (Sprint scope)**

---

## 🎯 Objectif du Sprint 6

Implémenter un **moteur de matching VIE minimal**, déterministe et explicable, qui tient la promesse produit :

> **« Voici les offres VIE réellement cohérentes avec ton profil, et pourquoi. »**

Ce moteur :
- ne prédit rien
- n’invente rien
- n’interprète pas
- **explique chaque décision avec des faits observables**

---

## 🧱 Contraintes fondamentales (NON NÉGOCIABLES)

1. **VIE strict**
   - Une offre est rejetée si `is_vie` est `False` **ou `None`**
   - Pas de déduction implicite

2. **Hard filter avant scoring**
   - Pays obligatoire
   - Titre + entreprise obligatoires
   - Whitelist pays profil respectée si fournie

3. **Aucune IA décisionnelle**
   - Pas de ML
   - Pas de probabilité
   - Pas de prédiction d’acceptation

4. **Graphe contextuel**
   - Utilisé **uniquement comme pondération**
   - Jamais comme filtre
   - Clamp ±20% max

5. **Seuil strict**
   - Score final = `int(round(100 * total))`
   - Affichage uniquement si `score >= 80`
   - Si aucune offre ≥ 80 → message explicite

---

## ⚙️ Architecture du moteur

### Pipeline global

```

Profil (pré-extrait 1x)
↓
Hard Filter strict (VIE, pays, champs min)
↓
Score skills (signal principal)
↓
Early-skip mathématique (impossible d’atteindre 80 ? → skip)
↓
Score langues / études / pays
↓
Score final (round)
↓
Explication (2–3 raisons max)

````

---

## 🧮 Formule de scoring (VERROUILLÉE)

### Pondérations
```python
skills    = 0.70
languages = 0.15
education = 0.10
country   = 0.05
````

### Score final

```python
score = int(round(100 * (
    0.70 * skills_score +
    0.15 * languages_score +
    0.10 * education_score +
    0.05 * country_score
)))
```

---

## 🧠 Détail des sous-scores

### 1) Skills (signal principal)

* Intersection profil ∩ offre
* Pondération par :

  * **IDF (rareté)** calculée sur le corpus d’offres
  * **Contexte** (optionnel) via `context_coeffs`
* Clamp contexte : `[0.8 ; 1.2]`

```text
skills_score = Σ(idf * contexte) / Σ(idf * contexte_offre)
```

Si l’offre n’a **aucune skill** → `skills_score = 0`

---

### 2) Langues

* Si aucune langue requise → `1.0`
* Sinon :

```text
|langues_profil ∩ langues_offre| / |langues_offre|
```

---

### 3) Niveau d’études

* Mapping ordinal fixe :

  * bac=1, bac+2=2, bac+3=3, bac+5=4, phd=5
* Si l’offre n’a pas de niveau requis → `1.0`
* Sinon :

  * `1.0` si profil ≥ requis
  * `0.0` sinon

---

### 4) Pays (préférence)

* Si le profil n’a pas de préférences → `1.0`
* Sinon :

  * `1.0` si pays dans préférences
  * `0.5` sinon (acceptable mais non préféré)

---

## 🚀 Optimisations clés (industrielles)

* **Profil extrait une seule fois**
* **Pays canonisé une seule fois** dans le hard filter
* **Early-skip mathématique** :

  * si même avec `languages=1`, `education=1`, `country=1`
    le score max < 80 → on skip sans calculer le reste
* **Explication générée uniquement si l’offre est retenue**

---

## 🧾 Explications utilisateur (2–3 max)

Ordre de priorité :

1. Compétences clés alignées (top 2–4)
2. Langues
3. Études ou pays (si pertinent)

### Exemples autorisés

* « Compétences clés alignées : excel, sql, reporting »
* « Langue requise compatible »
* « Niveau d’études cohérent »

### Interdits

* ❌ IA
* ❌ probabilité
* ❌ potentiel
* ❌ recommandation

---

## 📦 Sortie attendue

```json
{
  "profile_id": "p1",
  "threshold": 80,
  "results": [
    {
      "offer_id": "o1",
      "score": 92,
      "breakdown": {
        "skills": 0.88,
        "languages": 1.0,
        "education": 1.0,
        "country": 0.5
      },
      "reasons": [
        "Compétences clés alignées : excel, sql, reporting",
        "Langue requise compatible",
        "Niveau d’études cohérent"
      ]
    }
  ],
  "message": null
}
```

Si aucun résultat :

```json
{
  "profile_id": "p1",
  "threshold": 80,
  "results": [],
  "message": "Aucune offre n’atteint 80% avec les données actuelles (compétences/langues/études/pays)."
}
```

---

## 🧪 Tests obligatoires

1. Une offre avec `is_vie=None` → rejetée
2. Une offre avec `is_vie=False` → rejetée
3. Aucune explication > 3 lignes
4. Aucun mot interdit (`ia`, `probabilité`)
5. Early-skip ne laisse pas passer une offre < 80

---

## ✅ Definition of Done — Sprint 6

* Mêmes inputs → mêmes outputs
* Aucune donnée inventée
* Matching explicable humainement
* Performance OK sur gros volumes
* Tests passent

---

## 🔒 Note finale

Ce moteur **ne “comprend” pas encore un parcours**.
Il **évalue une compatibilité factuelle**.

La compréhension des trajectoires viendra **après** (Sprint ultérieur).
Ici, le signal est clair, propre, assumé.

**Sprint 6 est clos.**

```
```
