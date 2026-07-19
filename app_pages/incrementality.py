"""Incrementality & Elasticity — ghost-ads lift readouts and frequency response."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src import analytics, db, theme, ui

ui.page_header("Incrementality & Elasticity",
               "Every campaign carries a 20% ghost-ads holdout: the auction is won, the ad is "
               "suppressed, and the ghost impression is logged. Treated vs holdout conversion "
               "rates give causal lift — reported with confidence intervals, including the "
               "honest nulls.")

lift = analytics.add_lift_columns(db.run_sql("campaign_lift"))
freq = db.run_sql("frequency_response")

well_powered = lift[(lift.n_treated >= 1500) & (lift.conv_holdout >= 10)].copy()

sig_pos = int((well_powered.significant & (well_powered.lift > 0)).sum())
ui.kpi_row([
    ("Campaigns measured", f"{len(lift)}"),
    ("Well-powered readouts", f"{len(well_powered)}"),
    ("Significant positive lift", f"{sig_pos}"),
    ("Median lift (well-powered)", f"{well_powered.lift.median():+.1%}"),
    ("Incremental conversions (est.)", f"{well_powered.incremental_conversions.clip(lower=0).sum():,.0f}"),
])

st.subheader("Campaign lift readouts")
top = well_powered.nlargest(18, "n_treated").sort_values("lift")
colors = [theme.CAT[0] if s else theme.MUTED for s in top.significant]
fig = go.Figure()
fig.add_vline(x=0, line=dict(color=theme.BASELINE, width=1))
fig.add_trace(go.Scatter(
    x=top.lift, y=top.campaign_name, mode="markers",
    error_x=dict(array=top.hi - top.lift, arrayminus=top.lift - top.lo,
                 color=theme.MUTED, thickness=1.5, width=3),
    marker=dict(size=9, color=colors),
    customdata=np.stack([top.n_treated, top.n_holdout, top.p], axis=-1),
    hovertemplate="<b>%{y}</b><br>Lift %{x:+.1%}<br>"
                  "n treated %{customdata[0]:,.0f} · holdout %{customdata[1]:,.0f}"
                  "<br>p = %{customdata[2]:.3f}<extra></extra>"))
fig.update_layout(title="Conversion lift with 95% CI — 18 largest campaigns "
                        "(blue = significant at α=0.05, gray = not)",
                  height=520, xaxis=dict(tickformat="+.0%", title="Relative lift vs holdout"),
                  yaxis_title=None, showlegend=False)
st.plotly_chart(fig, use_container_width=True)
st.caption("A gray marker is a result, not a failure: reporting non-significant lift honestly "
           "is the core trust bar for advertiser-facing measurement.")

st.divider()
st.subheader("Single-campaign deep dive")
options = well_powered.sort_values("n_treated", ascending=False)
sel = st.selectbox("Campaign", options.campaign_name, index=0)
row = options[options.campaign_name == sel].iloc[0]

c1, c2 = st.columns([1, 1.3])
with c1:
    st.metric("Measured lift", f"{row.lift:+.1%}",
              f"95% CI [{row.lo:+.1%}, {row.hi:+.1%}]", delta_color="off")
    verdict = "Statistically significant (α=0.05)" if row.significant else "Not statistically significant"
    st.markdown(f"**{verdict}** — p = {row.p:.3f}")
    st.markdown(
        f"- Treated accounts: **{row.n_treated:,.0f}** (conv rate {row.rt:.2%})\n"
        f"- Holdout accounts: **{row.n_holdout:,.0f}** (conv rate {row.rh:.2%})\n"
        f"- Est. incremental conversions: **{max(row.incremental_conversions,0):,.0f}**\n"
        f"- Avg frequency: **{row.avg_frequency:.1f}** exposures/account\n"
        f"- Objective: {row.objective} · Category: {row.category}")
with c2:
    samples = analytics.bayes_lift_samples(row.conv_treated, row.n_treated,
                                           row.conv_holdout, row.n_holdout)
    p_pos = (samples > 0).mean()
    hist, edges = np.histogram(samples, bins=60)
    centers = (edges[:-1] + edges[1:]) / 2
    fig = go.Figure(go.Bar(
        x=centers, y=hist, width=(edges[1] - edges[0]) * 0.92,
        marker=dict(color=[theme.CAT[0] if c > 0 else theme.MUTED for c in centers],
                    cornerradius=2),
        hovertemplate="Lift %{x:+.1%}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=theme.BASELINE, width=1))
    lo_b, hi_b = np.percentile(samples, [2.5, 97.5])
    fig.update_layout(
        title=f"Bayesian posterior of lift (Jeffreys priors) — P(lift > 0) = {p_pos:.1%}, "
              f"95% credible [{lo_b:+.1%}, {hi_b:+.1%}]",
        height=330, xaxis=dict(tickformat="+.0%"), yaxis=dict(visible=False),
        showlegend=False, bargap=0)
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Frequency response (elasticity)")
cat_sel = st.selectbox("Advertiser category", sorted(freq.category.unique()),
                       index=sorted(freq.category.unique()).index(row.category)
                       if row.category in freq.category.unique() else 0)
fit = analytics.fit_frequency_response(freq[freq.category == cat_sel])
if fit.get("ok"):
    c3, c4 = st.columns([1.3, 1])
    with c3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=fit["f"], y=fit["rt"], mode="lines+markers", name="Exposed",
            line=dict(width=2, color=theme.CAT[0]), marker=dict(size=8),
            hovertemplate="f=%{x:.0f} · conv %{y:.2%}<extra>Exposed</extra>"))
        fig.add_trace(go.Scatter(
            x=fit["f"], y=fit["rh"], mode="lines+markers", name="Ghost holdout",
            line=dict(width=2, color=theme.CAT[1]), marker=dict(size=8),
            hovertemplate="f=%{x:.0f} · conv %{y:.2%}<extra>Ghost holdout</extra>"))
        fig.update_layout(
            title=f"Conversion rate by exposure frequency — {cat_sel}",
            height=380, xaxis=dict(title="Exposures per account (8 = 8+)", dtick=1),
            yaxis=dict(tickformat=".1%", title="90-day conversion rate"),
            legend=dict(orientation="h", y=1.02, yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Both curves rise with frequency because heavy viewers convert more — the "
                   "activity confound. The causal read is the *gap* between the curves at "
                   "each frequency, plotted right.")
    with c4:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=fit["f"], y=fit["gap"], mode="markers", name="Observed gap",
            marker=dict(size=np.clip(np.sqrt(fit["pairs"]) / 8, 6, 18), color=theme.CAT[0]),
            hovertemplate="f=%{x:.0f} · incremental %{y:.2%}<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=fit["curve_f"], y=fit["curve"], mode="lines", name="Fitted saturation",
            line=dict(width=2, color=theme.CAT[3], dash="dash"),
            hovertemplate="f=%{x:.1f} · fitted %{y:.2%}<extra></extra>"))
        fig.update_layout(
            title=f"Incremental rate vs frequency · fit: {fit['amplitude']:.1%}·(1−e^−{fit['k']:.2f}f)",
            height=380, xaxis=dict(title="Exposures per account", dtick=1),
            yaxis=dict(tickformat=".1%", title="Treated − holdout conv rate"),
            legend=dict(orientation="h", y=1.02, yanchor="bottom"))
        st.plotly_chart(fig, use_container_width=True)
        half_sat = np.log(2) / fit["k"]
        st.caption(f"Diminishing returns: ~50% of achievable lift is reached by "
                   f"**{half_sat:.1f} exposures**. Frequency beyond ~{3*half_sat:.0f} buys "
                   f"little — budget is better spent on reach or a fresh cohort.")
else:
    st.info("Not enough matched frequency data in this category for a stable fit.")

db.show_sql("campaign_lift", "SQL: ghost-ads lift readout")
db.show_sql("frequency_response", "SQL: frequency response")
