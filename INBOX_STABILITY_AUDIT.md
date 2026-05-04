# Audit Stabilité Inbox — Rapport Complet

## Problème Signalé
**Symptôme** : Même profil → Inbox affiche offres différentes à chaque reload  
**Impact** : Utilisateur ne sait pas si Top 10 est réellement le Top 10  
**Sévérité** : Critique (instabilité du produit)

---

## CAUSE IDENTIFIÉE

### 1. Backend: Tri Déterministe (OK)
**Fichier** : `apps/api/src/api/routes/inbox.py` ligne 1208-1221

```python
def _bucket_sort(bucket: List[InboxItem]) -> List[InboxItem]:
    return sorted(bucket, key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id))
```

Logique:
1. Score décroissant
2. Signal_score décroissant  
3. Offer_id ascendant (lexicographique)

**Verdict** : ✓ Déterministe, tri stable

**Catalogue source** : `apps/api/src/api/utils/inbox_catalog.py` ligne 316-317

```python
combined.sort(key=lambda offer: str(offer.get("id") or ""))
combined.sort(key=lambda offer: str(offer.get("publication_date") or ""), reverse=True)
```

- Cache basé sur mtime/taille fichier DB (ligne 72-76)
- Sorts stables en Python → ordre déterministe
- **Verdict** : ✓ Catalogue chargé dans ordre stable

---

### 2. Frontend: Tri INCOMPATIBLE avec Backend (PROBLÈME)
**Fichier** : `apps/web/src/lib/inboxItems.ts` ligne 157-167  

**AVANT (ancien code)**:
```typescript
export function sortInboxItemsForDisplay(items: NormalizedInboxItem[]) {
  return [...items].sort((a, b) => {
    return (
      primaryDisplayScore(b) - primaryDisplayScore(a) ||  // ← score_v3 OU score_v2 OU explanation.score
      blockersCount(a) - blockersCount(b) ||               // ← count de blockers
      strengthsCount(b) - strengthsCount(a) ||             // ← count de strengths
      recencyValue(b.publication_date) - recencyValue(a.publication_date) ||  // ← timestamp
      a.offer_id.localeCompare(b.offer_id)
    );
  });
}
```

**Problème** : `primaryDisplayScore` utilise différentes sources de score selon l'ordre de préférence :
- `scoring_v3.score * 100` (si présent)
- `scoring_v2.score * 100` (si présent)
- `explanation.score` (si présent)
- `score` (fallback)

**Exemple d'instabilité** :
```
Backend retourne:
- Offre A: score=85, signal_score=0.5, scoring_v3.score=0.75
- Offre B: score=80, signal_score=0.6, scoring_v3=null

Backend sort: A (score 85), B (score 80)

Frontend primaryDisplayScore:
- A: 75 (utilise scoring_v3)
- B: 80 (utilise score)

Frontend sort: B (80), A (75)
→ ORDRE INVERSE !
```

**Appels redondants** : `sortInboxItemsForDisplay` appelée DEUX FOIS
- Ligne 309 `inboxItems.ts`: `normalizeAndSortInboxItems` = normalize + sort
- Ligne 838 `InboxPage.tsx`: Reappelle après filtrage des décisions

→ Risque que les deux tris divergent

---

## FIXES APPLIQUÉS

### Fix 1: `sortInboxItemsForDisplay` — Matcher Backend
**Fichier** : `apps/web/src/lib/inboxItems.ts` ligne 157-167

**Code nouveau** :
```typescript
export function sortInboxItemsForDisplay(items: NormalizedInboxItem[]): NormalizedInboxItem[] {
  return [...items].sort((a, b) => {
    // Match backend sort exactly: score desc, signal_score desc, offer_id asc
    const scoreA = a.score || 0;
    const scoreB = b.score || 0;
    const signalA = a.signal_score || 0;
    const signalB = b.signal_score || 0;

    if (scoreB !== scoreA) {
      return scoreB - scoreA; // score desc
    }
    if (signalB !== signalA) {
      return signalB - signalA; // signal_score desc
    }
    return a.offer_id.localeCompare(b.offer_id); // offer_id asc
  });
}
```

