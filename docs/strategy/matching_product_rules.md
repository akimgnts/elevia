# Règles Produit — Matching V.I.E

**Version :** 1.0
**Sprint :** 10
**Statut :** Validé

---

## 1. Objectif de ce document

Ce document définit **ce que le produit fait** en fonction du diagnostic de matching.

Il empêche :
- L'improvisation lors de l'implémentation
- Les décisions incohérentes entre développeurs
- Les débats "on fait quoi si..." en plein sprint
- Le flou sur ce qui est affiché, masqué ou bloqué

Toute décision produit relative au matching doit être conforme à ce document.
Si une situation n'est pas couverte ici, c'est un trou dans la spec — pas une liberté d'interprétation.

---

## 2. Principe fondamental

> **Le diagnostic décide des actions produit.**
> **Le score sert uniquement à ordonner les offres entre elles.**

Autrement dit :

| Composant | Rôle | Ne fait PAS |
|-----------|------|-------------|
| **Diagnostic** | Décide si l'offre est visible, si un warning s'affiche, si l'utilisateur peut postuler | Ne classe pas les offres |
| **Score** | Classe les offres autorisées par ordre de pertinence | Ne bloque jamais, ne masque jamais, ne décide jamais seul |

Le score peut être élevé et l'offre masquée.
Le score peut être faible et l'offre affichée.
C'est normal. C'est voulu.

---

## 3. Matrice de règles produit

| Diagnostic | Verdict | Affichage | Bouton Postuler | Tri | Justification |
|------------|---------|-----------|-----------------|-----|---------------|
| **V.I.E Eligibility** | KO | **MASQUÉE** | N/A | Exclue du tri | Candidat légalement inéligible. Afficher serait trompeur. |
| **Langue** | KO | **AFFICHÉE** (section dégradée) | Actif + **WARNING** | Démotion (affiché après les OK) | L'utilisateur peut apprendre la langue. Décision lui appartient. |
| **Hard Skills** | KO | **AFFICHÉE** (normal) | Actif | Normal (par score) | Compétences = signal fort mais pas fatal. L'utilisateur juge. |
| **Education** | PARTIAL | **AFFICHÉE** (normal) | Actif | Normal | Expérience peut compenser. Pas de censure. |
| **Soft Skills** | PARTIAL | **AFFICHÉE** (normal) | Actif | Normal | Trop subjectif pour bloquer. |
| **Tous critères** | OK | **AFFICHÉE** (normal) | Actif | Normal (par score) | Aucun problème détecté. |

---

## 4. Règles détaillées par type de KO

### 4.1 KO V.I.E Eligibility

**Verdict :** KO
**Cause :** Âge > 28 ans OU nationalité hors Union Européenne

**Ce que voit l'utilisateur :**
- L'offre n'apparaît pas dans la liste.
- Aucun message "offre masquée" n'est affiché.
- L'utilisateur ne sait pas que l'offre existe.

**Ce qu'il peut faire :**
- Rien. L'offre est invisible.

**Pourquoi ce choix :**
Le V.I.E est un dispositif légal (Business France). Proposer une offre à quelqu'un qui ne peut légalement pas postuler est trompeur et contre-productif. L'offre est donc retirée silencieusement.

---

### 4.2 KO Langue

**Verdict :** KO
**Cause :** Au moins une langue requise par l'offre est absente du profil

**Ce que voit l'utilisateur :**
- L'offre est affichée, mais dans une section dégradée (après les offres OK).
- Un badge ou indicateur visuel signale le problème.
- Le détail "Langue requise manquante : X" est visible.

**Ce qu'il peut faire :**
- Consulter l'offre normalement.
- Cliquer sur "Postuler".
- Un **warning explicite** s'affiche avant confirmation : "Cette offre requiert une langue que vous n'avez pas déclarée. Souhaitez-vous continuer ?"

**Pourquoi ce choix :**
Une langue peut s'apprendre. Le candidat peut être en cours de formation. La décision de postuler malgré tout lui appartient. On informe, on ne censure pas.

---

### 4.3 KO Hard Skills

**Verdict :** KO
**Cause :** Plus de 50% des compétences techniques requises sont absentes

