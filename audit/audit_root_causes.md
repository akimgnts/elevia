# audit_root_causes

## Problème 1 : règle trop agressive (len < 3)

Exemples: ai, bi, bl, em, ia

## Problème 2 : n-grams non capturés

Exemples: machine learning, power bi

## Problème 3 : mapping ESCO incomplet

Exemples: accuracy, acquired, acquisition, across, actionable

## Problème 4 : filtre générique / stopword

Exemples: akinguentas13, 2017lycee, 2022universite, 2023caceis, 2024tribunal

## Réponses ciblées

- opc: CV_2026-02-17_Ania_Benabbas (1).pdf: ESCO_MAPPING / UNRESOLVED_ESCO
- opcvm: CV_2026-02-17_Ania_Benabbas (1).pdf: ESCO_MAPPING / UNRESOLVED_ESCO
- bi: Akim_Guentas_Resume.pdf: LENGTH_FILTER / REMOVED_LENGTH; CV_2026-02-17_Ania_Benabbas (1).pdf: NEVER_EXTRACTED (NOT_CAPTURED_BY_EXTRACTOR)
- power bi: Akim_Guentas_Resume.pdf: NEVER_EXTRACTED (NOT_CAPTURED_BY_EXTRACTOR)
- machine learning: Akim_Guentas_Resume.pdf: NEVER_EXTRACTED (NOT_CAPTURED_BY_EXTRACTOR)