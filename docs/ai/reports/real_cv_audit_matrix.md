# Real CV Audit Matrix

Audit réel effectué sur les PDF du dossier `/Users/akimguentas/Downloads/cvtest` en passant par le flow produit :
- `PDF -> /profile/parse-file -> DB profile_id -> /inbox`
- sans fixture `profiles/*.json`
- sans `akim_guentas_matching.json`
- sans modification code/scoring/matching core

REAL_CV_AUDIT_MATRIX:
CV: Akim Guentas – Audit & Data Analyst.pdf
profile_id: 645fa20a-6271-4fca-b6ff-3a7adcd6dbd6
extraction_source: baseline
role_detected: business_analysis
matching_skills_count: 9
top10_good: 3
top10_discussable: 4
top10_bad: 3
main_failure_mode: generic analyst/audit vocabulary scatters into policy/privacy/finance/cyber roles
verdict: discutable

REAL_CV_AUDIT_MATRIX:
CV: Akim_Guentas_Resume.pdf
profile_id: 46377341-39c5-46fb-91e3-e4353cce947f
extraction_source: baseline
role_detected: data_analytics
matching_skills_count: 14
top10_good: 0
top10_discussable: 0
top10_bad: 10
main_failure_mode: profile persistence failure in DB caused inbox fallback/default behavior and unusable ranking
verdict: mauvais

REAL_CV_AUDIT_MATRIX:
CV: CV - Nawel KADI 2026.pdf
profile_id: 78e32172-96d7-47ef-9e97-e48724b7953a
extraction_source: baseline
role_detected: hr_ops
matching_skills_count: 6
top10_good: 2
top10_discussable: 2
top10_bad: 6
main_failure_mode: HR profile overmatches generic process/manager signals and surfaces engineering/manager roles too high
verdict: mauvais

REAL_CV_AUDIT_MATRIX:
CV: CV CDI MOUSTAPHA LO DATA.pdf
profile_id: 47f95086-bcba-41bb-9b92-7879223da53f
extraction_source: baseline
role_detected: data_analytics
matching_skills_count: 15
top10_good: 4
top10_discussable: 4
top10_bad: 2
main_failure_mode: data profile still leaks to SOC/quality/policy because generic analytics terms dominate
verdict: discutable

REAL_CV_AUDIT_MATRIX:
CV: CV LISE MAITRE.pdf
profile_id: d29419ff-8a46-42c8-9c7f-d77642e0f556
extraction_source: baseline
role_detected: marketing_communication
matching_skills_count: 14
top10_good: 6
top10_discussable: 2
top10_bad: 2
main_failure_mode: marketing/commercial profile partly works but still overmatches non-commercial project roles
verdict: discutable

REAL_CV_AUDIT_MATRIX:
CV: CV Mathilde CEVAK.pdf
profile_id: 9e59480e-b714-4574-be30-4a89dfbca96b
extraction_source: baseline
role_detected: sales_business_dev
matching_skills_count: 9
top10_good: 6
top10_discussable: 3
top10_bad: 1
main_failure_mode: sales profile is mostly coherent but first results still include adjacent event/marketing roles
verdict: bon

REAL_CV_AUDIT_MATRIX:
CV: CV WECKER.pdf
profile_id: cff83202-3ce7-4703-996b-21f83f8a94ff
extraction_source: baseline
role_detected: software_it
matching_skills_count: 24
top10_good: 7
top10_discussable: 2
top10_bad: 1
main_failure_mode: software profile is broadly coherent but mixed IT/data roles remain noisy
verdict: bon

REAL_CV_AUDIT_MATRIX:
CV: CV_2026-02-17_Ania_Benabbas (1).pdf
profile_id: 52760a69-9537-4389-9340-dd4102d73129
extraction_source: baseline
role_detected: finance_ops
matching_skills_count: 6
top10_good: 2
top10_discussable: 2
top10_bad: 6
main_failure_mode: finance profile is pulled toward generic analyst/policy/cyber roles instead of finance-first offers
verdict: mauvais

REAL_CV_AUDIT_MATRIX:
CV: CV_HANI_Sidi-Walid.pdf
profile_id: f80fb360-8887-448b-99c5-b836732601b3
extraction_source: baseline
role_detected: data_analytics
matching_skills_count: 22
top10_good: 7
top10_discussable: 2
top10_bad: 1
main_failure_mode: strong data profile works well, with only a few adjacent cyber/process drifts
verdict: bon

REAL_CV_AUDIT_MATRIX:
CV: CV_MouisseTheo.pdf
profile_id: e4d3f162-abed-4d55-a8ae-ed5722349c65
extraction_source: baseline
role_detected: software_it
matching_skills_count: 14
top10_good: 4
top10_discussable: 2
top10_bad: 4
main_failure_mode: software profile is diluted by generic project/communication signals and drifts into HR/project roles
verdict: discutable

REAL_CV_AUDIT_MATRIX:
CV: Dia Madina-CV alternance en gestion de patrimoine.pdf
profile_id: e54b9acb-2b91-4415-931d-1aef7bdf07d6
extraction_source: baseline
role_detected: finance_ops
matching_skills_count: 3
top10_good: 1
top10_discussable: 2
top10_bad: 7
main_failure_mode: too few durable finance signals extracted from the real PDF, resulting in mostly out-of-domain matches
verdict: mauvais

REAL_CV_AUDIT_MATRIX:
CV: data-analyst-resume-example.pdf
profile_id: 981daf88-edb3-4258-b1be-8b996939cd12
extraction_source: baseline
role_detected: data_analytics
matching_skills_count: 8
top10_good: 6
top10_discussable: 2
top10_bad: 2
main_failure_mode: data profile is broadly coherent but still lets QA/automation outrank some pure data roles
verdict: discutable

GLOBAL_VERDICT:
- matching réel exploitable ? non, pas de façon suffisamment fiable sur l’ensemble des vrais CV PDF
- profils qui marchent : CV_HANI_Sidi-Walid, CV WECKER, CV Mathilde CEVAK
- profils partiellement exploitables : CV CDI MOUSTAPHA LO DATA, CV LISE MAITRE, data-analyst-resume-example, Akim Guentas – Audit & Data Analyst, CV_MouisseTheo
- profils qui échouent : Akim_Guentas_Resume, CV - Nawel KADI 2026, CV_2026-02-17_Ania_Benabbas (1), Dia Madina-CV alternance en gestion de patrimoine
- cause principale : sur vrais PDF, le parsing remonte des signaux génériques et parfois contaminés qui dominent le matching, et un cas de persistance DB a même cassé la réutilisation du profil
- prochain fix recommandé : fiabiliser d’abord le flux réel `parse-file -> save_profile -> inbox` sur PDF bruyants, en particulier nettoyage des caractères NUL et réduction du poids des signaux génériques (`analyse`, `communication`, `suivi`, `management`, etc.) avant toute calibration fine de ranking

Comparaison avec les fixtures :
- oui, les résultats fixtures étaient trop optimistes
- les fixtures donnaient des profils plus propres, plus courts, plus centrés BI/data et sans bruit PDF réel
- les vrais CV ne reproduisent pas ce niveau de qualité : plusieurs profils dérivent vers analyst/policy/SOC/project roles sur des signaux trop génériques
- le matching actuel est crédible sur quelques profils très data/IT, mais pas encore robuste sur des CV réels hétérogènes