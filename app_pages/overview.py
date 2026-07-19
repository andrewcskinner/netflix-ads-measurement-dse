"""Platform Overview — headline delivery, revenue, and sell-through."""

import plotly.graph_objects as go
import streamlit as st

from src import db, theme, ui

ui.page_header("Platform Overview",
               "90-day health of the ads platform: delivery, booked revenue, and where "
               "sell-through is strong or soft.")

daily = db.run_sql("daily_delivery")
inv = db.run_sql("cohort_inventory")
adv = db.run_sql("advertiser_summary")
manifest = db.query("SELECT * FROM build_manifest")
avg_ecpm = db.query(
    "SELECT AVG(ecpm_usd) AS e FROM fact_placement WHERE is_holdout = 0").e[0]

ui.kpi_row([
    ("Impressions (90d)", f"{daily.impressions.sum()/1e6:,.2f}M"),
    ("Booked revenue", f"${daily.revenue_usd.sum()/1e3:,.1f}k"),
    ("Avg eCPM", f"${avg_ecpm:,.2f}"),
    ("Sell-through", f"{daily.slots_filled.sum()/daily.ad_slots.sum():.1%}"),
    ("Active advertisers", f"{len(adv)}"),
    ("Positive actions", f"{int(manifest.conversions[0]):,}"),
])

c1, c2 = st.columns(2)
with c1:
    fig = go.Figure(go.Scatter(
        x=daily.session_date, y=daily.impressions, mode="lines",
        line=dict(width=2, color=theme.CAT[0]), name="Impressions",
        hovertemplate="%{x|%b %d}<br>%{y:,.0f} impressions<extra></extra>"))
    fig.update_layout(title="Daily ad impressions", height=300, showlegend=False,
                      yaxis_title=None, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig = go.Figure(go.Scatter(
        x=daily.session_date, y=daily.revenue_usd, mode="lines",
        line=dict(width=2, color=theme.CAT[1]), name="Revenue",
        hovertemplate="%{x|%b %d}<br>$%{y:,.0f}<extra></extra>"))
    fig.update_layout(title="Daily booked revenue (USD)", height=300, showlegend=False,
                      yaxis_title=None, xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

c3, c4 = st.columns([1.15, 1])
with c3:
    inv_s = inv.sort_values("fill_rate")
    fig = go.Figure(go.Bar(
        x=inv_s.fill_rate, y=inv_s.cohort_name, orientation="h",
        marker=dict(color=theme.CAT[0], cornerradius=4),
        text=[f"{v:.0%}" for v in inv_s.fill_rate], textposition="outside",
        textfont=dict(color=theme.INK_2),
        hovertemplate="%{y}<br>Sell-through %{x:.1%}<extra></extra>"))
    fig.update_layout(title="Sell-through by session cohort", height=420,
                      xaxis=dict(tickformat=".0%", range=[0, 1.12]),
                      yaxis_title=None, bargap=0.35)
    st.plotly_chart(fig, use_container_width=True)
with c4:
    st.markdown("**Top advertisers by spend**")
    top = adv.head(12)[["advertiser_name", "category", "spend_usd", "avg_ecpm", "positive_actions"]]
    st.dataframe(
        top, hide_index=True, use_container_width=True, height=420,
        column_config={
            "advertiser_name": "Advertiser", "category": "Category",
            "spend_usd": st.column_config.NumberColumn("Spend (90d)", format="$%.0f"),
            "avg_ecpm": st.column_config.NumberColumn("Avg eCPM", format="$%.2f"),
            "positive_actions": st.column_config.NumberColumn("Positive actions", format="%d"),
        })

st.caption("Volumes reflect the simulated sample (~25k ad-tier accounts over 90 days), "
           "not platform scale — rates, prices, and lifts are the realistic part.")

db.show_sql("daily_delivery", "SQL: daily delivery")
db.show_sql("cohort_inventory", "SQL: cohort inventory health")
