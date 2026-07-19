"""Recommendation Engine — measured lift + price + availability → ranked actions."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analytics, db, theme, ui

MCP_TOOL_MANIFEST = """{
  "tools": [
    {
      "name": "propose_ad_load_change",
      "description": "Draft a proposed ad-load change for a session cohort. Does not apply the change -- creates a reviewable proposal only.",
      "input_schema": {
        "type": "object",
        "properties": {
          "cohort_name": {"type": "string"},
          "action": {"type": "string", "enum": ["SPIN_UP", "SPIN_DOWN"]},
          "load_multiplier": {"type": "number", "minimum": 0.5, "maximum": 1.5},
          "rationale": {"type": "string"}
        },
        "required": ["cohort_name", "action", "load_multiplier", "rationale"]
      }
    },
    {
      "name": "request_human_approval",
      "description": "Escalate a proposed change to a human approver before it can be applied.",
      "input_schema": {
        "type": "object",
        "properties": {
          "proposal_ref": {"type": "string"},
          "reason": {"type": "string"},
          "approver_role": {"type": "string", "enum": ["ads_ops_lead", "measurement_lead", "finance"]}
        },
        "required": ["proposal_ref", "reason"]
      }
    },
    {
      "name": "open_ops_ticket",
      "description": "Open a tracked ticket documenting the decision and its rationale.",
      "input_schema": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "description": {"type": "string"},
          "priority": {"type": "string", "enum": ["P1", "P2", "P3"]}
        },
        "required": ["title", "description"]
      }
    },
    {
      "name": "notify_stakeholders",
      "description": "Post a summary to a Slack channel or distribution list.",
      "input_schema": {
        "type": "object",
        "properties": {
          "channel": {"type": "string"},
          "message": {"type": "string"}
        },
        "required": ["channel", "message"]
      }
    }
  ]
}"""


def build_agent_handoff(rows: pd.DataFrame) -> str:
    """A prompt an MCP-connected ops agent could act on, generated from *today's*
    live recommendations rather than a static example. Escalation flags are
    computed here, not left for the agent to infer, since a deterministic
    guardrail belongs in code -- the agent's job is drafting and judgment calls
    on top of it, not deciding what counts as risky."""
    live = rows[rows.action != "HOLD"]
    lines = [
        "SYSTEM: You are the Ads Ops execution agent for Netflix's ad platform.",
        "Available MCP tools: propose_ad_load_change, request_human_approval, "
        "open_ops_ticket, notify_stakeholders.",
        "Never invent a cohort, multiplier, or rationale that isn't given to you below.",
        "",
        "GUARDRAILS:",
        "- Never change ad load directly -- always `propose_ad_load_change` first; "
        "it drafts, it doesn't apply.",
        "- If needs_human_approval=true below, call `request_human_approval` before "
        "proposing anything for that cohort.",
        "- Quote the `rationale` field verbatim in the ticket -- do not paraphrase away "
        "the eCPM/fill-rate evidence behind it.",
        "- Do not act on HOLD rows; they mean 'monitor', not 'no action needed'.",
        "",
        f"TASK: For each of the {len(live)} actionable cohorts below, call "
        "`propose_ad_load_change` (plus `request_human_approval` where flagged), then "
        "`open_ops_ticket` once summarizing all proposals, then `notify_stakeholders`.",
        "",
        "RECOMMENDATION ENGINE OUTPUT:",
    ]
    for r in live.itertuples():
        mult = 1.15 if r.action == "SPIN UP" else 0.85
        needs_approval = r.action == "SPIN DOWN" or (r.action == "SPIN UP" and r.attention_index < 0.5)
        lines.append(
            f'- action={r.action.replace(" ", "_")} cohort="{r.cohort_name}" '
            f"fill_rate={r.fill_rate:.0%} avg_ecpm=${r.avg_ecpm:.2f} "
            f"unfilled_slots={r.unfilled_slots:,.0f} suggested_multiplier={mult:.2f} "
            f"needs_human_approval={str(needs_approval).lower()}")
        lines.append(f"  rationale: {r.rationale}")
    return "\n".join(lines)

ui.page_header("Recommendation Engine",
               "Turns the measurement outputs into decisions: which cohorts an advertiser "
               "should buy (and how much room there is to buy them), where budget should "
               "move, which creative type to lean on, and which inventory the platform "
               "should spin up or down.")

inv = db.run_sql("cohort_inventory")
cells = db.run_sql("recommend_cells")
lift = analytics.add_lift_columns(db.run_sql("campaign_lift"))
adv = db.run_sql("advertiser_summary")

sel_name = st.selectbox("Advertiser", adv.advertiser_name, index=0)
arow = adv[adv.advertiser_name == sel_name].iloc[0]
scored = analytics.score_cohorts_for_category(cells, inv, arow.category)

st.subheader(f"1 · Where should {sel_name} buy? (inventory → advertiser matching)")
if scored.empty:
    st.info("Not enough measured data in this category.")
    st.stop()

best = scored.iloc[0]
st.markdown(
    f"**Top match: {best.cohort_name}** — measured {arow.category} lift "
    f"{best.lift_shrunk:+.0%} at \\${best.avg_ecpm:.0f} eCPM with "
    f"{best.unfilled_slots:,.0f} unsold slots available. Projected "
    f"**{best.projected_inc_conv_per_10k:,.0f} incremental conversions per \\$10k**.")

c1, c2 = st.columns([1.15, 1])
with c1:
    s = scored.sort_values("score")
    fig = go.Figure(go.Bar(
        x=s.score, y=s.cohort_name, orientation="h",
        marker=dict(color=theme.CAT[0], cornerradius=4),
        text=[f"{v:.0f}" for v in s.score], textposition="outside",
        textfont=dict(color=theme.INK_2),
        customdata=np.stack([s.lift_shrunk, s.avg_ecpm, s.unfilled_slots], axis=-1),
        hovertemplate="<b>%{y}</b><br>Score %{x:.0f}<br>Lift %{customdata[0]:+.1%} · "
                      "eCPM $%{customdata[1]:.0f}<br>%{customdata[2]:,.0f} slots open<extra></extra>"))
    fig.update_layout(title=f"Cohort match score for {arow.category} "
                            "(incremental efficiency × availability)",
                      height=440, bargap=0.35, xaxis=dict(range=[0, 118]))
    st.plotly_chart(fig, use_container_width=True)
with c2:
    st.dataframe(
        scored[["cohort_name", "score", "lift_shrunk", "avg_ecpm", "avg_frequency",
                "unfilled_slots", "projected_inc_conv_per_10k"]],
        hide_index=True, use_container_width=True, height=440,
        column_config={
            "cohort_name": "Cohort",
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100,
                                                     format="%.0f"),
            "lift_shrunk": st.column_config.NumberColumn("Lift (shrunk)", format="percent"),
            "avg_ecpm": st.column_config.NumberColumn("eCPM", format="$%.0f"),
            "avg_frequency": st.column_config.NumberColumn("Avg freq", format="%.1f"),
            "unfilled_slots": st.column_config.NumberColumn("Open slots", format="%d"),
            "projected_inc_conv_per_10k": st.column_config.NumberColumn(
                "Inc. conv / $10k", format="%.0f"),
        })
st.caption("Score = incremental conversions per media dollar (holdout-measured, shrunk toward "
           "the category-pooled lift when a cell is thin), scaled by open inventory. "
           "Small cells lean on the pooled estimate — the engine won't chase noise.")

st.divider()
st.subheader("2 · Budget reallocation")
spend = db.query("""
    SELECT p.cohort_id, c.cohort_name, SUM(p.ecpm_usd)/1000 AS spend_usd
    FROM fact_placement p
    JOIN dim_campaign cm USING (campaign_id)
    JOIN dim_cohort c    USING (cohort_id)
    WHERE cm.advertiser_id = ? AND p.is_holdout = 0
    GROUP BY 1, 2 ORDER BY spend_usd DESC""", (int(arow.advertiser_id),))
merged = spend.merge(scored[["cohort_name", "inc_conv_per_1k_usd", "score"]], on="cohort_name")
if len(merged) >= 2:
    frm, to = merged.iloc[merged.inc_conv_per_1k_usd.idxmin()], merged.iloc[merged.inc_conv_per_1k_usd.idxmax()]
    shift = 0.15 * frm.spend_usd
    delta_conv = shift / 1000 * (to.inc_conv_per_1k_usd - frm.inc_conv_per_1k_usd)
    st.markdown(
        f"Move **\\${shift:,.0f}** (15% of its {frm.cohort_name} spend) into "
        f"**{to.cohort_name}** → projected **{delta_conv:+,.0f} incremental conversions** "
        f"per 90 days at current prices.\n\n"
        f"- {frm.cohort_name}: {frm.inc_conv_per_1k_usd:.1f} inc. conv/\\$1k (saturating)\n"
        f"- {to.cohort_name}: {to.inc_conv_per_1k_usd:.1f} inc. conv/\\$1k (headroom)")
    fig = go.Figure(go.Bar(
        x=merged.sort_values("spend_usd").spend_usd,
        y=merged.sort_values("spend_usd").cohort_name, orientation="h",
        marker=dict(color=theme.CAT[0], cornerradius=4),
        customdata=merged.sort_values("spend_usd").inc_conv_per_1k_usd,
        text=[f"${v/1000:,.0f}k" for v in merged.sort_values("spend_usd").spend_usd],
        textposition="outside", textfont=dict(color=theme.INK_2),
        hovertemplate="%{y}<br>Spend $%{x:,.0f}<br>%{customdata:.1f} inc. conv/$1k<extra></extra>"))
    fig.update_layout(title=f"{sel_name} current 90-day spend by cohort", height=360,
                      bargap=0.35, xaxis=dict(range=[0, merged.spend_usd.max() * 1.2]))
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("3 · Creative type recommendation")
obj = (lift[lift.category == arow.category]
       .groupby("objective")
       .apply(lambda g: analytics.lift_with_ci(g.conv_treated.sum(), g.n_treated.sum(),
                                               g.conv_holdout.sum(), g.n_holdout.sum())["lift"],
              include_groups=False)
       .sort_values(ascending=False))
if not obj.empty:
    names = {"awareness": "Awareness", "direct_response": "Direct response",
             "click_to_learn_more": "Click-to-learn-more"}
    winner = names.get(obj.index[0], obj.index[0])
    parts = " · ".join(f"{names.get(k, k)}: {v:+.1%}" for k, v in obj.items())
    st.markdown(f"Pooled {arow.category} lift by creative objective — {parts}. "
                f"**Lead with {winner}** for this category; check this advertiser's own "
                f"A/B results on the A/B Testing page before locking rotation.")

st.divider()
st.subheader("4 · Platform inventory actions (spin up / spin down)")
actions = analytics.spin_actions(inv)
icon = {"SPIN UP": "▲", "SPIN DOWN": "▼", "HOLD": "●"}
for r in actions.itertuples():
    color = {"SPIN UP": theme.STATUS["good"], "SPIN DOWN": theme.STATUS["serious"],
             "HOLD": theme.MUTED}[r.action]
    st.markdown(
        f"<div style='border-left:3px solid {color}; padding:0.35rem 0.8rem; margin:0.3rem 0;"
        f"background:#1a1a19; border-radius:4px;'>"
        f"<span style='color:{color}; font-weight:700;'>{icon[r.action]} {r.action}</span> "
        f"<b>{r.cohort_name}</b><br>"
        f"<span style='color:#c3c2b7; font-size:0.88rem;'>{r.rationale}</span></div>",
        unsafe_allow_html=True)
st.caption("Try any of these levers live in the Cohort Control Console →")

st.divider()
st.subheader("5 · Make it agentic: hand off to an MCP-connected ops agent")
st.markdown(
    "Section 4's output is already shaped like a set of tool calls — a cohort, an action, "
    "a magnitude, and a rationale — which is what makes it plausible to hand to an "
    "autonomous agent instead of a human clicking through a dashboard. Below is an "
    "illustrative MCP tool manifest a 'Netflix AdOps' server might expose, and the exact "
    "prompt this page would generate from **today's live recommendations** to brief that "
    "agent — guardrails included.")

with st.expander("Illustrative MCP tool manifest (what the agent could call)"):
    st.code(MCP_TOOL_MANIFEST, language="json")
    st.caption("Illustrative only — no MCP server is actually connected here. This is the "
               "shape a real AdOps tool server would need to expose for an agent to act on "
               "these recommendations directly, rather than a human reading the cards above.")

actions_enriched = actions.merge(inv[["cohort_name", "attention_index"]], on="cohort_name")
st.code(build_agent_handoff(actions_enriched), language="text")
st.caption("Generated live from the Section 4 actions — not a static example; rerun the page "
           "with different data and this prompt changes with it. Point it at a real MCP "
           "server in place of the manifest above and this becomes an actual agent brief "
           "instead of a demonstration of one.")

db.show_sql("recommend_cells", "SQL: cohort × category cells behind the scores")
