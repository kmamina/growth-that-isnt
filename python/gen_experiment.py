import numpy as np
import pandas as pd
import config as cfg
from gen_orders import time_of_day

SNAP = pd.Timestamp("2026-04-01")
LAPSE_CUTOFF = SNAP - pd.Timedelta(days=45)      # 2026-02-15
WINDOW_END = SNAP + pd.Timedelta(days=90)        # 2026-06-30 00:00


def customer_segments(orders):
    v = orders[(orders.status != "cancelled") & (orders.order_ts < SNAP)].copy()
    v["promo_used"] = (v.discount_amount > 0).astype(int)
    g = v.groupby("customer_id").agg(n_orders=("order_id", "size"),
                                     promo_share=("promo_used", "mean"),
                                     last_ts=("order_ts", "max"))
    g["lapsing"] = g.last_ts < LAPSE_CUTOFF
    g["segment"] = np.select([g.promo_share >= 0.6,
                              (g.n_orders >= 4) & (g.promo_share <= 0.2)],
                             ["deal_seeker", "loyal_lapsing"], default="other")
    return g


def make_experiment(rng, orders, latent, deliv, merchants):
    seg = customer_segments(orders)
    elig = seg[seg.lapsing & seg.segment.isin(["loyal_lapsing", "deal_seeker"])]

    # ---- sample and assign 50/50 within each segment ----
    parts = []
    for s, grp in elig.groupby("segment"):
        ids = rng.permutation(grp.index.to_numpy())[:cfg.EXP_MAX_PER_SEGMENT]
        parts.append(pd.DataFrame({
            "customer_id": ids, "segment": s,
            "variant": np.where(np.arange(len(ids)) % 2 == 0, "treatment", "control")}))
    ex = pd.concat(parts, ignore_index=True)
    n = len(ex)

    # ---- baseline: who reorders in the window without any offer ----
    v = orders[(orders.status != "cancelled") & (orders.order_ts >= SNAP) & (orders.order_ts < WINDOW_END)]
    first_in_window = v.sort_values("order_ts").groupby("customer_id").order_id.first()
    ex["base_order_id"] = ex.customer_id.map(first_in_window)
    ex["base_reorder"] = ex.base_order_id.notna()
    base_rate = ex.groupby("segment").base_reorder.mean()

    # ---- treatment effect ----
    lift = ex.segment.map(cfg.EXP_LIFT).to_numpy()
    p_add = lift / (1 - ex.segment.map(base_rate).to_numpy())
    treated = (ex.variant == "treatment").to_numpy()
    base = ex.base_reorder.to_numpy()
    ex["incremental"] = treated & ~base & (rng.random(n) < p_add)
    ex["redeem_base"] = treated & base & (rng.random(n) < cfg.EXP_REDEEM_BASE)
    ex["offer_cost"] = np.where(ex.incremental | ex.redeem_base, cfg.OFFER_COST, 0.0)

    # ---- apply the credit to baseline orders that were redeemed ----
    orders = orders.copy()
    m = orders.order_id.isin(ex.loc[ex.redeem_base, "base_order_id"].astype(int))
    orders.loc[m, "promo_id"] = 11
    orders.loc[m, "discount_amount"] = cfg.OFFER_COST
    orders.loc[m, "payment_fee"] = (0.2 + 0.012 * (orders.loc[m, "order_value"] - cfg.OFFER_COST)).round(2)

    # ---- new orders for customers the offer brought back ----
    inc = ex.loc[ex.incremental, ["customer_id"]].reset_index(drop=True)
    inc["n_orders"] = 1 + rng.poisson(cfg.EXP_EXTRA_ORDERS, len(inc))
    inc["first_idx"] = rng.integers(0, 90, len(inc))
    rows = inc.loc[inc.index.repeat(inc.n_orders), ["customer_id", "first_idx"]].reset_index(drop=True)
    rows["j"] = rows.groupby("customer_id").cumcount()
    rows["row_id"] = np.arange(len(rows))
    k = len(rows)

    first = (rows.j == 0).to_numpy()
    fi = rows.first_idx.to_numpy()
    day_idx = np.where(first, fi, fi + np.floor(rng.random(k) * (90 - fi)).astype(int))
    new_ts = pd.Series(SNAP + pd.to_timedelta(day_idx, unit="D") + pd.to_timedelta(time_of_day(rng, k)))

    # template = a random earlier valid order of the same customer
    pool = (orders[(orders.status != "cancelled") & (orders.order_ts < SNAP)]
            .merge(rows[["customer_id", "row_id"]], on="customer_id"))
    pool["r"] = rng.random(len(pool))
    tmpl = pool.sort_values("r").drop_duplicates("row_id").sort_values("row_id").reset_index(drop=True)
    td = deliv.set_index("order_id").loc[tmpl.order_id].reset_index()
    tl = latent.set_index("order_id").loc[tmpl.order_id].reset_index()

    new_id = int(orders.order_id.max()) + 1 + np.arange(k)
    ov = (tmpl.order_value.to_numpy() * rng.lognormal(0, 0.15, k)).clip(6, 150).round(2)
    comm_pct = merchants.set_index("merchant_id").commission_pct.reindex(tmpl.merchant_id).to_numpy()
    disc = np.where(first, cfg.OFFER_COST, 0.0)

    new_orders = pd.DataFrame({
        "order_id": new_id, "customer_id": tmpl.customer_id, "merchant_id": tmpl.merchant_id,
        "promo_id": pd.Series(np.where(first, 11, np.nan)).astype("Int64"),
        "order_ts": new_ts, "zone": tmpl.zone, "order_type": tmpl.order_type,
        "items_count": tmpl.items_count, "order_value": ov, "discount_amount": disc,
        "delivery_fee": tmpl.delivery_fee, "commission_amount": (ov * comm_pct).round(2),
        "rider_cost": tmpl.rider_cost, "payment_fee": (0.2 + 0.012 * (ov - disc)).round(2),
        "status": "delivered", "promised_eta_min": tmpl.promised_eta_min,
        "updated_at": new_ts + pd.Timedelta(minutes=60)})

    new_deliv = pd.DataFrame({"order_id": new_id, "rider_id": td.rider_id, "placed_ts": new_ts})
    for c in ["merchant_accepted_ts", "food_ready_ts", "rider_assigned_ts", "picked_up_ts", "delivered_ts"]:
        new_deliv[c] = new_ts + (td[c] - td.placed_ts)
    new_deliv["distance_km"] = td.distance_km

    new_latent = pd.DataFrame({"order_id": new_id, "customer_id": tmpl.customer_id, "order_seq": 0,
                               "is_late": tl.is_late.to_numpy(), "distance_km": td.distance_km,
                               "first_order_flat": False})

    orders = pd.concat([orders, new_orders], ignore_index=True)
    deliv = pd.concat([deliv, new_deliv], ignore_index=True)
    latent = pd.concat([latent, new_latent], ignore_index=True)
    ts = orders.set_index("order_id").order_ts
    latent = latent.assign(_ts=latent.order_id.map(ts)).sort_values(["customer_id", "_ts", "order_id"])
    latent["order_seq"] = latent.groupby("customer_id").cumcount() + 1
    latent = latent.drop(columns="_ts").sort_values("order_id").reset_index(drop=True)

    assignments = (ex[["customer_id", "variant", "offer_cost"]]
                   .assign(experiment_id=cfg.EXPERIMENT_ID, assigned_date=SNAP.date())
                   [["customer_id", "experiment_id", "variant", "assigned_date", "offer_cost"]]
                   .sort_values("customer_id").reset_index(drop=True))
    return assignments, orders, latent, deliv, ex, seg


