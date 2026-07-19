"""Cohort Control Console — what-if simulator for spinning ad load up or down."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src import analytics, db, theme, ui

ui.page_header("Cohort Control Console",
               "A what-if console for the spin-up/spin-down decision: move the ad-load lever "
               "for a cohort and the equilibrium model reprices the book — more supply "
               "clears at lower eCPM, softer fill, and a viewer-experience cost. Nothing is "
               "persisted; this is a planning surface.")

inv = db.run_sql("cohort_inventory")

c0, c1 = st.columns([1.2, 2])
with c0:
    sel = st.selectbox("Cohort", inv.cohort_name)
    row = inv[inv.cohort_name == sel].iloc[0]
    mult = st.slider("Ad load vs today", 0.5, 1.5, 1.0, 0.05,
                     format="%.2fx",
                     help="1.0x = current pods/hour for this cohort")
    st.markdown(f"<span style='color:#898781'>{row.description}</span>",
                unsafe_allow_html=True)
    label, color, icon = theme.status_for_fill(row.fill_rate)
    st.markdown(f"Current demand status: <span style='color:{color}; font-weight:700;'>"
                f"{icon} {label}</span> · sell-through {row.fill_rate:.0%} · "
                f"eCPM ${row.avg_ecpm:.0f}", unsafe_allow_html=True)

sim = analytics.simulate_ad_load(row, mult)

with c1:
    ui.kpi_row([
        ("Impressions (90d)", f"{sim['imps']/1e3:,.0f}k", f"{sim['d_imps_pct']:+.1%}"),
        ("Revenue (90d)", f"${sim['revenue']/1e3:,.1f}k",
         f"{sim['d_revenue_pct']:+.1%} (${sim['d_revenue']:+,.0f})"),
        ("Clearing eCPM", f"${sim['ecpm']:.2f}", f"{sim['d_ecpm_pct']:+.1%}"),
        ("Sell-through", f"{sim['fill']:.1%}", f"{sim['d_fill']:+.1%}"),
    ])
    g1, g2 = st.columns(2)
    with g1:
        st.metric("Ad completion (proj.)",
                  f"{row.completion_rate + sim['completion_delta']:.1%}",
                  f"{sim['completion_delta']:+.1%} vs today")
    with g2:
        st.metric("Advertiser incremental conv. (proj.)",
                  f"{(sim['conv_mult'] - 1):+.1%}",
                  "vs today, saturation-adjusted", delta_color="off")
    if sim["churn_flag"]:
        st.warning("⚠ Viewer-experience guardrail: this is a low-attention cohort — pushing "
                   "load above 1.25x risks session abandonment and churn. Recommend staging "
                   "the increase and watching completion weekly.")

# revenue curve across the whole lever range, with the chosen point marked
mults = np.arange(0.5, 1.51, 0.02)
sims = [analytics.simulate_ad_load(row, float(m)) for m in mults]
rev = [s["revenue"] / 1e3 for s in sims]
opt_i = int(np.argmax(rev))

c2, c3 = st.columns([1.5, 1])
with c2:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mults, y=rev, mode="lines", name="Projected revenue",
        line=dict(width=2, color=theme.CAT[0]),
        hovertemplate="%{x:.2f}x load · $%{y:,.0f}k<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[mult], y=[sim["revenue"] / 1e3], mode="markers+text", name="Your setting",
        marker=dict(size=12, color=theme.INK, line=dict(width=2, color=theme.CAT[0])),
        text=[f"  {mult:.2f}x"], textposition="middle right",
        textfont=dict(color=theme.INK),
        hovertemplate="Your setting · $%{y:,.0f}k<extra></extra>"))
    fig.add_vline(x=mults[opt_i], line=dict(color=theme.MUTED, width=1, dash="dot"),
                  annotation_text=f"revenue-max {mults[opt_i]:.2f}x",
                  annotation_position="top left", annotation_font_color=theme.MUTED)
    fig.update_layout(title=f"Projected 90-day revenue vs ad load — {sel}",
                      height=400, xaxis_title="Ad load multiplier",
                      yaxis_title="Revenue ($k)", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
with c3:
    st.markdown("**Model assumptions (stated, not hidden)**")
    st.markdown(
        f"- Price pass-through: eCPM ∝ load^−{analytics.PRICE_PASSTHROUGH} "
        "(more supply, softer clearing prices)\n"
        f"- Advertiser demand elasticity: quantity ∝ price^−{analytics.DEMAND_ELASTICITY}\n"
        f"- Fill = demand ÷ slots, capped at 98.5%\n"
        f"- Incremental conversions scale as impressions^{analytics.CONV_SATURATION} "
        "(frequency saturation)\n"
        "- Completion decays with load, faster for low-attention cohorts\n\n"
        "In production these elasticities would be estimated from pricing "
        "experiments (regional ad-load tests), not assumed.")
    if st.button("Add to rollout plan", type="primary", use_container_width=True):
        st.session_state.setdefault("plan", []).append(
            f"{sel}: set ad load to {mult:.2f}x "
            f"(Δ revenue {sim['d_revenue_pct']:+.1%}, Δ completion {sim['completion_delta']:+.1%})")
    for item in st.session_state.get("plan", []):
        st.markdown(f"- {item}")
    if st.session_state.get("plan") and st.button("Clear plan", use_container_width=True):
        st.session_state["plan"] = []
        st.rerun()

db.show_sql("cohort_inventory", "SQL: cohort baseline feeding the simulator")