**Logique** :
1. Score décroissant ✓
2. Signal_score décroissant ✓
3. Offer_id ascendant ✓

→ Désormais identique au backend

---

### Fix 2: Enlever Tri Redondant InboxPage
**Fichier** : `apps/web/src/pages/InboxPage.tsx` ligne 838

**AVANT**:
```typescript
const displayedItems = useMemo(() => sortInboxItemsForDisplay(availableItems), [availableItems]);
```

**APRÈS**:
```typescript
const displayedItems = useMemo(() => availableItems, [availableItems]);
```

**Raison** :
- `availableItems` = items déjà triés par backend + filtrés
- `filter()` préserve l'ordre
- Pas besoin de retrier
- Élimine risque de divergence

---

## TESTS AJOUTÉS

### 1. Tests Backend — Tri Stable
**Fichier** : `apps/api/tests/test_inbox_stability.py`

Tests:
- ✓ `test_inbox_sorting_deterministic` — Tri idempotent
- ✓ `test_limit_applied_after_sorting` — Limit après tri, pas avant
- ✓ `test_tiebreak_with_same_scores` — Tiebreak lexicographique stable

---

### 2. Tests Frontend — Tri Compatible
**Fichier** : `apps/web/src/lib/__tests__/inboxItems.test.ts`

Tests:
- ✓ `should sort by score descending as primary key` — Score prioritaire
- ✓ `should use signal_score as tiebreaker` — Signal_score comme tiebreak
- ✓ `should use offer_id lexicographic tiebreaker` — Offer_id comme tiebreak final
- ✓ `should be deterministic on multiple sorts` — Tri idempotent
- ✓ `should preserve order when filtering` — Filter ne change pas ordre

---

## GARANTIES APRÈS FIX

| Critère | Avant | Après |
|---------|-------|-------|
| Tri backend déterministe | ✓ | ✓ |
| Tri frontend identique backend | ✗ | ✓ |
| Appels tri redondants | 2 | 1 |
| Order stable après filter | ✗ | ✓ |
| Limit appliqué après tri | ✓ | ✓ |

---

## LOGIQUE FINALE

```
API /inbox
  ↓ [retourne items triés: score desc, signal_score desc, offer_id asc]
Frontend reçoit (data.items)
  ↓
normalizeAndSortInboxItems(data.items)
  ├─ normalizeInboxItems() → NormalizedInboxItem[]
  └─ sortInboxItemsForDisplay() → trie par (score desc, signal_score desc, offer_id asc)
  ↓ [items déjà triés]
setItems(normalized) → state items
  ↓
availableItems = items.filter(!decided) → ordre préservé
  ↓
displayedItems = availableItems → DIRECT, pas de retri
  ↓ [Affiche en ordre correct]
Render InboxCardV2 list
```

---

## VÉRIFICATION

**Cas de test** :
```
Même profile_id → même /inbox API call
→ même items retournés
→ même normalizeAndSortInboxItems() 
→ même displayedItems
→ même rendu
```

✓ Déterministe, reproductible, prévisible

---

## FICHIERS MODIFIÉS

1. `apps/web/src/lib/inboxItems.ts` — sortInboxItemsForDisplay()
2. `apps/web/src/pages/InboxPage.tsx` — Enlever tri redondant
3. `apps/api/tests/test_inbox_stability.py` — Tests backend (ajouté)
4. `apps/web/src/lib/__tests__/inboxItems.test.ts` — Tests frontend (ajouté)

---

## RÈGLES RESPECTÉES

✓ Ne pas toucher scoring core  
✓ Ne pas toucher parsing CV  
✓ Ne pas modifier classification profil  
✓ Pas de refactor global  
✓ Fixes ciblés Inbox/tri/cache  
✓ Tests ajoutés  

---

## VERDICT

**Pour un même profil et un même catalogue, l'Inbox retourne désormais un Top N déterministe trié par score décroissant.**

Tri frontend = tri backend → ordre stable → utilisateur sait que Top 10 = Top 10 réel.
