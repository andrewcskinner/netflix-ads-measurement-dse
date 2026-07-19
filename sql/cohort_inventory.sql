-- Cohort-level inventory health: supply, sell-through, price, and demand breadth.
-- "Ad slots" are auction opportunities (2 per pod); a placement row exists only
-- for slots that cleared (including ghost/holdout wins, which are real demand
-- but book no revenue). Unfilled slots are the spin-up opportunity.
WITH supply AS (
    SELECT
        s.cohort_id,
        COUNT(*)                        AS sessions,
        SUM(s.ad_slots)                 AS ad_slots,
        SUM(s.slots_filled)             AS slots_filled,
        SUM(s.duration_min) / 60.0      AS watch_hours
    FROM fact_session s
    GROUP BY 1
),
demand AS (
    SELECT
        p.cohort_id,
        COUNT(*)                                            AS impressions,
        COUNT(DISTINCT p.campaign_id)                       AS campaigns_bidding,
        AVG(p.ecpm_usd)                                     AS avg_ecpm,
        SUM(CASE WHEN p.is_holdout = 0 THEN p.ecpm_usd END) / 1000.0 AS revenue_usd,
        AVG(p.completed::DOUBLE) FILTER (p.is_holdout = 0)  AS completion_rate
    FROM fact_placement p
    GROUP BY 1
)
SELECT
    c.cohort_id,
    c.cohort_name,
    c.description,
    c.attention_index,
    su.sessions,
    su.watch_hours,
    su.ad_slots,
    su.slots_filled,
    su.slots_filled::DOUBLE / su.ad_slots          AS fill_rate,
    su.ad_slots - su.slots_filled                  AS unfilled_slots,
    d.impressions,
    d.campaigns_bidding,
    d.avg_ecpm,
    d.revenue_usd,
    d.completion_rate
FROM dim_cohort c
JOIN supply  su USING (cohort_id)
JOIN demand  d  USING (cohort_id)
ORDER BY fill_rate DESC;
