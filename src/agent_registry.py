"""The approved-analysis registry — the heart of the codified-analysis approach.

This is what the cover letter means by "limiting SQL/Python generation to
pre-approved parameters." Each entry is a fixed analysis: named SQL from
``sql/*.sql`` plus vetted functions from ``analytics.py``, with a small,
typed set of parameters (advertiser, category, cohort, metric) whose allowed
values are drawn from the live warehouse. The LLM's only job upstream is to
pick ONE analysis and fill those parameters from the enumerated options — it
never writes a query. The runners below are ordinary, reviewable, deterministic
Python; given the same parameters they always produce the same numbers.

Parameters are declared once, as data, in ``PARAMS``. The OpenAI tool schema,
each analysis's parameter subset, and the offline fallback's value-matching are
all derived from that single source — there is no hand-maintained copy to keep
in sync.

Each runner returns a `Result`: a number-grounded headline, a raw-number dict
for the LLM to summarize (and for the offline fallback to echo), an optional
table + column config, an optional Plotly figure, and the provenance (which SQL
and which functions ran, with the parameters that were bound).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats

from src import analytics, db, theme

TOOL_NAME = "run_measurement_analysis"


@dataclass
class Result:
    headline: str                       # number-grounded finding (deterministic)
    stats: dict                         # raw numbers, fed to the LLM summary
    bound_params: dict                  # the parameters actually used
    sql_names: list[str]                # approved SQL that ran
    python_fns: list[str]               # approved functions that ran
    table: pd.DataFrame | None = None
    table_config: dict | None = None
    figure: go.Figure | None = None
    notes: str = ""                     # e.g. a default that was applied


@dataclass
class Analysis:
    key: str
    label: str
    description: str                    # analytical description; params appended generatively
    params: list[str]                   # names of params this analysis reads (keys into PARAMS)
    example: str                        # a sample question
    run: object = field(repr=False)     # callable(enums, **params) -> Result


@dataclass
class Param:
    name: str
    enum_key: str                       # key into warehouse_enums()
    description: str                    # shown to the LLM in the tool schema


# Every parameter any analysis can take, declared once. The schema, the
# per-analysis subset (Analysis.params), and the offline value-matcher all read
# from here — add a parameter in one place and everything downstream follows.
PARAMS: dict[str, Param] = {
    "advertiser_name": Param("advertiser_name", "advertiser_name",
                             "Advertiser to filter to, when the question names one."),
    "category": Param("category", "category",
                      "Advertiser category (e.g. Finance, Beverage, Gaming)."),
    "cohort_name": Param("cohort_name", "cohort_name",
                         "Session cohort, when the question names one."),
    "metric": Param("metric", "metric",
                    "Which inventory metric to lead with (sell_through or clearing_price)."),
}


def _st():
    import streamlit as st
    return st


# ---------------------------------------------------------------- enums

def warehouse_enums() -> dict:
    """Allowed parameter values, pulled live from the warehouse so the LLM can
    only ever pick values that actually exist."""
    adv = db.run_sql("advertiser_summary")
    inv = db.run_sql("cohort_inventory")
    return {
        "advertiser_name": adv.advertiser_name.tolist(),
        "category": sorted(adv.category.unique().tolist()),
        "cohort_name": inv.cohort_name.tolist(),
        "metric": ["sell_through", "clearing_price"],
    }


# ---------------------------------------------------------------- helpers

def _wp_lift() -> pd.DataFrame:
    lift = analytics.add_lift_columns(db.run_sql("campaign_lift"))
    return lift[(lift.n_treated >= 1500) & (lift.conv_holdout >= 10)].copy()


def _ci_dot_figure(df: pd.DataFrame, title: str) -> go.Figure:
    d = df.nlargest(min(12, len(df)), "n_treated").sort_values("lift")
    colors = [theme.CAT[0] if s else theme.MUTED for s in d.significant]
    fig = go.Figure()
    fig.add_vline(x=0, line=dict(color=theme.BASELINE, width=1))
    fig.add_trace(go.Scatter(
        x=d.lift, y=d.campaign_name, mode="markers",
        error_x=dict(array=d.hi - d.lift, arrayminus=d.lift - d.lo,
                     color=theme.MUTED, thickness=1.5, width=3),
        marker=dict(size=9, color=colors),
        hovertemplate="<b>%{y}</b><br>Lift %{x:+.1%}<extra></extra>"))
    fig.update_layout(title=title, height=420, showlegend=False,
                      xaxis=dict(tickformat="+.0%", title="Relative lift vs holdout"),
                      yaxis_title=None)
    return fig


# ---------------------------------------------------------------- runners

def run_incrementality(enums, advertiser_name=None, **_) -> Result:
    wp = _wp_lift()
    notes = ""
    subset = wp
    if advertiser_name:
        cand = wp[wp.advertiser_name == advertiser_name]
        if cand.empty:
            notes = (f"No well-powered campaigns for “{advertiser_name}”; "
                     "showing the full well-powered portfolio instead.")
            advertiser_name = None
        else:
            subset = cand
    row = subset.nlargest(1, "n_treated").iloc[0]
    samples = analytics.bayes_lift_samples(row.conv_treated, row.n_treated,
                                           row.conv_holdout, row.n_holdout)
    p_pos = float((samples > 0).mean())
    scope = advertiser_name or "the well-powered portfolio"
    headline = (f"{row.campaign_name}: {row.lift:+.0%} measured lift "
                f"({'significant' if row.significant else 'not significant'}, p={row.p:.3f}).")
    stats_d = {
        "scope": scope,
        "headline_campaign": row.campaign_name,
        "advertiser": row.advertiser_name,
        "category": row.category,
        "objective": row.objective,
        "measured_lift": round(float(row.lift), 4),
        "ci95": [round(float(row.lo), 4), round(float(row.hi), 4)],
        "p_value": round(float(row.p), 4),
        "significant_at_0.05": bool(row.significant),
        "prob_true_lift_positive": round(p_pos, 3),
        "n_treated": int(row.n_treated),
        "n_holdout": int(row.n_holdout),
        "conv_rate_treated": round(float(row.rt), 4),
        "conv_rate_holdout": round(float(row.rh), 4),
        "incremental_conversions": int(max(row.incremental_conversions, 0)),
        "portfolio_median_lift": round(float(subset.lift.median()), 4),
        "n_campaigns_in_scope": int(len(subset)),
        "n_significant_positive": int((subset.significant & (subset.lift > 0)).sum()),
    }
    table = subset.sort_values("n_treated", ascending=False)[
        ["campaign_name", "lift", "lo", "hi", "p", "significant", "n_treated"]].head(20)
    _st_ = _st()
    cfg = {
        "campaign_name": "Campaign",
        "lift": _st_.column_config.NumberColumn("Lift", format="percent"),
        "lo": _st_.column_config.NumberColumn("CI low", format="percent"),
        "hi": _st_.column_config.NumberColumn("CI high", format="percent"),
        "p": _st_.column_config.NumberColumn("p-value", format="%.3f"),
        "significant": _st_.column_config.CheckboxColumn("Sig."),
        "n_treated": _st_.column_config.NumberColumn("n treated", format="%d"),
    }
    return Result(headline, stats_d,
                  {"advertiser_name": advertiser_name}, ["campaign_lift"],
                  ["analytics.add_lift_columns", "analytics.lift_with_ci",
                   "analytics.bayes_lift_samples"],
                  table=table, table_config=cfg,
                  figure=_ci_dot_figure(subset, f"Lift with 95% CI — {scope}"),
                  notes=notes)


def run_inventory_demand(enums, metric="sell_through", **_) -> Result:
    inv = db.run_sql("cohort_inventory")
    plat_fill = float(inv.slots_filled.sum() / inv.ad_slots.sum())
    hot = inv.nlargest(1, "fill_rate").iloc[0]
    cold = inv.nsmallest(1, "fill_rate").iloc[0]
    unsold = inv.nlargest(1, "unfilled_slots").iloc[0]
    headline = (f"Platform sell-through {plat_fill:.0%}. Hottest: {hot.cohort_name} "
                f"({hot.fill_rate:.0%} at ${hot.avg_ecpm:.0f} eCPM); softest: "
                f"{cold.cohort_name} ({cold.fill_rate:.0%}). Most spin-up room: "
                f"{unsold.cohort_name} ({unsold.unfilled_slots:,.0f} unsold slots).")
    stats_d = {
        "metric_requested": metric,
        "platform_sell_through": round(plat_fill, 4),
        "n_cohorts": int(len(inv)),
        "hottest_cohort": hot.cohort_name,
        "hottest_fill_rate": round(float(hot.fill_rate), 4),
        "hottest_ecpm": round(float(hot.avg_ecpm), 2),
        "softest_cohort": cold.cohort_name,
        "softest_fill_rate": round(float(cold.fill_rate), 4),
        "most_unsold_cohort": unsold.cohort_name,
        "most_unsold_slots": int(unsold.unfilled_slots),
        "ecpm_range": [round(float(inv.avg_ecpm.min()), 2), round(float(inv.avg_ecpm.max()), 2)],
    }
    table = inv.sort_values("fill_rate", ascending=False)[
        ["cohort_name", "fill_rate", "avg_ecpm", "unfilled_slots", "campaigns_bidding"]]
    _st_ = _st()
    cfg = {
        "cohort_name": "Cohort",
        "fill_rate": _st_.column_config.ProgressColumn("Sell-through", format="percent",
                                                       min_value=0, max_value=1),
        "avg_ecpm": _st_.column_config.NumberColumn("Avg eCPM", format="$%.2f"),
        "unfilled_slots": _st_.column_config.NumberColumn("Unfilled", format="%d"),
        "campaigns_bidding": _st_.column_config.NumberColumn("Bidders", format="%d"),
    }
    color = theme.CAT[0] if metric == "sell_through" else theme.CAT[3]
    yv = "fill_rate" if metric == "sell_through" else "avg_ecpm"
    s = inv.sort_values(yv)
    txt = ([f"{v:.0%}" for v in s[yv]] if metric == "sell_through"
           else [f"${v:.0f}" for v in s[yv]])
    fig = go.Figure(go.Bar(x=s[yv], y=s.cohort_name, orientation="h",
                           marker=dict(color=color, cornerradius=4),
                           text=txt, textposition="outside", textfont=dict(color=theme.INK_2)))
    ttl = ("Sell-through by cohort" if metric == "sell_through"
           else "Clearing price (eCPM) by cohort")
    fig.update_layout(title=ttl, height=440, bargap=0.35,
                      xaxis=dict(tickformat=".0%" if metric == "sell_through" else None,
                                 range=[0, s[yv].max() * 1.18]))
    return Result(headline, stats_d, {"metric": metric},
                  ["cohort_inventory"], [], table=table, table_config=cfg, figure=fig)


def run_frequency_elasticity(enums, category=None, **_) -> Result:
    freq = db.run_sql("frequency_response")
    notes = ""
    if not category or category not in freq.category.unique():
        counts = freq.groupby("category").pairs.sum()
        category = counts.idxmax()
        notes = f"No category specified; used the best-powered category (“{category}”)."
    fit = analytics.fit_frequency_response(freq[freq.category == category])
    if not fit.get("ok"):
        stats_d = {"category": category, "fit": "insufficient data"}
        return Result(f"Not enough matched frequency data in {category} for a stable fit.",
                      stats_d, {"category": category}, ["frequency_response"],
                      ["analytics.fit_frequency_response"], notes=notes)
    half_sat = float(np.log(2) / fit["k"])
    practical_cap = 3 * half_sat
    headline = (f"{category}: incremental lift saturates as A·(1−e^−k·f) with "
                f"amplitude {fit['amplitude']:.1%}, k={fit['k']:.2f}. "
                f"~50% of achievable lift by {half_sat:.1f} exposures; "
                f"practical cap ≈ {practical_cap:.0f}.")
    stats_d = {
        "category": category,
        "saturation_amplitude": round(float(fit["amplitude"]), 4),
        "rate_constant_k": round(float(fit["k"]), 3),
        "half_saturation_frequency": round(half_sat, 2),
        "practical_frequency_cap": round(practical_cap, 1),
    }
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fit["f"], y=fit["gap"], mode="markers", name="Observed gap",
                             marker=dict(size=np.clip(np.sqrt(fit["pairs"]) / 8, 6, 18),
                                         color=theme.CAT[0]),
                             hovertemplate="f=%{x:.0f} · incremental %{y:.2%}<extra></extra>"))
    fig.add_trace(go.Scatter(x=fit["curve_f"], y=fit["curve"], mode="lines",
                             name="Fitted saturation",
                             line=dict(width=2, color=theme.CAT[3], dash="dash")))
    fig.update_layout(title=f"Incremental rate vs frequency — {category}", height=400,
                      xaxis=dict(title="Exposures per account", dtick=1),
                      yaxis=dict(tickformat=".1%", title="Treated − holdout conv rate"),
                      legend=dict(orientation="h", y=1.02, yanchor="bottom"))
    return Result(headline, stats_d, {"category": category},
                  ["frequency_response"], ["analytics.fit_frequency_response"],
                  figure=fig, notes=notes)


def _arm_stats(g: pd.DataFrame) -> pd.Series:
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
        rate_a=ra, rate_b=rb, imps_a=na, imps_b=nb,
        delta=rb / ra - 1 if ra else np.nan, p=p, significant=p < 0.05))


def run_ab_test(enums, advertiser_name=None, **_) -> Result:
    ab = db.run_sql("ab_results")
    tests = ab.groupby("test_id").apply(_arm_stats, include_groups=False).reset_index()
    notes = ""
    subset = tests
    if advertiser_name:
        cand = tests[tests.advertiser == advertiser_name]
        if cand.empty:
            notes = f"No creative tests for “{advertiser_name}”; showing all tests."
            advertiser_name = None
        else:
            subset = cand
    t = subset.sort_values("p").iloc[0]                 # most conclusive
    winner = "B" if t.delta > 0 else "A"
    wname = t.creative_b if t.delta > 0 else t.creative_a
    headline = (f"{t.campaign}: arm B vs A on {t.metric} is "
                f"{t.delta:+.1%} (p={t.p:.3f}, "
                f"{'significant — ship arm ' + winner if t.significant else 'not significant'}).")
    stats_d = {
        "scope": advertiser_name or "all advertisers",
        "n_tests": int(len(subset)),
        "n_significant": int(subset.significant.sum()),
        "headline_test": {"advertiser": t.advertiser, "campaign": t.campaign,
                          "metric": t.metric, "rate_a": round(float(t.rate_a), 4),
                          "rate_b": round(float(t.rate_b), 4),
                          "delta_b_vs_a": round(float(t.delta), 4),
                          "p_value": round(float(t.p), 4),
                          "significant": bool(t.significant),
                          "winner_arm": winner, "winner_creative": wname},
    }
    table = subset.sort_values("p")[
        ["advertiser", "campaign", "metric", "rate_a", "rate_b", "delta", "p", "significant"]]
    _st_ = _st()
    cfg = {
        "advertiser": "Advertiser", "campaign": "Campaign", "metric": "Metric",
        "rate_a": _st_.column_config.NumberColumn("Rate A", format="percent"),
        "rate_b": _st_.column_config.NumberColumn("Rate B", format="percent"),
        "delta": _st_.column_config.NumberColumn("Δ B vs A", format="percent"),
        "p": _st_.column_config.NumberColumn("p-value", format="%.3f"),
        "significant": _st_.column_config.CheckboxColumn("Sig."),
    }
    names = [f"A · {t.creative_a}", f"B · {t.creative_b}"]
    rates = [t.rate_a, t.rate_b]
    errs = [analytics.Z95 * np.sqrt(r * (1 - r) / n) for r, n in zip(rates, [t.imps_a, t.imps_b])]
    fig = go.Figure(go.Bar(x=names, y=rates,
                           error_y=dict(array=errs, color=theme.MUTED, thickness=1.5),
                           marker=dict(color=[theme.CAT[0], theme.CAT[2]], cornerradius=4),
                           width=0.45, text=[f"{r:.2%}" for r in rates],
                           textposition="outside", textfont=dict(color=theme.INK_2)))
    fig.update_layout(title=f"{t.metric.replace('_', ' ').title()} by arm (95% CI)",
                      height=380, showlegend=False, bargap=0.4,
                      yaxis=dict(tickformat=".1%", range=[0, max(rates) * 1.35]))
    return Result(headline, stats_d, {"advertiser_name": advertiser_name},
                  ["ab_results"], ["scipy two-proportion z-test"],
                  table=table, table_config=cfg, figure=fig, notes=notes)


def run_cohort_recommendation(enums, advertiser_name=None, **_) -> Result:
    adv = db.run_sql("advertiser_summary")
    notes = ""
    if not advertiser_name or advertiser_name not in adv.advertiser_name.values:
        advertiser_name = adv.iloc[0].advertiser_name
        notes = f"No advertiser specified; used the top spender (“{advertiser_name}”)."
    arow = adv[adv.advertiser_name == advertiser_name].iloc[0]
    cells = db.run_sql("recommend_cells")
    inv = db.run_sql("cohort_inventory")
    scored = analytics.score_cohorts_for_category(cells, inv, arow.category)
    if scored.empty:
        return Result(f"Not enough measured data in the {arow.category} category.",
                      {"advertiser": advertiser_name, "category": arow.category},
                      {"advertiser_name": advertiser_name},
                      ["recommend_cells", "cohort_inventory"],
                      ["analytics.score_cohorts_for_category"], notes=notes)
    best = scored.iloc[0]
    headline = (f"For {advertiser_name} ({arow.category}), the top cohort is "
                f"{best.cohort_name}: {best.lift_shrunk:+.0%} measured lift at "
                f"${best.avg_ecpm:.0f} eCPM, {best.unfilled_slots:,.0f} open slots — "
                f"projected {best.projected_inc_conv_per_10k:,.0f} incremental conv. per $10k.")
    stats_d = {
        "advertiser": advertiser_name,
        "category": arow.category,
        "top_cohort": best.cohort_name,
        "top_cohort_lift": round(float(best.lift_shrunk), 4),
        "top_cohort_ecpm": round(float(best.avg_ecpm), 2),
        "top_cohort_open_slots": int(best.unfilled_slots),
        "projected_inc_conv_per_10k": round(float(best.projected_inc_conv_per_10k), 1),
        "n_cohorts_scored": int(len(scored)),
        "runner_up": scored.iloc[1].cohort_name if len(scored) > 1 else None,
    }
    table = scored[["cohort_name", "score", "lift_shrunk", "avg_ecpm",
                    "unfilled_slots", "projected_inc_conv_per_10k"]]
    _st_ = _st()
    cfg = {
        "cohort_name": "Cohort",
        "score": _st_.column_config.ProgressColumn("Score", min_value=0, max_value=100,
                                                   format="%.0f"),
        "lift_shrunk": _st_.column_config.NumberColumn("Lift (shrunk)", format="percent"),
        "avg_ecpm": _st_.column_config.NumberColumn("eCPM", format="$%.0f"),
        "unfilled_slots": _st_.column_config.NumberColumn("Open slots", format="%d"),
        "projected_inc_conv_per_10k": _st_.column_config.NumberColumn("Inc. conv / $10k",
                                                                      format="%.0f"),
    }
    s = scored.sort_values("score")
    fig = go.Figure(go.Bar(x=s.score, y=s.cohort_name, orientation="h",
                           marker=dict(color=theme.CAT[0], cornerradius=4),
                           text=[f"{v:.0f}" for v in s.score], textposition="outside",
                           textfont=dict(color=theme.INK_2)))
    fig.update_layout(title=f"Cohort match score for {arow.category}", height=440,
                      bargap=0.35, xaxis=dict(range=[0, 118]))
    return Result(headline, stats_d, {"advertiser_name": advertiser_name},
                  ["recommend_cells", "cohort_inventory"],
                  ["analytics.score_cohorts_for_category", "analytics.lift_with_ci"],
                  table=table, table_config=cfg, figure=fig, notes=notes)


# ---------------------------------------------------------------- registry

ANALYSES: dict[str, Analysis] = {
    a.key: a for a in [
        Analysis("incrementality", "Campaign incrementality (ghost-ads lift)",
                 "Is a campaign or advertiser driving incremental conversions? Returns "
                 "holdout-measured lift with a 95% CI, p-value, and the probability the "
                 "true lift is positive.",
                 ["advertiser_name"],
                 "Is Coca-Cola's advertising actually working?", run_incrementality),
        Analysis("inventory_demand", "Inventory demand & sell-through",
                 "Where is ad demand strongest and which inventory is undersold? Returns "
                 "sell-through, clearing price (eCPM), and unfilled slots by cohort.",
                 ["metric"],
                 "Which cohorts are underselling and where's the spin-up room?",
                 run_inventory_demand),
        Analysis("frequency_elasticity", "Frequency elasticity (saturation)",
                 "What's the optimal exposure frequency for a category before returns "
                 "saturate? Fits the incremental-lift-by-frequency curve and reports the "
                 "half-saturation frequency.",
                 ["category"],
                 "How many times should we show a Finance ad before it stops paying off?",
                 run_frequency_elasticity),
        Analysis("ab_test", "Creative A/B test readout",
                 "Which creative won a head-to-head A/B test? Returns per-arm rates, the "
                 "delta, a two-proportion p-value, and a ship recommendation.",
                 ["advertiser_name"],
                 "Which creative won for DoorDash?", run_ab_test),
        Analysis("cohort_recommendation", "Cohort buy recommendation",
                 "Which cohorts should an advertiser buy? Ranks cohorts by incremental "
                 "conversions per media dollar (holdout-measured, shrunk) scaled by "
                 "availability.",
                 ["advertiser_name"],
                 "Where should PlayStation spend its next $10k?", run_cohort_recommendation),
    ]
}


# ---------------------------------------------------------------- tool schema

def build_tool_schema(enums: dict) -> dict:
    """OpenAI function schema, generated from the registry. analysis_type and
    every parameter are constrained to enumerated values (from ANALYSES / PARAMS
    / the warehouse), so the model selects — it never authors."""
    props = {"analysis_type": {"type": "string", "enum": list(ANALYSES),
                               "description": "Which approved analysis to run."}}
    for name, p in PARAMS.items():
        props[name] = {"type": "string", "enum": enums[p.enum_key], "description": p.description}
    props["intent"] = {"type": "string",
                       "description": "One-sentence restatement of the user's question."}
    analysis_lines = "; ".join(
        f"{k} = {a.description} [params: {', '.join(a.params) if a.params else 'none'}]"
        for k, a in ANALYSES.items())
    return {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": ("Route the question to exactly one approved analysis and select its "
                            "parameters from the enumerated values. Never author SQL or Python. "
                            "Analyses: " + analysis_lines),
            "parameters": {"type": "object", "properties": props,
                           "required": ["analysis_type", "intent"]},
        },
    }


# ---------------------------------------------------------------- offline fallback

def fallback_summary(res: Result) -> str:
    """Deterministic stand-in for the LLM summary when no key is configured:
    the number-grounded headline the analysis already produced."""
    return res.headline


# Minimal keyword router — a safety net only, used when no LLM is configured.
# The LLM is the real semantic layer; this exists so the page still runs offline.
_FALLBACK_ROUTES = [
    ("cohort_recommendation", ("recommend", "should buy", "should spend", "where should",
                               "budget", "next $")),
    ("frequency_elasticity", ("frequency", "how many times", "how often", "saturat")),
    ("ab_test", ("a/b", "creative", "which ad", "which creative", "winner")),
    ("inventory_demand", ("inventory", "sell-through", "undersell", "unsold", "spin",
                          "clearing price", "ecpm", "daypart")),
    ("incrementality", ("lift", "incremental", "working", "causal", "holdout")),
]


def resolve_deterministic(query: str, enums: dict) -> dict:
    """Offline router used only when no LLM key is configured. Same output shape
    as the LLM's structured call: {analysis_type, <params>, intent}. Parameter
    values are matched literally against the warehouse enums (underscores read as
    spaces), so it stays in sync with PARAMS with no per-value special cases."""
    q = query.lower()
    analysis = next((key for key, kws in _FALLBACK_ROUTES if any(k in q for k in kws)),
                    "incrementality")
    args = {"analysis_type": analysis, "intent": f"(offline keyword match) {query.strip()}"}
    for name, p in PARAMS.items():
        match = next((v for v in enums[p.enum_key] if v.replace("_", " ").lower() in q), None)
        if match is not None:
            args[name] = match
    return args
