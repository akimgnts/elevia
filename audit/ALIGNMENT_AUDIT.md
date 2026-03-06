# ALIGNEMENT GLOBAL DU MATCHING — AUDIT

Base : DB locale + `/tmp/parse_esco_on.json`
Note : le clustering offres est calculé via `detect_offer_cluster(title, description, skills_map)` (pas de colonne `cluster_macro` en DB).

---

## 1. COUVERTURE DES OFFRES (par cluster)

**cluster | offers | offers_with_uri | coverage | avg_uri_per_offer**

- DATA_IT | 202 | 198 | 98.02% | 6.31
- FINANCE | 0 | 0 | 0.00% | 0.00
- ENGINEERING_INDUSTRY | 218 | 209 | 95.87% | 4.00
- MARKETING_SALES | 181 | 181 | 100.00% | 5.33
- OTHER | 364 | 357 | 98.08% | 4.76

✅ Offres largement alignées ESCO (sauf FINANCE absent du dataset).

---

## 2. COUVERTURE DU PROFIL

- profile_skill_count: **16**
- profile_esco_uri_count: **16**
- profile_mapping_ratio: **1.0**
- profile_effective_esco_count (incl. promotion): **18**

✅ Le profil est bien projeté dans ESCO.

---

## 3. OVERLAP RÉEL PROFIL ↔ MARCHÉ (DATA_IT)

- profile_uri_total: **18**
- profile_uri_in_offers: **16**
- overlap_ratio: **0.889**

✅ Profil **fortement aligné** avec le marché.

---

## 4. STRUCTURE DU MARCHÉ (Top 20 ESCO par cluster)

**DATA_IT (Top 10)**
- `.../skill/97bd1c21...` (115)
- `.../skill/21d2f96d...` (91)
- `.../skill/25f0ea33...` (88)
- `.../skill/143769cb...` (87)
- `.../skill/09f2f811...` (82)
- `.../skill/6d3edede...` (81)
- `.../skill/15d76317...` (79)
- `.../skill/7111b95d...` (69)
- `.../skill/ccd0a1d9...` (58)
- `.../skill/598de5b0...` (49)

(Top 20 disponibles si besoin.)

---

## 5. GAP ANALYSIS (DATA_IT)

**A. Marché → Profil (Top offer URIs missing in profile)**
Top 10 (compétences demandées non présentes chez le profil) :
- `.../skill/21d2f96d...` (91)
- `.../skill/143769cb...` (87)
- `.../skill/09f2f811...` (82)
- `.../skill/6d3edede...` (81)
- `.../skill/7111b95d...` (69)
- `.../skill/7b5cce4d...` (36)
- `.../skill/f0de4973...` (27)
- `.../skill/19a8293b...` (19)
- `.../skill/2b9f4584...` (19)
- `.../skill/66db424f...` (13)

**B. Profil → Marché (Top profile URIs missing in offers)**
- `.../skill/3a2d5b45...` (0)
- `.../skill/cb668e89...` (0)

---

## 6. IMPACT RÉEL DU MATCHING (DATA_IT, offres VIE valides)

- offers_tested: **166**
- mean_score: **63.5**
- stdev_score: **20.07**
- distribution:
  - 0–39: **22**
  - 40–59: **50**
  - 60–79: **61**
  - 80–100: **33**

✅ Le moteur **discrimine** (distribution large, écart-type élevé).

---

## 7. DIAGNOSTIC FINAL

1) **Donnée offres propre ?** → **Oui** (couverture ESCO >95% sur clusters majeurs)
2) **Profil correctement traduit ESCO ?** → **Oui** (mapping_ratio = 1.0)
3) **Même ontologie marché/profil ?** → **Oui** (overlap_ratio = 0.889)

**Conclusion**
Le système est **aligné** sur les trois couches (profil, offres, ESCO).
La friction résiduelle est **produit** (gap skills manquantes / compétences du profil peu demandées), pas technique.
