"""Statistics and recommendation logic on top of the SQL layer.

Frequentist lift CIs use the delta method on the log rate ratio; Bayesian
readouts use Jeffreys Beta posteriors. The recommender turns measured
cohort-level lift, price, and unfilled supply into ranked, dollar-denominated
actions. The cohort simulator is a stylized supply/demand equilibrium with
stated elasticity assumptions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

Z95 = 1.959964

# --------------------------------------------------------------------- lift

def lift_with_ci(ct: float, nt: float, ch: float, nh: float) -> dict:
    """Relative lift (rt/rh - 1) with 95% CI via delta method on log ratio."""
    if min(nt, nh) == 0 or ch == 0 or ct == 0:
        return dict(lift=np.nan, lo=np.nan, hi=np.nan, p=np.nan, rt=np.nan, rh=np.nan)
    rt, rh = ct / nt, ch / nh
    log_rr = np.log(rt / rh)
    se = np.sqrt((1 - rt) / (rt * nt) + (1 - rh) / (rh * nh))
    lo, hi = np.exp(log_rr - Z95 * se) - 1, np.exp(log_rr + Z95 * se) - 1
    # two-proportion z-test on the absolute difference
    p_pool = (ct + ch) / (nt + nh)
    se_d = np.sqrt(p_pool * (1 - p_pool) * (1 / nt + 1 / nh))
    z = (rt - rh) / se_d if se_d > 0 else 0.0
    return dict(lift=rt / rh - 1, lo=lo, hi=hi, p=2 * stats.norm.sf(abs(z)), rt=rt, rh=rh)


def add_lift_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized lift_with_ci over a campaign_lift-shaped frame."""
    out = df.copy()
    res = [lift_with_ci(r.conv_treated, r.n_treated, r.conv_holdout, r.n_holdout)
           for r in df.itertuples()]
    for k in ("lift", "lo", "hi", "p", "rt", "rh"):
        out[k] = [r[k] for r in res]
    out["significant"] = (out.p < 0.05) & out.lift.notna()
    out["incremental_conversions"] = (out.rt - out.rh) * out.n_treated
    return out


def bayes_lift_samples(ct, nt, ch, nh, n=6000, seed=7) -> np.ndarray:
    """Posterior samples of relative lift from independent Jeffreys Beta posteriors."""
    rng = np.random.default_rng(seed)
    pt = rng.beta(ct + 0.5, nt - ct + 0.5, n)
    ph = rng.beta(ch + 0.5, nh - ch + 0.5, n)
    return pt / ph - 1


# --------------------------------------------------------------- elasticity

def saturation(f, amplitude, k):
    return amplitude * (1 - np.exp(-k * f))


def fit_frequency_response(freq_df: pd.DataFrame) -> dict:
    """Fit incremental-lift-by-frequency A*(1-exp(-kf)) for one category.

    freq_df: rows from frequency_response.sql for a single category. The fit
    target is the treated-minus-holdout conversion-rate gap per frequency
    bucket, which nets out the activity confound.
    """
    piv = freq_df.pivot_table(index="freq_bucket", columns="is_holdout",
                              values=["pairs", "converters"], aggfunc="sum")
    piv = piv.dropna()
    if piv.empty or (1 not in piv["pairs"].columns):
        return dict(ok=False)
    f = piv.index.values.astype(float)
    rt = piv["converters"][0] / piv["pairs"][0]
    rh = piv["converters"][1] / piv["pairs"][1]
    gap = (rt - rh).values
    w = np.minimum(piv["pairs"][0].values, piv["pairs"][1].values).astype(float)
    try:
        (amp, k), _ = optimize.curve_fit(
            saturation, f, gap, p0=[max(gap.max(), 1e-3), 0.6],
            sigma=1 / np.sqrt(np.maximum(w, 1)), bounds=([0, 0.05], [0.5, 5.0]), maxfev=5000)
    except Exception:
        return dict(ok=False)
    return dict(ok=True, f=f, gap=gap, rt=rt.values, rh=rh.values, pairs=w,
                amplitude=amp, k=k,
                curve_f=np.linspace(0.5, 10, 60),
                curve=saturation(np.linspace(0.5, 10, 60), amp, k))


# --------------------------------------------------------------- recommender

