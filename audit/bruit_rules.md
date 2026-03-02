# bruit_detecte — definition et regles

Definition:
- `Brut detecte` = tokens extraits par `esco.extract.extract_raw_skills_from_profile`.
- `Ignorees` = tokens elimines par `profile.skill_filter.strict_filter_skills` (bruit + non-ESCO).

Regles principales (pointeurs code):
1. Tokenisation + normalisation: `apps/api/src/esco/extract.py:_normalize_text`
2. Split + filtrage stopwords / digits / longueur < 2: `apps/api/src/esco/extract.py:_split_text`
3. Filtrage bruit (len < 3, digits, @, stopwords): `apps/api/src/profile/skill_filter.py:_has_noise`
4. Alias ESCO deterministe: `apps/api/src/profile/skill_filter.py:strict_filter_skills` + `profile/esco_aliases.py`
5. Mapping ESCO strict (sans fuzzy): `apps/api/src/esco/mapper.py:map_skill(enable_fuzzy=False)`
6. Dedup URI: `apps/api/src/profile/skill_filter.py:strict_filter_skills`
7. Troncature MAX_VALIDATED=40: `apps/api/src/profile/skill_filter.py:MAX_VALIDATED`
8. Bigram whitelist limitee: `apps/api/src/esco/extract.py:BIGRAM_WHITELIST`

Exemples (issus du CV, stage + regle):
- ai -> noise_removed (len < 3)
- akinguentas13 -> noise_removed (digit)
- bi -> noise_removed (len < 3)
- bl -> noise_removed (len < 3)
- em -> noise_removed (len < 3)
- ia -> noise_removed (len < 3)
- ml -> noise_removed (len < 3)
- accuracy -> unresolved_esco (no_esco_match)
- acquired -> unresolved_esco (no_esco_match)
- acquisition -> unresolved_esco (no_esco_match)