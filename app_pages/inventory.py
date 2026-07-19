"""Inventory & Demand — not all inventory is equally sought after."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src import db, theme, ui

ui.page_header("Inventory & Demand",
               "The same 30-second slot clears at very different prices depending on who is "
               "watching and when. Demand concentrates in high-attention cohorts and prime "
               "dayparts; the soft cells are the spin-up/spin-down decisions.")

inv = db.run_sql("cohort_inventory")
hm = db.run_sql("inventory_heatmap")

dp_order = ["early_morning", "daytime", "prime", "late_night"]
dp_labels = ["Early AM", "Daytime", "Prime", "Late night"]
coh_order = inv.sort_values("fill_rate", ascending=False).cohort_name.tolist()

metric = st.radio("Heatmap metric", ["Clearing price (eCPM)", "Sell-through (fill rate)"],
                  horizontal=True, label_visibility="collapsed")

z, fmt, title = [], "", ""
piv = hm.pivot(index="cohort_name", columns="daypart",
               values="avg_ecpm" if metric.startswith("Clearing") else "fill_rate")
piv = piv.reindex(index=coh_order, columns=dp_order)
if metric.startswith("Clearing"):
    text = [[f"${v:.0f}" for v in row] for row in piv.values]
    hover = "%{y} · %{x}<br>eCPM $%{z:.2f}<extra></extra>"
    title = "Average clearing price (eCPM, USD) by cohort × daypart"
else:
    text = [[f"{v:.0%}" for v in row] for row in piv.values]
    hover = "%{y} · %{x}<br>Sell-through %{z:.1%}<extra></extra>"
    title = "Sell-through by cohort × daypart"

fig = go.Figure(go.Heatmap(
    z=piv.values, x=dp_labels, y=piv.index,
    colorscale=[[i / (len(theme.SEQ) - 1), c] for i, c in enumerate(theme.SEQ)],
    text=text, texttemplate="%{text}", textfont=dict(size=11),
    hovertemplate=hover, xgap=2, ygap=2, colorbar=dict(thickness=10, outlinewidth=0)))
fig.update_layout(title=title, height=460, yaxis=dict(autorange="reversed"))
st.plotly_chart(fig, use_container_width=True)

c1, c2 = st.columns([1.1, 1])
with c1:
    # price vs sell-through: the demand-inequality picture in one frame
    # alternate label positions by price rank so the labels don't collide
    pos_cycle = ["top center", "bottom center", "middle right", "middle left"]
    positions = [pos_cycle[i % len(pos_cycle)]
                 for i in inv.avg_ecpm.rank(method="first").astype(int)]
    fig = go.Figure(go.Scatter(
        x=inv.fill_rate, y=inv.avg_ecpm, mode="markers+text",
        marker=dict(size=np.sqrt(inv.ad_slots / inv.ad_slots.max()) * 34 + 8,
                    color=theme.CAT[0], opacity=0.85,
                    line=dict(width=2, color=theme.SURFACE)),
        text=inv.cohort_name.str.replace("Late-Night Low-Attention", "Late-Night", regex=False),
        textposition=positions, textfont=dict(size=10, color=theme.INK_2),
        hovertemplate="<b>%{text}</b><br>Sell-through %{x:.1%}<br>eCPM $%{y:.2f}<extra></extra>"))
    fig.update_layout(title="Price vs sell-through (bubble = slot supply)",
                      xaxis=dict(title="Sell-through", tickformat=".0%"),
                      yaxis=dict(title="Avg eCPM (USD)"), height=460)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    inv_u = inv.sort_values("unfilled_slots", ascending=True)
    fig = go.Figure(go.Bar(
        x=inv_u.unfilled_slots, y=inv_u.cohort_name, orientation="h",
        marker=dict(color=theme.CAT[4], cornerradius=4),
        text=[f"{v/1000:,.0f}k" for v in inv_u.unfilled_slots], textposition="outside",
        textfont=dict(color=theme.INK_2),
        hovertemplate="%{y}<br>%{x:,.0f} unfilled slots (90d)<extra></extra>"))
    fig.update_layout(title="Unsold ad slots by cohort (90d) — the availability picture",
                      height=460, bargap=0.35,
                      xaxis=dict(range=[0, inv_u.unfilled_slots.max() * 1.18]))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("**Cohort inventory detail**")
det = inv.copy()
det["status"] = [ui.status_chip(f) for f in det.fill_rate]
st.dataframe(
    det[["cohort_name", "status", "sessions", "ad_slots", "fill_rate", "unfilled_slots",
         "avg_ecpm", "campaigns_bidding", "completion_rate", "attention_index"]],
    hide_index=True, use_container_width=True,
    column_config={
        "cohort_name": "Cohort", "status": "Demand status",
        "sessions": st.column_config.NumberColumn("Sessions", format="%d"),
        "ad_slots": st.column_config.NumberColumn("Ad slots", format="%d"),
        "fill_rate": st.column_config.ProgressColumn("Sell-through", format="percent",
                                                     min_value=0, max_value=1),
        "unfilled_slots": st.column_config.NumberColumn("Unfilled", format="%d"),
        "avg_ecpm": st.column_config.NumberColumn("Avg eCPM", format="$%.2f"),
        "campaigns_bidding": st.column_config.NumberColumn("Campaigns bidding", format="%d"),
        "completion_rate": st.column_config.NumberColumn("Completion", format="percent"),
        "attention_index": st.column_config.NumberColumn("Attention idx", format="%.2f"),
    })
st.caption("Demand status: ▲ Hot ≥90% · ● Healthy ≥75% · ◆ Soft ≥60% · ▼ Cold <60% sell-through.")

db.show_sql("inventory_heatmap", "SQL: cohort × daypart heatmap")
db.show_sql("cohort_inventory", "SQL: cohort inventory health")