def score_cohorts_for_category(cells: pd.DataFrame, inventory: pd.DataFrame,
                               category: str) -> pd.DataFrame:
    """Rank cohorts for an advertiser category by incremental efficiency.

    Efficiency = incremental conversions per $1k of media, from measured
    treated-vs-holdout rates and the cell's clearing price. Small cells are
    shrunk toward the category-pooled lift (precision weighting).
    """
    cat_cells = cells[cells.category == category].copy()
    if cat_cells.empty:
        return cat_cells
    pooled = lift_with_ci(cat_cells.conv_treated.sum(), cat_cells.n_treated.sum(),
                          cat_cells.conv_holdout.sum(), cat_cells.n_holdout.sum())
    rows = []
    for r in cat_cells.itertuples():
        cell = lift_with_ci(r.conv_treated, r.n_treated, r.conv_holdout, r.n_holdout)
        if np.isnan(cell["lift"]):
            lift, rh = pooled["lift"], pooled["rh"]
        else:
            se_cell = (cell["hi"] - cell["lo"]) / (2 * Z95) or 1.0
            se_pool = (pooled["hi"] - pooled["lo"]) / (2 * Z95) or 1.0
            w = (1 / se_cell**2) / (1 / se_cell**2 + 1 / se_pool**2)
            lift = w * cell["lift"] + (1 - w) * pooled["lift"]
            rh = cell["rh"]
        inc_per_pair = rh * lift                       # incremental convs per exposed account
        inc_per_1k_imps = inc_per_pair / max(r.avg_frequency, 1e-6) * 1000
        inc_per_1k_usd = inc_per_1k_imps / max(r.avg_ecpm, 1e-6) * 1000
        rows.append(dict(cohort_id=r.cohort_id, measured_lift=cell["lift"], lift_shrunk=lift,
                         baseline_rate=rh, avg_ecpm=r.avg_ecpm, avg_frequency=r.avg_frequency,
                         n_treated=r.n_treated,
                         inc_conv_per_1k_usd=inc_per_1k_usd))
    out = pd.DataFrame(rows).merge(
        inventory[["cohort_id", "cohort_name", "fill_rate", "unfilled_slots", "attention_index"]],
        on="cohort_id")
    # availability-aware score: efficiency scaled by how much room there is to buy
    avail = np.clip(out.unfilled_slots / out.unfilled_slots.max(), 0.15, 1.0)
    eff = out.inc_conv_per_1k_usd.clip(lower=0)
    out["score"] = np.round(100 * (eff / max(eff.max(), 1e-9)) * (0.6 + 0.4 * avail), 1)
    out["projected_inc_conv_per_10k"] = np.round(out.inc_conv_per_1k_usd * 10, 1)
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def spin_actions(inventory: pd.DataFrame) -> pd.DataFrame:
    """Platform-level spin-up / spin-down calls from sell-through and price."""
    rows = []
    med_ecpm = inventory.avg_ecpm.median()
    for r in inventory.itertuples():
        extra_slots_day = r.ad_slots / 90 * 0.15
        if r.fill_rate >= 0.90:
            action, rationale = "SPIN UP", (
                f"Sell-through {r.fill_rate:.0%} with eCPM ${r.avg_ecpm:.0f} — demand is "
                f"clearing the book. +15% ad load ≈ {extra_slots_day:,.0f} slots/day, "
                f"≈ ${extra_slots_day * 0.9 * r.avg_ecpm / 1000 * 0.9:,.0f}/day incremental revenue "
                f"at modest price give-back.")
        elif r.fill_rate <= 0.62:
            action, rationale = "SPIN DOWN", (
                f"Sell-through {r.fill_rate:.0%} at eCPM ${r.avg_ecpm:.0f} (platform median "
                f"${med_ecpm:.0f}). Throttle ad load or repackage into performance bundles "
                f"before this inventory drags clearing prices down.")
        else:
            action, rationale = "HOLD", (
                f"Sell-through {r.fill_rate:.0%} is balanced; monitor weekly.")
        rows.append(dict(cohort_name=r.cohort_name, action=action, fill_rate=r.fill_rate,
                         avg_ecpm=r.avg_ecpm, unfilled_slots=r.unfilled_slots,
                         rationale=rationale))
    order = {"SPIN UP": 0, "SPIN DOWN": 1, "HOLD": 2}
    return (pd.DataFrame(rows).sort_values(["action", "fill_rate"],
            key=lambda s: s.map(order) if s.name == "action" else s, ascending=[True, False])
            .reset_index(drop=True))


# ---------------------------------------------------------------- simulator

# stylized elasticities, stated in the UI
PRICE_PASSTHROUGH = 0.45   # clearing price falls ~4.5% per +10% supply
DEMAND_ELASTICITY = 1.25   # quantity demanded rises ~12.5% per -10% price
CONV_SATURATION = 0.70     # incremental conversions scale sublinearly with imps

def simulate_ad_load(row, mult: float) -> dict:
    """Project cohort economics at ad-load multiplier `mult` (1.0 = today).

    Supply/demand equilibrium: more slots -> lower clearing price -> more
    quantity demanded; fill is demand/supply capped at 98.5%. Viewer-experience
    guardrail: completion decays with added load, faster for low-attention
    cohorts.
    """
    slots0, fill0, ecpm0 = row.ad_slots, row.fill_rate, row.avg_ecpm
    imps0 = slots0 * fill0
    rev0 = imps0 * ecpm0 / 1000

    slots1 = slots0 * mult
    ecpm1 = ecpm0 * mult ** (-PRICE_PASSTHROUGH)
    demand1 = imps0 * (ecpm1 / ecpm0) ** (-DEMAND_ELASTICITY)
    fill1 = min(0.985, demand1 / slots1)
    imps1 = slots1 * fill1
    rev1 = imps1 * ecpm1 / 1000

    completion_delta = -0.055 * (mult - 1) * (1.6 - row.attention_index)
    conv_mult = (imps1 / imps0) ** CONV_SATURATION if imps0 > 0 else 1.0
    return dict(
        slots=slots1, ecpm=ecpm1, fill=fill1, imps=imps1, revenue=rev1,
        d_revenue=rev1 - rev0, d_revenue_pct=rev1 / rev0 - 1 if rev0 else 0,
        d_imps_pct=imps1 / imps0 - 1 if imps0 else 0,
        d_ecpm_pct=ecpm1 / ecpm0 - 1,
        d_fill=fill1 - fill0,
        completion_delta=completion_delta,
        conv_mult=conv_mult,
        churn_flag=mult > 1.25 and row.attention_index < 0.5,
    )
