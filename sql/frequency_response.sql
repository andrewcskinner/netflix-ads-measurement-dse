-- Conversion rate by exposure frequency, split by treatment arm.
-- For holdout pairs, freq counts ghost impressions — the exposures the account
-- *would* have received — which lets the same frequency bucket be compared
-- treated vs counterfactual. The gap between the two curves at each bucket is
-- the incremental effect; its flattening is saturation.
-- Caveat (by construction and in real life): high-frequency accounts are
-- heavier viewers, so the *within-arm* slope confounds frequency with
-- activity; the treated-minus-holdout gap per bucket is the clean read.
WITH exposure AS (
    SELECT campaign_id, account_id,
           MAX(is_holdout) AS is_holdout,
           COUNT(*)        AS freq
    FROM fact_placement
    GROUP BY 1, 2
),
converters AS (
    SELECT DISTINCT campaign_id, account_id
    FROM fact_positive_action
)
SELECT
    a.category,
    e.is_holdout,
    LEAST(e.freq, 8)          AS freq_bucket,       -- 8 = "8+"
    COUNT(*)                  AS pairs,
    COUNT(cv.account_id)      AS converters
FROM exposure e
JOIN dim_campaign c   USING (campaign_id)
JOIN dim_advertiser a USING (advertiser_id)
LEFT JOIN converters cv USING (campaign_id, account_id)
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
