-- Validation queries for v3_metier complete backfill
-- Run after backfill completes to verify coverage and quality

-- 1. Coverage check: all offers should have v3_metier
SELECT
  COUNT(*) as total_offers,
  COUNT(*) FILTER (WHERE v3_count > 0) as offers_with_v3,
  ROUND(100.0 * COUNT(*) FILTER (WHERE v3_count > 0) / COUNT(*), 2) as pct_with_v3,
  COUNT(*) FILTER (WHERE v3_count >= 3) as offers_with_3_or_more,
  ROUND(100.0 * COUNT(*) FILTER (WHERE v3_count >= 3) / COUNT(*), 2) as pct_with_3_or_more
FROM (
  SELECT
    co.id,
    COUNT(*) FILTER (WHERE os.enrichment_version = 'offer_skills_v3_metier') as v3_count
  FROM clean_offers co
  LEFT JOIN offer_skills os ON os.offer_id = co.id
  WHERE co.source = 'business_france'
  GROUP BY co.id
) t;

-- 2. Skill type distribution
SELECT
  skill_type,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as pct
FROM offer_skills
WHERE enrichment_version = 'offer_skills_v3_metier'
GROUP BY skill_type
ORDER BY count DESC;

-- 3. Skills per offer distribution
SELECT
  skills_count,
  COUNT(*) as n_offers,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as pct
FROM (
  SELECT
    COUNT(*) as skills_count
  FROM offer_skills
  WHERE enrichment_version = 'offer_skills_v3_metier'
  GROUP BY offer_id
) t
GROUP BY skills_count
ORDER BY skills_count;

-- 4. Top canonical IDs (v3)
SELECT
  canonical_id,
  COUNT(*) as freq,
  COUNT(DISTINCT offer_id) as n_offers
FROM offer_skills
WHERE enrichment_version = 'offer_skills_v3_metier'
GROUP BY canonical_id
ORDER BY freq DESC
LIMIT 20;

-- 5. Evidence quality check: all rows have evidence
SELECT
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE evidence IS NOT NULL AND evidence <> '') as has_evidence,
  COUNT(*) FILTER (WHERE evidence IS NULL OR evidence = '') as missing_evidence
FROM offer_skills
WHERE enrichment_version = 'offer_skills_v3_metier';

-- 6. Domain distribution in v3 (by top skills)
SELECT
  ode.domain_tag,
  COUNT(DISTINCT os.offer_id) as n_offers,
  COUNT(*) as n_skills,
  STRING_AGG(DISTINCT canonical_id, ', ' ORDER BY canonical_id) FILTER (WHERE rn <= 3) as top_3_skills
FROM offer_skills os
JOIN clean_offers co ON co.id = os.offer_id
LEFT JOIN offer_domain_enrichment ode ON ode.source = co.source AND ode.external_id = co.external_id
WHERE os.enrichment_version = 'offer_skills_v3_metier'
  AND ode.domain_tag IS NOT NULL
WINDOW w AS (PARTITION BY ode.domain_tag ORDER BY COUNT(*) DESC)
GROUP BY ode.domain_tag
ORDER BY n_offers DESC;

-- 7. Confidence distribution
SELECT
  ROUND(confidence, 1) as confidence_rounded,
  COUNT(*) as count
FROM offer_skills
WHERE enrichment_version = 'offer_skills_v3_metier'
GROUP BY ROUND(confidence, 1)
ORDER BY confidence_rounded DESC;

-- 8. Source method check (should be ai_metier_v3)
SELECT
  source_method,
  COUNT(*) as count
FROM offer_skills
WHERE enrichment_version = 'offer_skills_v3_metier'
GROUP BY source_method;
