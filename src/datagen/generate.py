"""Seeded synthetic data generator for the Ads Measurement Console.

Builds the entire DuckDB warehouse (~1M placement rows) from a fixed seed in
~15-30s. Every effect the dashboard "discovers" — incrementality, elasticity,
demand inequality across cohorts, creative A/B deltas — is planted here as
ground truth, so the estimators on the analysis pages can be checked against
what was actually simulated (see sim_* tables).

Design notes
- Ghost-ads holdout: per (account, campaign), a deterministic 10% hash bucket
  wins the auction but has the ad suppressed. Ghost impressions are logged in
  fact_placement with is_holdout=1 and book no revenue.
- Conversions follow p = p0 * (1 + L * (1 - exp(-k * f))) for treated accounts
  (L = campaign true lift, f = exposure frequency) and p0 for holdouts, which
  gives both measurable lift and diminishing returns to frequency.
- No PII anywhere: accounts are opaque integer ids with a household id.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import time

import duckdb
import numpy as np
import pandas as pd

from src.datagen import catalog as cat

SEED = 42
N_ACCOUNTS = 25_000
N_HOUSEHOLDS = 17_000
N_SESSIONS = 220_000
WINDOW_DAYS = 90
HOLDOUT_PCT = 20  # ghost-ads holdout share per (account, campaign)
CONV_SCALE = 3.5  # scales category baseline conversion rates

REGIONS = ["US", "CA", "UK", "AU", "BR", "MX", "DE", "JP"]
REGION_W = [0.42, 0.07, 0.12, 0.05, 0.10, 0.08, 0.09, 0.07]
DEVICES = ["tv", "mobile", "tablet", "desktop"]
DEVICE_W = [0.71, 0.14, 0.07, 0.08]

COHORT_GENRES = {
    1: ["Sitcom Rerun", "Action", "Dating Reality"], 2: ["Limited Series", "Drama", "Period Piece"],
    3: ["Thriller", "Fantasy", "Drama"], 4: ["Animated Family", "Adventure", "Game Show"],
    5: ["Sitcom Rerun", "Comfort Drama"], 6: ["True Crime", "Docuseries"],
    7: ["Dating Reality", "Sitcom Rerun", "Talk"], 8: ["Competition Reality", "Dating Reality"],
    9: ["International Film", "Foreign Drama"], 10: ["Anime", "Animation"],
    11: ["Sports Docuseries", "Competition"], 12: ["Nature Doc", "Cooking", "Ambient"],
}

GENERIC_CONCEPTS = [
    "Hero Spot", "Testimonial", "Product Demo", "Offer Countdown", "Brand Anthem",
    "How-It-Works", "Founder Story", "UGC Mashup", "Seasonal Refresh", "Retail Moment",
]


def _hash_bucket(a: np.ndarray, b: np.ndarray, mod: int) -> np.ndarray:
    """Deterministic pseudo-random bucket from two id arrays (holdout / AB arms)."""
    return ((a.astype(np.int64) * 1_000_003 + b.astype(np.int64) * 7_919) * 2_654_435_761 % 2**31) % mod


def build(db_path: str, progress=None) -> None:
    t0 = time.time()
    rng = np.random.default_rng(SEED)

    def note(msg):
        if progress:
            progress(msg)

    end_date = dt.date.today() - dt.timedelta(days=1)
    dates = pd.to_datetime([end_date - dt.timedelta(days=i) for i in range(WINDOW_DAYS)][::-1])

    # ------------------------------------------------------------------ dims
    note("Building advertisers, campaigns & creatives…")
    adv = pd.DataFrame(cat.ADVERTISERS, columns=["advertiser_name", "category"])
    adv["advertiser_id"] = np.arange(1, len(adv) + 1)
    # Tier split ~20% AAA / ~35% AA / ~45% A, proportional to the roster size
    # so it holds whether there are 20 advertisers or 100.
    n_adv = len(adv)
    tier_draw = rng.permutation(n_adv)
    adv["tier"] = np.select(
        [tier_draw < round(0.20 * n_adv), tier_draw < round(0.55 * n_adv)],
        ["AAA", "AA"], "A")

    ctype = pd.DataFrame(cat.CREATIVE_TYPES, columns=["creative_type_id", "creative_type", "description", "cpm_mult"])

    dr_cats = {"Finance", "Insurance", "Marketplace", "Gaming", "QSR", "Retail", "Telecom"}
    brand_cats = {"Beverage", "CPG", "Auto", "Apparel", "Entertainment", "Food"}
    camp_rows, creative_rows = [], []
    camp_id, cr_id = 0, 0
    tier_budget = {"AAA": 950_000, "AA": 430_000, "A": 190_000}
    for a in adv.itertuples():
        n_camp = int(rng.integers(2, 6)) if a.tier != "A" else int(rng.integers(2, 4))
        names = rng.choice(cat.CAMPAIGN_NAME_TEMPLATES, size=n_camp, replace=False)
        famous = list(cat.FAMOUS_CREATIVES.get(a.advertiser_name, []))
        if a.category in dr_cats:
            obj_w = [0.25, 0.50, 0.25]
        elif a.category in brand_cats:
            obj_w = [0.55, 0.20, 0.25]
        else:
            obj_w = [0.40, 0.30, 0.30]
        for j in range(n_camp):
            camp_id += 1
            objective = int(rng.choice([1, 2, 3], p=obj_w))
            budget = float(np.round(tier_budget[a.tier] * rng.lognormal(0, 0.45) / n_camp, -3))
            camp_rows.append((camp_id, a.advertiser_id, f"{a.advertiser_name} · {names[j]}",
                              objective, str(dates[0].date()), str(end_date), budget))
            n_cr = int(rng.integers(2, 4))
            for c in range(n_cr):
                cr_id += 1
                if famous:
                    cname = famous.pop(0)
                else:
                    concept = GENERIC_CONCEPTS[int(rng.integers(len(GENERIC_CONCEPTS)))]
                    cname = f"{concept} '{names[j].split()[-1]}'"
                # first creative carries the campaign objective; extras may vary
                ct = objective if c == 0 or rng.random() < 0.7 else int(rng.integers(1, 4))
                dur = int(rng.choice([15, 30, 60], p=[0.55, 0.40, 0.05]))
                creative_rows.append((cr_id, camp_id, ct, f"{cname} :{dur}", dur))

    camp = pd.DataFrame(camp_rows, columns=["campaign_id", "advertiser_id", "campaign_name",
                                            "objective_type_id", "start_date", "end_date", "budget_usd"])
    creative = pd.DataFrame(creative_rows, columns=["creative_id", "campaign_id", "creative_type_id",
                                                    "creative_name", "duration_s"])

    coh = pd.DataFrame(cat.COHORTS, columns=["cohort_id", "cohort_name", "description", "supply_share",
                                             "attention_index", "demand_index", "ad_load_pods_per_hr", "cpm_multiplier"])

    # planted campaign-level ground truth
    n_camp_total = len(camp)
    lift = rng.lognormal(np.log(0.22), 0.5, n_camp_total)
    null_mask = rng.random(n_camp_total) < 0.15
    lift[null_mask] = rng.normal(0.0, 0.015, null_mask.sum())
    obj_adj = np.select([camp.objective_type_id == 2, camp.objective_type_id == 1], [1.30, 0.80], 1.0)
    truth = pd.DataFrame({
        "campaign_id": camp.campaign_id,
        "true_lift": np.round(np.clip(lift * obj_adj, -0.05, 1.2), 4),
        "elasticity_k": np.round(rng.uniform(0.5, 1.2, n_camp_total), 3),
    })

    # ------------------------------------------------------------------ accounts
    note("Creating anonymized accounts & households…")
    acct = pd.DataFrame({
        "account_id": np.arange(1, N_ACCOUNTS + 1),
        "household_id": rng.integers(1, N_HOUSEHOLDS + 1, N_ACCOUNTS),
        "primary_cohort_id": rng.choice(coh.cohort_id, N_ACCOUNTS, p=coh.supply_share),
        "region": rng.choice(REGIONS, N_ACCOUNTS, p=REGION_W),
        "tenure_months": rng.integers(1, 44, N_ACCOUNTS),
    })
    acct["plan"] = "standard_with_ads"

    # ------------------------------------------------------------------ sessions
    note(f"Simulating {N_SESSIONS:,} viewing sessions…")
    activity = rng.lognormal(0, 0.9, N_ACCOUNTS)
    a_idx = rng.choice(N_ACCOUNTS, N_SESSIONS, p=activity / activity.sum())
    s_account = acct.account_id.values[a_idx]
    s_cohort = acct.primary_cohort_id.values[a_idx].copy()
    drift = rng.random(N_SESSIONS) < 0.12
    s_cohort[drift] = rng.choice(coh.cohort_id, drift.sum())

    dow = dates.dayofweek.values
    day_w = (1.0 + 0.28 * np.isin(dow, [4, 5, 6])) * np.linspace(0.92, 1.08, WINDOW_DAYS)
    s_date_i = rng.choice(WINDOW_DAYS, N_SESSIONS, p=day_w / day_w.sum())

    dp_mix = np.array([cat.COHORT_DAYPART_MIX[c] for c in coh.cohort_id])
    s_daypart = np.empty(N_SESSIONS, dtype=object)
    for i, c in enumerate(coh.cohort_id.values):
        m = s_cohort == c
        s_daypart[m] = rng.choice(cat.DAYPARTS, m.sum(), p=dp_mix[i])

    dur_mean = {1: 71, 2: 49, 3: 120, 4: 60, 5: 41, 6: 53, 7: 34, 8: 45, 9: 83, 10: 38, 11: 56, 12: 90}
    mean_arr = np.vectorize(dur_mean.get)(s_cohort).astype(float)
    s_duration = np.clip(rng.gamma(3.0, mean_arr / 3.0), 8, 420)

    ad_load = coh.set_index("cohort_id").ad_load_pods_per_hr
    s_pods = rng.poisson(np.maximum(s_duration / 60.0 * ad_load.reindex(s_cohort).values, 0.4))
    s_slots = s_pods * 2

    demand_idx = coh.set_index("cohort_id").demand_index.reindex(s_cohort).values
    dp_demand = pd.Series(cat.DAYPART_DEMAND).reindex(s_daypart).values
    p_fill = np.clip(0.28 + 0.46 * demand_idx * dp_demand, 0.22, 0.985)
    s_filled = rng.binomial(s_slots, p_fill)

    genres = np.empty(N_SESSIONS, dtype=object)
    for c, glist in COHORT_GENRES.items():
        m = s_cohort == c
        genres[m] = rng.choice(glist, m.sum())

    sess = pd.DataFrame({
        "session_id": np.arange(1, N_SESSIONS + 1),
        "account_id": s_account, "cohort_id": s_cohort,
        "session_date": dates.values[s_date_i], "daypart": s_daypart,
        "device": rng.choice(DEVICES, N_SESSIONS, p=DEVICE_W),
        "duration_min": np.round(s_duration, 1),
        "content_genre": genres,
        "pods_served": s_pods, "ad_slots": s_slots, "slots_filled": s_filled,
    })

    # ------------------------------------------------------------------ placements
    note("Running ~1M ad auctions (placements)…")
    n_pl = int(s_filled.sum())
    rep = np.repeat(np.arange(N_SESSIONS), s_filled)
    p_session = sess.session_id.values[rep]
    p_account = s_account[rep]
    p_cohort = s_cohort[rep]
    p_date = dates.values[s_date_i][rep]
    p_daypart = s_daypart[rep]
    starts = np.concatenate(([0], np.cumsum(s_filled)[:-1]))
    p_pos = np.arange(n_pl) - np.repeat(starts, s_filled) + 1

    # campaign selection: budget-weighted, boosted by category-cohort affinity
    camp_cat = camp.merge(adv[["advertiser_id", "category"]], on="advertiser_id")
    base_w = camp_cat.budget_usd.values ** 1.5
    p_campaign = np.empty(n_pl, dtype=np.int64)
    for i, c in enumerate(coh.cohort_id.values):
        aff = np.array([cat.CATEGORY_COHORT_AFFINITY.get((k, c), 1.0) for k in camp_cat.category]) ** 2
        w = base_w * aff
        m = p_cohort == c
        p_campaign[m] = rng.choice(camp_cat.campaign_id.values, m.sum(), p=w / w.sum())

    # creative selection within campaign (A/B campaigns split by account hash)
    cr_by_camp = creative.groupby("campaign_id").creative_id.apply(np.array)
    cr_offsets = {k: v for k, v in cr_by_camp.items()}
    u = rng.random(n_pl)
    counts = creative.groupby("campaign_id").size()
    n_cr_arr = counts.reindex(p_campaign).values
    pick = (u * n_cr_arr).astype(int)
    flat = np.concatenate([cr_offsets[k] for k in counts.index])
    off = np.concatenate(([0], np.cumsum(counts.values)[:-1]))
    off_map = pd.Series(off, index=counts.index)
    p_creative = flat[off_map.reindex(p_campaign).values + pick]

    # A/B tests: ~30 campaigns with two same-type creatives; arm by account hash
    note("Assigning A/B experiment arms…")
    ab_candidates = (creative.groupby(["campaign_id", "creative_type_id"])
                     .creative_id.apply(list).reset_index())
    ab_candidates = ab_candidates[ab_candidates.creative_id.str.len() >= 2]
    # test on the biggest campaigns so the experiments are actually powered
    ab_candidates = (ab_candidates.merge(camp[["campaign_id", "budget_usd"]], on="campaign_id")
                     .nlargest(min(30, len(ab_candidates)), "budget_usd"))
    ab_rows, ab_truth_rows = [], []
    ab_ctr_mult = np.ones(n_pl)
    ab_cmp_mult = np.ones(n_pl)
    for t_id, row in enumerate(ab_candidates.itertuples(), start=1):
        cr_a, cr_b = row.creative_id[0], row.creative_id[1]
        is_null = rng.random() < 0.4
        ctr_mult = 1.0 if is_null else float(np.round(rng.lognormal(0, 0.18), 3))
        cmp_mult = 1.0 if is_null else float(np.round(rng.lognormal(0, 0.05), 3))
        metric = "ctr" if row.creative_type_id != 1 else "completion_rate"
        ab_rows.append((t_id, row.campaign_id, cr_a, cr_b,
                        f"Creative B lifts {metric.replace('_', ' ')} vs A", metric,
                        str(dates[0].date()), str(end_date)))
        ab_truth_rows.append((t_id, ctr_mult, cmp_mult))
        m = p_campaign == row.campaign_id
        arm_b = _hash_bucket(p_account[m], np.full(m.sum(), row.campaign_id), 2) == 1
        forced = np.where(arm_b, cr_b, cr_a)
        p_creative[m] = forced
        mm = np.zeros(n_pl, bool)
        mm[np.flatnonzero(m)[arm_b]] = True
        ab_ctr_mult[mm] = ctr_mult
        ab_cmp_mult[mm] = cmp_mult
    ab = pd.DataFrame(ab_rows, columns=["test_id", "campaign_id", "creative_id_a", "creative_id_b",
                                        "hypothesis", "primary_metric", "start_date", "end_date"])
    ab_truth = pd.DataFrame(ab_truth_rows, columns=["test_id", "true_ctr_mult_b", "true_completion_mult_b"])

    # holdout (ghost ads)
    p_holdout = _hash_bucket(p_account, p_campaign, 100) < HOLDOUT_PCT

    # outcomes
    note("Simulating attention outcomes & clearing prices…")
    attention = coh.set_index("cohort_id").attention_index.reindex(p_cohort).values
    cr_type = creative.set_index("creative_id").creative_type_id.reindex(p_creative).values
    type_cmp = np.select([cr_type == 2, cr_type == 3], [0.97, 0.95], 1.0)
    p_complete = np.clip((0.52 + 0.44 * attention) * type_cmp * ab_cmp_mult, 0.05, 0.97)
    completed = (rng.random(n_pl) < p_complete) & ~p_holdout

    click_base = np.select([cr_type == 3, cr_type == 2], [0.014, 0.009], 0.0012)
    p_click = click_base * (0.45 + 0.9 * attention) * ab_ctr_mult
    clicked = (rng.random(n_pl) < p_click) & ~p_holdout

    cpm_mult = coh.set_index("cohort_id").cpm_multiplier.reindex(p_cohort).values
    dp_mult = pd.Series(cat.DAYPART_CPM_MULT).reindex(p_daypart).values
    t_mult = ctype.set_index("creative_type_id").cpm_mult.reindex(cr_type).values
    ecpm = 26.0 * cpm_mult * dp_mult * t_mult * rng.lognormal(0, 0.10, n_pl)

    plc = pd.DataFrame({
        "placement_id": np.arange(1, n_pl + 1),
        "session_id": p_session, "account_id": p_account, "cohort_id": p_cohort,
        "campaign_id": p_campaign, "creative_id": p_creative,
        "session_date": p_date, "daypart": p_daypart, "pod_position": p_pos,
        "is_holdout": p_holdout.astype(np.int8),
        "completed": completed.astype(np.int8), "clicked": clicked.astype(np.int8),
        "ecpm_usd": np.round(ecpm, 2),
    })

    # ------------------------------------------------------------------ conversions
    note("Generating advertiser positive-action reports…")
    exp = (plc.groupby(["account_id", "campaign_id"])
           .agg(f=("placement_id", "size"), holdout=("is_holdout", "max"),
                last_date=("session_date", "max"))
           .reset_index())
    exp = exp.merge(camp_cat[["campaign_id", "advertiser_id", "category"]], on="campaign_id")
    exp = exp.merge(acct[["account_id", "primary_cohort_id"]], on="account_id")
    exp = exp.merge(truth, on="campaign_id")

    base = exp.category.map(cat.CATEGORY_BASE_CONV).values * CONV_SCALE
    aff = np.array([cat.CATEGORY_COHORT_AFFINITY.get((c, k), 1.0)
                    for c, k in zip(exp.category, exp.primary_cohort_id)])
    prop = rng.lognormal(0, 0.5, len(exp))
    p0 = np.clip(base * aff * prop, 0, 0.5)
    sat = 1 - np.exp(-exp.elasticity_k.values * exp.f.values)
    p_conv = np.where(exp.holdout.values == 1, p0, p0 * (1 + exp.true_lift.values * sat))
    conv_mask = rng.random(len(exp)) < p_conv

    # Delivered (intent-to-treat) lift per campaign: the asymptotic true_lift
    # attenuated by the saturation actually reached at delivered frequencies.
    # This — not the asymptotic parameter — is what a ghost-ads readout should
    # recover, so it's the calibration target on the methodology page.
    tr = exp.holdout.values == 0
    itt = (pd.DataFrame({"campaign_id": exp.campaign_id.values[tr],
                         "w": p0[tr], "ws": p0[tr] * sat[tr]})
           .groupby("campaign_id").sum())
    truth = truth.merge(
        ((itt.ws / itt.w).rename("sat_reached")).reset_index(), on="campaign_id", how="left")
    truth["true_itt_lift"] = np.round(truth.true_lift * truth.sat_reached.fillna(0), 4)
    truth["sat_reached"] = np.round(truth.sat_reached, 4)

    conv = exp[conv_mask].copy()
    act_map = pd.DataFrame([(k, v[0], v[1]) for k, v in cat.CATEGORY_ACTION.items()],
                           columns=["category", "action_type", "avg_value"])
    conv = conv.merge(act_map, on="category")
    lag = rng.integers(0, 8, len(conv))
    conv["action_date"] = pd.to_datetime(conv.last_date) + pd.to_timedelta(lag, unit="D")
    conv["action_date"] = conv.action_date.clip(upper=pd.Timestamp(end_date))
    conv["action_value_usd"] = np.round(conv.avg_value.values * rng.lognormal(0, 0.4, len(conv)), 2)
    conv["match_type"] = rng.choice(["deterministic", "modeled"], len(conv), p=[0.72, 0.28])
    conv["action_id"] = np.arange(1, len(conv) + 1)
    pact = conv[["action_id", "advertiser_id", "campaign_id", "account_id",
                 "action_date", "action_type", "action_value_usd", "match_type"]]

    # ------------------------------------------------------------------ write
    note("Writing DuckDB warehouse…")
    con = duckdb.connect(db_path)
    frames = {
        "dim_advertiser": adv[["advertiser_id", "advertiser_name", "category", "tier"]],
        "dim_creative_type": ctype[["creative_type_id", "creative_type", "description"]],
        "dim_campaign": camp, "dim_creative": creative, "dim_cohort": coh,
        "dim_account": acct, "dim_ab_test": ab,
        "fact_session": sess, "fact_placement": plc, "fact_positive_action": pact,
        "sim_campaign_truth": truth, "sim_ab_truth": ab_truth,
    }
    for name, df in frames.items():
        con.register("_tmp", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _tmp")
        con.unregister("_tmp")
    manifest = pd.DataFrame([{
        "seed": SEED, "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "window_start": str(dates[0].date()), "window_end": str(end_date),
        "placements": n_pl, "sessions": N_SESSIONS, "accounts": N_ACCOUNTS,
        "conversions": len(pact), "build_seconds": round(time.time() - t0, 1),
        "fingerprint": hashlib.sha256(f"{SEED}-{n_pl}".encode()).hexdigest()[:12],
    }])
    con.register("_tmp", manifest)
    con.execute("CREATE OR REPLACE TABLE build_manifest AS SELECT * FROM _tmp")
    con.close()
    note(f"Done: {n_pl:,} placements, {len(pact):,} positive actions in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    import os, sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/netflix_ads.duckdb"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    build(path, progress=print)