**Ce que voit l'utilisateur :**
- L'offre est affichée normalement.
- Le détail "Compétences manquantes : X, Y, Z" est visible dans la fiche.

**Ce qu'il peut faire :**
- Consulter l'offre.
- Postuler sans avertissement supplémentaire.

**Pourquoi ce choix :**
Les compétences déclarées dans une offre sont souvent sur-spécifiées. Un candidat motivé peut compenser par de l'apprentissage rapide ou des compétences adjacentes. Le signal est informatif, pas bloquant.

---

### 4.4 PARTIAL Education

**Verdict :** PARTIAL
**Cause :** Niveau d'études du profil inférieur au niveau requis par l'offre

**Ce que voit l'utilisateur :**
- L'offre est affichée normalement.
- Le détail peut mentionner "Niveau requis non atteint".

**Ce qu'il peut faire :**
- Tout. Aucune restriction.

**Pourquoi ce choix :**
L'expérience professionnelle compense souvent le niveau d'études. Ce critère ne justifie jamais un blocage.

---

### 4.5 PARTIAL Soft Skills

**Verdict :** PARTIAL
**Cause :** Soft skills requis non déclarés dans le profil

**Ce que voit l'utilisateur :**
- L'offre est affichée normalement.
- Aucun avertissement particulier.

**Ce qu'il peut faire :**
- Tout. Aucune restriction.

**Pourquoi ce choix :**
Les soft skills sont subjectifs, mal déclarés, et souvent non-discriminants dans la vraie sélection. Aucune action produit n'est justifiée.

---

## 5. Cas limites assumés

### 5.1 Score élevé + Diagnostic KO

**Situation :** Une offre a un score de 85% mais un diagnostic `KO Langue`.

**Ce qui se passe :**
- L'offre est affichée en section dégradée.
- Le score 85% est visible.
- Le warning langue s'applique.

**Ce n'est PAS un bug.**
Le score mesure une compatibilité globale. Le diagnostic révèle un blocage spécifique. Les deux informations coexistent. L'utilisateur décide.

---

### 5.2 Score faible + Diagnostic OK

**Situation :** Une offre a un score de 45% mais aucun KO ni PARTIAL.

**Ce qui se passe :**
- L'offre est affichée normalement.
- Elle apparaît en bas de liste (tri par score).
- Aucun avertissement.

**Ce n'est PAS un bug.**
Un score faible signifie une compatibilité globale modeste, pas un problème bloquant. L'offre reste accessible.

---

### 5.3 Diagnostic contradictoire au score

**Situation :** Score 92%, mais `KO V.I.E Eligibility`.

**Ce qui se passe :**
- L'offre est **masquée**.
- Le score n'apparaît nulle part.
- L'utilisateur ne sait pas qu'il "aurait eu 92%".

**Ce n'est PAS un bug.**
L'éligibilité légale prime sur tout. Afficher un score élevé pour une offre inaccessible serait cruel et inutile.

---

### 5.4 Responsabilité utilisateur

Le produit :
- Informe sur les incompatibilités détectées.
- Ne bloque jamais la candidature (sauf illégalité).
- Ne prend pas de décision à la place de l'utilisateur.

Si un utilisateur postule malgré un KO Langue ou un KO Hard Skills, c'est son choix assumé. Le produit l'a averti. La suite ne nous appartient pas.

---

## 6. Ce que ce document interdit

- Bloquer le bouton "Postuler" sur un critère autre que l'illégalité V.I.E.
- Masquer une offre pour une raison autre que l'inéligibilité V.I.E.
- Utiliser le score seul pour décider d'une action (masquage, warning, blocage).
- Inventer une nouvelle règle sans l'ajouter à ce document.
- Appliquer une logique "intelligente" non documentée ici.

---

## 7. Résumé exécutif

| Si... | Alors... |
|-------|----------|
| KO V.I.E | Offre masquée |
| KO Langue | Offre visible + warning avant candidature |
| KO Hard Skills | Offre visible, aucun blocage |
| PARTIAL (tous) | Offre visible, aucun blocage |
| OK (tous) | Offre visible, aucun blocage |

Le score trie. Le diagnostic décide.

---

**Fin du document.**
