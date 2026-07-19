-- Daily platform delivery: impressions, booked revenue, sell-through.
-- Ghost (holdout) impressions are excluded from revenue but included in
-- sell-through, since the slot cleared the auction.
SELECT
    s.session_date,
    SUM(s.ad_slots)                                            AS ad_slots,
    SUM(s.slots_filled)                                        AS slots_filled,
    SUM(s.slots_filled)::DOUBLE / SUM(s.ad_slots)              AS fill_rate,
    (SELECT COUNT(*) FROM fact_placement p
      WHERE p.session_date = s.session_date)                   AS impressions,
    (SELECT SUM(p.ecpm_usd) / 1000.0 FROM fact_placement p
      WHERE p.session_date = s.session_date AND p.is_holdout = 0) AS revenue_usd
FROM fact_session s
GROUP BY 1
ORDER BY 1;
