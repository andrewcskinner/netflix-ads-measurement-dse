-- Cohort x advertiser-category cells that power the recommendation engine:
-- observed conversion lift (treated vs holdout), price, and reach per cell.
-- Pairs are attributed to the account's primary cohort so the lift read is at
-- the audience level the planner can actually buy.
WITH exposure AS (
    SELECT p.campaign_id,
           p.account_id,
           MAX(p.is_holdout) AS is_holdout,
           COUNT(*)          AS freq
    FROM fact_placement p
    GROUP BY 1, 2
),
converters AS (
    SELECT DISTINCT campaign_id, account_id
    FROM fact_positive_action
),
pair_level AS (
    SELECT
        ac.primary_cohort_id AS cohort_id,
        adv.category,
        e.is_holdout,
        e.freq,
        CASE WHEN cv.account_id IS NOT NULL THEN 1 ELSE 0 END AS converted
    FROM exposure e
    JOIN dim_account ac    USING (account_id)
    JOIN dim_campaign c    USING (campaign_id)
    JOIN dim_advertiser adv USING (advertiser_id)
    LEFT JOIN converters cv USING (campaign_id, account_id)
),
price AS (
    SELECT p.cohort_id, adv.category, AVG(p.ecpm_usd) AS avg_ecpm
    FROM fact_placement p
    JOIN dim_campaign c     USING (campaign_id)
    JOIN dim_advertiser adv USING (advertiser_id)
    GROUP BY 1, 2
)
SELECT
    pl.cohort_id,
    pl.category,
    COUNT(*)            FILTER (is_holdout = 0) AS n_treated,
    SUM(converted)      FILTER (is_holdout = 0) AS conv_treated,
    COUNT(*)            FILTER (is_holdout = 1) AS n_holdout,
    SUM(converted)      FILTER (is_holdout = 1) AS conv_holdout,
    AVG(freq)           FILTER (is_holdout = 0) AS avg_frequency,
    pr.avg_ecpm
FROM pair_level pl
JOIN price pr ON pr.cohort_id = pl.cohort_id AND pr.category = pl.category
GROUP BY pl.cohort_id, pl.category, pr.avg_ecpm
HAVING COUNT(*) FILTER (is_holdout = 0) >= 200
ORDER BY 1, 2;
