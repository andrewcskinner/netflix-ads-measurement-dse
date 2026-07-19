-- Ghost-ads incrementality readout, one row per campaign.
--
-- Design: for each (account, campaign) pair, a deterministic 20% hash bucket
-- is held out — the ad wins the auction but is suppressed, and the ghost
-- impression is logged. Treated and holdout accounts are therefore drawn from
-- the same auction-winning population, so the holdout conversion rate is a
-- valid counterfactual. Positive actions come back from advertisers via the
-- positive-action report (fact_positive_action), matched to accounts.
WITH exposure AS (
    SELECT campaign_id,
           account_id,
           MAX(is_holdout) AS is_holdout,      -- pair-level arm (constant by design)
           COUNT(*)        AS freq
    FROM fact_placement
    GROUP BY 1, 2
),
converters AS (
    SELECT DISTINCT campaign_id, account_id
    FROM fact_positive_action
)
SELECT
    e.campaign_id,
    c.campaign_name,
    a.advertiser_name,
    a.category,
    ct.creative_type                                       AS objective,
    c.budget_usd,
    COUNT(*)               FILTER (e.is_holdout = 0)       AS n_treated,
    COUNT(cv.account_id)   FILTER (e.is_holdout = 0)       AS conv_treated,
    COUNT(*)               FILTER (e.is_holdout = 1)       AS n_holdout,
    COUNT(cv.account_id)   FILTER (e.is_holdout = 1)       AS conv_holdout,
    AVG(e.freq)            FILTER (e.is_holdout = 0)       AS avg_frequency
FROM exposure e
JOIN dim_campaign c        USING (campaign_id)
JOIN dim_advertiser a      USING (advertiser_id)
JOIN dim_creative_type ct  ON ct.creative_type_id = c.objective_type_id
LEFT JOIN converters cv    USING (campaign_id, account_id)
GROUP BY ALL
ORDER BY n_treated DESC;
