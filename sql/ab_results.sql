-- Creative A/B test readout: per test, per arm.
-- Arms are assigned by account-level hash, so an account always sees the same
-- creative for a given campaign (no within-user contamination). Holdout
-- (ghost) impressions are excluded — they saw nothing.
SELECT
    t.test_id,
    t.primary_metric,
    t.hypothesis,
    c.campaign_name,
    adv.advertiser_name,
    CASE WHEN p.creative_id = t.creative_id_a THEN 'A' ELSE 'B' END AS arm,
    cr.creative_name,
    ct.creative_type,
    COUNT(*)          AS impressions,
    COUNT(DISTINCT p.account_id) AS accounts,
    SUM(p.clicked)    AS clicks,
    SUM(p.completed)  AS completes,
    AVG(p.ecpm_usd)   AS avg_ecpm
FROM dim_ab_test t
JOIN fact_placement p ON p.campaign_id = t.campaign_id
                     AND p.creative_id IN (t.creative_id_a, t.creative_id_b)
                     AND p.is_holdout = 0
JOIN dim_creative cr       ON cr.creative_id = p.creative_id
JOIN dim_creative_type ct  ON ct.creative_type_id = cr.creative_type_id
JOIN dim_campaign c        ON c.campaign_id = t.campaign_id
JOIN dim_advertiser adv    ON adv.advertiser_id = c.advertiser_id
GROUP BY ALL
ORDER BY t.test_id, arm;
