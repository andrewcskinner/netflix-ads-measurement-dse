-- Advertiser rollup: delivery, spend, price, and reported positive actions.
SELECT
    a.advertiser_id,
    a.advertiser_name,
    a.category,
    a.tier,
    COUNT(DISTINCT c.campaign_id)                             AS campaigns,
    COUNT(p.placement_id)                                     AS impressions,
    SUM(CASE WHEN p.is_holdout = 0 THEN p.ecpm_usd END)/1000  AS spend_usd,
    AVG(p.ecpm_usd)                                           AS avg_ecpm,
    (SELECT COUNT(*) FROM fact_positive_action pa
      WHERE pa.advertiser_id = a.advertiser_id)               AS positive_actions,
    (SELECT SUM(pa.action_value_usd) FROM fact_positive_action pa
      WHERE pa.advertiser_id = a.advertiser_id)               AS action_value_usd
FROM dim_advertiser a
JOIN dim_campaign c   USING (advertiser_id)
JOIN fact_placement p USING (campaign_id)
GROUP BY 1, 2, 3, 4
ORDER BY spend_usd DESC;
