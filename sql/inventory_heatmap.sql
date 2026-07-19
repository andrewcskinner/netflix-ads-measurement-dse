-- Sell-through and clearing price by cohort x daypart.
-- This is the "not all inventory is equally sought after" cut: the same ad
-- slot is worth 4x more in a Prestige Drama prime pod than in daytime
-- Background Autoplay, and advertisers bid accordingly.
WITH slot_supply AS (
    SELECT cohort_id, daypart,
           SUM(ad_slots)     AS ad_slots,
           SUM(slots_filled) AS slots_filled
    FROM fact_session
    GROUP BY 1, 2
),
pricing AS (
    SELECT cohort_id, daypart,
           AVG(ecpm_usd) AS avg_ecpm,
           COUNT(*)      AS impressions
    FROM fact_placement
    GROUP BY 1, 2
)
SELECT
    c.cohort_name,
    s.daypart,
    s.ad_slots,
    s.slots_filled::DOUBLE / s.ad_slots AS fill_rate,
    s.ad_slots - s.slots_filled         AS unfilled_slots,
    p.avg_ecpm,
    p.impressions
FROM slot_supply s
JOIN pricing p USING (cohort_id, daypart)
JOIN dim_cohort c USING (cohort_id)
ORDER BY c.cohort_id,
         CASE s.daypart WHEN 'early_morning' THEN 1 WHEN 'daytime' THEN 2
                        WHEN 'prime' THEN 3 ELSE 4 END;