def check_experiment(orders, ex, seg):
    print("\nSegments among lapsing customers (before sampling):\n",
          seg[seg.lapsing].segment.value_counts())
    v = orders[(orders.status != "cancelled") & (orders.order_ts >= SNAP) & (orders.order_ts < WINDOW_END)]
    ex = ex.copy()
    ex["reorder"] = ex.customer_id.isin(v.customer_id)
    print("\nReorder rate within 90 days of assignment:\n",
          ex.groupby(["segment", "variant"]).agg(n=("reorder", "size"), reorder_rate=("reorder", "mean")).round(3))
    for s in ["loyal_lapsing", "deal_seeker"]:
        a = ex[(ex.segment == s) & (ex.variant == "treatment")]
        b = ex[(ex.segment == s) & (ex.variant == "control")]
        pa, pb = a.reorder.mean(), b.reorder.mean()
        se = np.sqrt(pa * (1 - pa) / len(a) + pb * (1 - pb) / len(b))
        lift = pa - pb
        cost = a.offer_cost.sum()
        inc = lift * len(a)
        per = f"${cost / inc:,.2f}" if inc > 1 else "n/a (no incremental orders)"
        print(f"{s}: lift {lift*100:.1f} pts (95% CI {100*(lift-1.96*se):.1f} to {100*(lift+1.96*se):.1f}) "
              f"| offer cost ${cost:,.0f} | cost per incremental reorder {per}")