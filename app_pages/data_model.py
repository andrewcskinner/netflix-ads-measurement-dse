"""Data Model & Methodology — schema, calibration against planted truth, and SQL browser."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src import analytics, db, theme, ui

ui.page_header("Data Model & Methodology",
               "The warehouse behind every page: a seeded simulation with planted ground "
               "truth, which means the estimators can be audited against what was actually "
               "simulated — the calibration check below is the punchline.")

manifest = db.query("SELECT * FROM build_manifest").iloc[0]
st.caption(f"Build: seed {manifest.seed} · window {manifest.window_start} → {manifest.window_end} · "
           f"{manifest.placements:,} placements · {manifest.conversions:,} positive actions · "
           f"generated in {manifest.build_seconds}s · fingerprint {manifest.fingerprint}")

tab_schema, tab_calib, tab_sql, tab_notes = st.tabs(
    ["Schema", "Estimator calibration", "SQL browser", "Methodology notes"])

with tab_schema:
    counts = db.query("""
        SELECT table_name, estimated_size AS rows FROM duckdb_tables()
        WHERE database_name = current_database() ORDER BY rows DESC""")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.graphviz_chart("""
digraph G {
  bgcolor="transparent"; rankdir=LR;
  node [shape=record, style=filled, fillcolor="#1a1a19", color="#383835",
        fontcolor="#c3c2b7", fontname="Helvetica", fontsize=11];
  edge [color="#898781", arrowsize=0.7];
  advertiser [label="dim_advertiser|100 brands, category, tier"];
  campaign   [label="dim_campaign|budget, objective, flight"];
  creative   [label="dim_creative|real-ish creative names"];
  ctype      [label="dim_creative_type|awareness · DR · CTLM"];
  cohort     [label="dim_cohort|12 session cohorts"];
  account    [label="dim_account|anonymized, household_id"];
  session    [label="fact_session|220k sessions, slots"];
  placement  [label="fact_placement|~1M auctions, ghost flag"];
  paction    [label="fact_positive_action|advertiser-reported"];
  abtest     [label="dim_ab_test|30 creative experiments"];
  truth      [label="sim_campaign_truth|planted lift & elasticity", fillcolor="#252523"];
  advertiser -> campaign -> creative; ctype -> creative;
  cohort -> session; account -> session; session -> placement;
  campaign -> placement; creative -> placement;
  advertiser -> paction; account -> paction; campaign -> paction;
  campaign -> abtest; campaign -> truth [style=dashed];
}""")
    with c2:
        st.dataframe(counts, hide_index=True, use_container_width=True, height=430,
                     column_config={"table_name": "Table",
                                    "rows": st.column_config.NumberColumn("Rows", format="%d")})
    st.markdown(
        "- **Privacy posture:** accounts are opaque integers with a household id — no "
        "demographics beyond behavioral cohort, no PII, nothing reversible. A household "
        "can hold several accounts, mirroring profile reality.\n"
        "- **Ghost holdout** lives on the placement, so incrementality is computable from "
        "delivery data alone plus the advertiser's positive-action report.")

with tab_calib:
    st.markdown(
        "Because the simulator plants each campaign's true effect, the ghost-ads estimator "
        "can be scored against it. The target is the **delivered (intent-to-treat) lift** — "
        "the planted asymptotic lift attenuated by the frequency saturation actually "
        "reached — since that, not the asymptote, is what a holdout readout measures.")
    lift = analytics.add_lift_columns(db.run_sql("campaign_lift"))
    truth = db.query("SELECT campaign_id, true_lift, true_itt_lift FROM sim_campaign_truth")
    cal = lift.merge(truth, on="campaign_id")
    cal = cal[(cal.n_treated >= 1500) & (cal.conv_holdout >= 10)]
    cover = ((cal.true_itt_lift >= cal.lo) & (cal.true_itt_lift <= cal.hi)).mean()
    c1, c2 = st.columns([1.4, 1])
    with c1:
        lim = max(cal.true_itt_lift.max(), cal.lift.max()) * 1.15
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[-0.1, lim], y=[-0.1, lim], mode="lines",
                                 line=dict(color=theme.BASELINE, width=1, dash="dot"),
                                 hoverinfo="skip", name="Perfect recovery"))
        fig.add_trace(go.Scatter(
            x=cal.true_itt_lift, y=cal.lift, mode="markers",
            error_y=dict(array=cal.hi - cal.lift, arrayminus=cal.lift - cal.lo,
                         color="rgba(137,135,129,0.35)", thickness=1),
            marker=dict(size=7, color=theme.CAT[0], opacity=0.85),
            customdata=cal.campaign_name,
            hovertemplate="<b>%{customdata}</b><br>True ITT %{x:+.1%} · "
                          "Measured %{y:+.1%}<extra></extra>", name="Campaign"))
        fig.update_layout(title="Measured lift vs planted (delivered) truth — 95% CIs",
                          height=460, xaxis=dict(title="True ITT lift", tickformat="+.0%"),
                          yaxis=dict(title="Measured lift", tickformat="+.0%"),
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.metric("95% CI coverage of truth", f"{cover:.0%}",
                  "target ≈ 95% for a calibrated estimator", delta_color="off")
        st.metric("Well-powered campaigns scored", f"{len(cal)}")
        mae = (cal.lift - cal.true_itt_lift).abs().mean()
        st.metric("Mean absolute error", f"{mae:.1%}")
        st.markdown(
            "Scatter off the diagonal is **sampling noise, not bias** — and the CIs say so. "
            "This is exactly the discipline advertiser-facing lift products need: an "
            "estimate is only as trustworthy as its stated uncertainty.")

with tab_sql:
    st.markdown("Every analysis in this console runs the SQL below against DuckDB — "
                "no hidden pandas munging of core metrics.")
    import pathlib
    files = sorted(p.stem for p in (db.SQL_DIR).glob("*.sql"))
    pick = st.selectbox("Query", files)
    st.code(db.sql_text(pick), language="sql")

with tab_notes:
    st.markdown("""
#### Measurement design
- **Ghost-ads holdout (20%)** per (account × campaign), assigned by deterministic hash —
  the holdout wins the auction and the ad is suppressed, so treated and holdout groups are
  drawn from the identical bidding population. No selection bias, no PSA costs.
- **Lift** = treated ÷ holdout conversion rate − 1, with 95% CIs via the delta method on the
  log rate ratio, and a two-proportion z-test for significance. **Bayesian companion
  readout** uses Jeffreys Beta posteriors — P(lift > 0) is often the more useful number in
  an advertiser conversation than a p-value.
- **Elasticity**: incremental rate by frequency is fit to A·(1−e^(−kf)). The within-arm
  frequency slope is confounded by viewer activity; the treated-minus-holdout gap per
  frequency bucket is the clean read. Half-saturation frequency drives the budget and
  frequency-cap recommendations.
- **Attribution meta-experiment**: last-touch attributed conversions vs holdout-measured
  incremental conversions, per campaign — quantifying how flattering last-touch is.

#### Known limitations (deliberate)
- Conversion matching is modeled as account-level joins on the advertiser's positive-action
  report; a production system would run this in a clean room with match-rate calibration.
- The cohort simulator's elasticities are stylized constants; production values would come
  from staged regional ad-load experiments.
- Small campaigns are honestly noisy. The recommender shrinks thin cells toward pooled
  estimates rather than ranking on raw noise.
""")
