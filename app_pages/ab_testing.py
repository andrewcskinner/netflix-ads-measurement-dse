"""A/B Testing — creative experiments plus a meta-experiment on attribution itself."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from src import analytics, db, theme, ui

ui.page_header("A/B Testing",
               "Creative experiments run account-split (an account always sees the same arm), "
               "and the measurement system itself gets tested: the meta-experiment below "
               "compares last-touch attribution against holdout-measured truth.")

ab = db.run_sql("ab_results")
lift = analytics.add_lift_columns(db.run_sql("campaign_lift"))


def arm_stats(g: pd.DataFrame) -> pd.Series:
    a = g[g.arm == "A"].iloc[0]
    b = g[g.arm == "B"].iloc[0]
    metric = a.primary_metric
    if metric == "ctr":
        xa, na, xb, nb = a.clicks, a.impressions, b.clicks, b.impressions
    else:
        xa, na, xb, nb = a.completes, a.impressions, b.completes, b.impressions
    ra, rb = xa / na, xb / nb
    p_pool = (xa + xb) / (na + nb)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / na + 1 / nb))
    z = (rb - ra) / se if se > 0 else 0
    p = 2 * stats.norm.sf(abs(z))
    return pd.Series(dict(
        advertiser=a.advertiser_name, campaign=a.campaign_name, metric=metric,
        creative_a=a.creative_name, creative_b=b.creative_name,
        imps_a=na, imps_b=nb, rate_a=ra, rate_b=rb,
        delta=rb / ra - 1 if ra else np.nan, p=p, significant=p < 0.05,
        xa=xa, xb=xb))


tests = ab.groupby("test_id").apply(arm_stats, include_groups=False).reset_index()

n_sig = int(tests.significant.sum())
winners_b = int((tests.significant & (tests.delta > 0)).sum())
ui.kpi_row([
    ("Live creative tests", f"{len(tests)}"),
    ("Significant results", f"{n_sig}"),
    ("B beats A", f"{winners_b}"),
    ("A beats B", f"{n_sig - winners_b}"),
    ("Median |Δ| (significant)", f"{tests[tests.significant].delta.abs().median():.1%}" if n_sig else "—"),
])

st.subheader("Creative test deep dive")
tests_sorted = tests.sort_values("p")  # most conclusive first
label = {r.test_id: f"{r.advertiser} — {r.campaign.split('·')[-1].strip()} ({r.metric})"
         for r in tests_sorted.itertuples()}
sel = st.selectbox("Experiment", tests_sorted.test_id, format_func=lambda t: label[t])
t = tests[tests.test_id == sel].iloc[0]

c1, c2 = st.columns([1.2, 1])
with c1:
    names = [f"A · {t.creative_a}", f"B · {t.creative_b}"]
    rates = [t.rate_a, t.rate_b]
    ns = [t.imps_a, t.imps_b]
    errs = [analytics.Z95 * np.sqrt(r * (1 - r) / n) for r, n in zip(rates, ns)]
    fig = go.Figure(go.Bar(
        x=names, y=rates, error_y=dict(array=errs, color=theme.MUTED, thickness=1.5),
        marker=dict(color=[theme.CAT[0], theme.CAT[2]], cornerradius=4), width=0.45,
        text=[f"{r:.2%}" for r in rates], textposition="outside",
        textfont=dict(color=theme.INK_2),
        hovertemplate="%{x}<br>%{y:.3%} · %{customdata:,} imps<extra></extra>",
        customdata=ns))
    fig.update_layout(title=f"{t.metric.replace('_',' ').title()} by arm (95% CI)",
                      height=380, yaxis=dict(tickformat=".1%",
                                             range=[0, max(rates) * 1.35]),
                      showlegend=False, bargap=0.4)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    st.metric("Arm B vs Arm A", f"{t.delta:+.1%}", f"p = {t.p:.3f}", delta_color="off")
    if t.significant:
        winner = "B" if t.delta > 0 else "A"
        wname = t.creative_b if t.delta > 0 else t.creative_a
        st.success(f"**Ship arm {winner}** — “{wname}” wins on {t.metric.replace('_',' ')} "
                   f"at α=0.05. Roll to 100% of the campaign's rotation.")
    else:
        st.info("**No significant difference.** Keep the 50/50 rotation or run longer; "
                "do not ship a winner off noise.")
    st.markdown(f"- Impressions: A {t.imps_a:,.0f} · B {t.imps_b:,.0f}\n"
                f"- Events: A {t.xa:,.0f} · B {t.xb:,.0f}\n"
                f"- Assignment: account-level hash split (sticky arms)")

st.markdown("**All creative tests**")
show = tests[["advertiser", "campaign", "metric", "rate_a", "rate_b", "delta", "p", "significant"]]
st.dataframe(show.sort_values("p"), hide_index=True, use_container_width=True, height=300,
             column_config={
                 "advertiser": "Advertiser", "campaign": "Campaign", "metric": "Metric",
                 "rate_a": st.column_config.NumberColumn("Rate A", format="percent"),
                 "rate_b": st.column_config.NumberColumn("Rate B", format="percent"),
                 "delta": st.column_config.NumberColumn("Δ B vs A", format="percent"),
                 "p": st.column_config.NumberColumn("p-value", format="%.3f"),
                 "significant": st.column_config.CheckboxColumn("Significant"),
             })

st.divider()
st.subheader("Meta-experiment: last-touch attribution vs holdout-measured truth")
st.markdown(
    "Advertisers often credit **every** conversion from an exposed account to the campaign "
    "(last-touch). The ghost-ads holdout measures what would have happened anyway. "
    "Comparing the two quantifies how much last-touch overstates.")

wp = lift[(lift.n_treated >= 1500) & (lift.conv_holdout >= 10) & (lift.lift > 0.02)].copy()
wp["attributed"] = wp.conv_treated                      # last-touch: all exposed conversions
wp["incremental"] = wp.incremental_conversions.clip(lower=0)
wp = wp[wp.incremental > 0]
wp["overstatement"] = wp.attributed / wp.incremental

c3, c4 = st.columns([1.2, 1])
with c3:
    fig = go.Figure()
    lim = wp.attributed.max() * 1.1
    fig.add_trace(go.Scatter(x=[0, lim], y=[0, lim], mode="lines", name="y = x (no overstatement)",
                             line=dict(color=theme.BASELINE, width=1, dash="dot"),
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=wp.incremental, y=wp.attributed, mode="markers", name="Campaign",
        marker=dict(size=8, color=theme.CAT[0], opacity=0.85),
        customdata=np.stack([wp.campaign_name, wp.overstatement], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b><br>Incremental %{x:,.0f} · "
                      "Attributed %{y:,.0f}<br>%{customdata[1]:.1f}× overstated<extra></extra>"))
    fig.update_layout(title="Attributed (last-touch) vs incremental conversions per campaign",
                      height=420, xaxis_title="Incremental (holdout-measured)",
                      yaxis_title="Attributed (last-touch)",
                      legend=dict(orientation="h", y=1.02, yanchor="bottom"))
    st.plotly_chart(fig, use_container_width=True)
with c4:
    med = wp.overstatement.median()
    st.metric("Median overstatement", f"{med:.1f}×",
              "last-touch vs incremental", delta_color="off")
    hist, edges = np.histogram(wp.overstatement.clip(upper=15), bins=24)
    centers = (edges[:-1] + edges[1:]) / 2
    fig = go.Figure(go.Bar(x=centers, y=hist, width=(edges[1] - edges[0]) * 0.9,
                           marker=dict(color=theme.CAT[0], cornerradius=3),
                           hovertemplate="%{x:.1f}× · %{y} campaigns<extra></extra>"))
    fig.add_vline(x=med, line=dict(color=theme.INK, width=1, dash="dash"),
                  annotation_text=f"median {med:.1f}×",
                  annotation_font_color=theme.INK_2)
    fig.update_layout(title="Distribution of overstatement factor",
                      height=330, xaxis_title="Attributed ÷ incremental (capped 15×)",
                      yaxis=dict(visible=False), bargap=0)
    st.plotly_chart(fig, use_container_width=True)
st.caption("Takeaway for advertiser conversations: last-touch numbers are directionally "
           "useful but systematically flattering; incrementality is the billing-grade truth.")

db.show_sql("ab_results", "SQL: A/B readout")
db.show_sql("campaign_lift", "SQL: lift readout behind the meta-experiment")
