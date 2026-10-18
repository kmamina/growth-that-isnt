import numpy as np
import pandas as pd
import config as cfg

END_EXCL = pd.Timestamp(cfg.DATA_END) + pd.Timedelta(days=1)


def month_index(ts):
    return (ts.dt.year - 2025) * 12 + ts.dt.month


def late_probability(zone, ts):
    hr = ts.dt.hour + ts.dt.minute / 60
    peak = (zone.isin(["C", "F"]) & (hr >= 18) & (hr < 21.5)).to_numpy()
    m = month_index(ts).to_numpy()
    return np.where(peak, np.where(m <= 12, cfg.LATE_PEAK_Q1, cfg.LATE_PEAK_Q0), cfg.LATE_BASE)


def time_of_day(rng, n):
    p = np.array(cfg.HOUR_WEIGHTS, dtype=float)
    p /= p.sum()
    h = rng.choice(24, size=n, p=p)
    td = (pd.to_timedelta(h, unit="h") + pd.to_timedelta(rng.integers(0, 60, n), unit="m")
          + pd.to_timedelta(rng.integers(0, 60, n), unit="s"))
    return td.to_numpy()


def make_orders(rng, customers, traits, merchants, promotions):
    c = (traits.merge(customers[["customer_id", "acquisition_channel", "home_zone"]], on="customer_id")
         .sort_values("customer_id").reset_index(drop=True))
    n = len(c)
    assert (c.customer_id.to_numpy() == np.arange(1, n + 1)).all()
    sens = c.promo_sensitivity.to_numpy()
    month = c.cohort_month.to_numpy()
    first_ts = c.first_order_ts

    # ---- first-order outcomes decide whether the customer repeats ----
    first_late = rng.random(n) < late_probability(c.home_zone, first_ts)
    flat_share = np.where(month <= 12, cfg.FLAT_SHARE_Q1, cfg.FLAT_SHARE_Q0)
    first_flat = rng.random(n) < np.clip(flat_share * (0.5 + sens) / 0.9, 0, 0.9)
    p_rep = (c.acquisition_channel.map(cfg.BASE_REPEAT).to_numpy()
             * np.where(first_late, cfg.LATE_MULT, 1.0)
             * np.where(first_flat, cfg.FLAT_MULT, 1.0))
    repeats = rng.random(n) < p_rep
    late_rep = (~repeats) & (rng.random(n) < cfg.LATE_REPEAT_P)

    # ---- second order ----
    gap = np.where(repeats, np.clip(rng.gamma(2.0, 9.0, n), 1, 89), 91 + rng.exponential(60, n))
    second_ts = (first_ts + pd.to_timedelta(gap, unit="D").to_numpy()).dt.normalize() + time_of_day(rng, n)
    second_ts = second_ts.where((repeats | late_rep) & (second_ts < END_EXCL))

    # ---- further orders ----
    life = pd.to_timedelta(c.lifetime_days.to_numpy(), unit="D").to_numpy()
    window_end = (second_ts + life).clip(upper=END_EXCL)
    win_days = ((window_end - second_ts).dt.total_seconds() / 86400).fillna(0).clip(lower=0).to_numpy()
    reduce = c.will_reduce.to_numpy()
    lam = c.orders_per_month.to_numpy() / 30 * win_days * np.where(reduce, 0.75, 1.0)
    n_extra = rng.poisson(lam)
    idx = np.repeat(np.arange(n), n_extra)
    u = rng.random(len(idx))
    u = np.where(reduce[idx], u ** 1.8, u)           # reducers order earlier in their window
    extra_ts = ((second_ts.iloc[idx].reset_index(drop=True)
                 + pd.to_timedelta(u * win_days[idx], unit="D").to_numpy()).dt.normalize()
                + time_of_day(rng, len(idx)))

    has2 = second_ts.notna().to_numpy()
    o = pd.concat([
        pd.DataFrame({"customer_id": c.customer_id, "order_ts": first_ts}),
        pd.DataFrame({"customer_id": c.customer_id[has2], "order_ts": second_ts[has2]}),
        pd.DataFrame({"customer_id": c.customer_id.to_numpy()[idx], "order_ts": extra_ts}),
    ], ignore_index=True)
    o = o.sort_values(["order_ts", "customer_id"]).reset_index(drop=True)
    N = len(o)
    o["order_id"] = np.arange(1, N + 1)
    o["order_seq"] = o.groupby("customer_id").cumcount() + 1

    cid = o.customer_id.to_numpy() - 1
    o["zone"] = c.home_zone.to_numpy()[cid]
    channel = c.acquisition_channel.to_numpy()[cid]
    sens_o = sens[cid]
    is_first = (o.order_seq == 1).to_numpy()
    zone_arr = o.zone.to_numpy()

    # ---- lateness flag (first orders keep the flag that drove repeat) ----
    late = rng.random(N) < late_probability(o.zone, o.order_ts)
    late = np.where(is_first, first_late[cid], late)

    # ---- merchant and order type ----
    is_grocery = rng.random(N) < cfg.GROCERY_SHARE
    merchant_id = np.zeros(N, dtype=int)
    for z in cfg.ZONES:
        for g in (True, False):
            mask = (zone_arr == z) & (is_grocery == g)
            pool = merchants.loc[(merchants.zone == z) &
                                 ((merchants.merchant_type == "dark_store") == g), "merchant_id"].to_numpy()
            merchant_id[mask] = rng.choice(pool, size=int(mask.sum()))

    # ---- values and costs ----
    ov = np.where(is_grocery, rng.lognormal(np.log(26), 0.40, N),
                  rng.lognormal(np.log(17), 0.45, N)).clip(6, 150)
    flat_first = is_first & first_flat[cid]
    ov = np.where(flat_first & (ov < 12), 12.0, ov).round(2)
    items = np.clip(np.round(ov / rng.uniform(5, 9, N)), 1, 25).astype(int)
    dist = np.clip(rng.gamma(3.0, 1.0, N), 0.5, 10).round(2)
    delivery_fee = (2.8 + 0.4 * dist).round(2)
    rider_cost = (1.6 + 0.3 * dist + rng.normal(0, 0.3, N)).clip(1.0).round(2)
    eta = np.round(32 + 3 * dist + rng.integers(-2, 3, N)).astype(int)
    comm_pct = merchants.set_index("merchant_id").commission_pct.reindex(merchant_id).to_numpy()
    commission = (ov * comm_pct).round(2)

    # ---- promotions ----
    month_o = month_index(o.order_ts).to_numpy()
    p_use = np.clip((cfg.PROMO_P0 + cfg.PROMO_P1 * sens_o)
                    * np.where(month_o <= 12, 1.0, cfg.PROMO_Q0_MULT), 0, 0.9)
    elig = promotions[(promotions.promo_type != "first_order_flat") &
                      (promotions.promo_id != 11)].reset_index(drop=True)   # 11 is reserved for the experiment
    date = o.order_ts.dt.normalize()
    W = np.zeros((N, len(elig)))
    for j, r in elig.iterrows():
        ok = (((date >= pd.Timestamp(r.start_date)) & (date <= pd.Timestamp(r.end_date))).to_numpy()
              & (ov >= r.min_order_value))
        if r.target_audience == "repeat_customers":
            ok &= ~is_first
        if r.target_audience == "grocery_shoppers":
            ok &= is_grocery
        if r.target_audience == "referred_customers":
            ok &= (channel == "referral")
        W[:, j] = ok * cfg.PROMO_WEIGHTS[int(r.promo_id)]
    cum = W.cumsum(axis=1)
    tot = cum[:, -1]
    pick = np.minimum((cum < (rng.random(N) * tot)[:, None]).sum(axis=1), len(elig) - 1)
    use = (rng.random(N) < p_use) & (tot > 0) & ~flat_first
    promo_id = np.where(use, elig.promo_id.to_numpy()[pick], 0)
    promo_id = np.where(flat_first, 1, promo_id)

    pinfo = promotions.set_index("promo_id")
    ptype = pinfo.promo_type.reindex(promo_id).to_numpy()
    pval = pinfo.discount_value.reindex(promo_id).fillna(0).to_numpy()
    disc = np.select([ptype == "pct_off", ptype == "cashback", ptype == "free_delivery"],
                     [pval * ov, pval * ov, delivery_fee], default=pval)
    disc = np.where(promo_id == 0, 0, np.minimum(disc, 0.6 * ov)).round(2)
    pay_fee = (0.2 + 0.012 * (ov - disc)).round(2)

    # ---- status ----
    cancelled = (o.order_seq.to_numpy() >= 3) & (rng.random(N) < cfg.CANCEL_P)

    orders = pd.DataFrame({
        "order_id": o.order_id, "customer_id": o.customer_id, "merchant_id": merchant_id,
        "promo_id": pd.Series(promo_id).where(promo_id > 0).astype("Int64"),
        "order_ts": o.order_ts, "zone": o.zone,
        "order_type": np.where(is_grocery, "grocery", "food"), "items_count": items,
        "order_value": ov, "discount_amount": disc, "delivery_fee": delivery_fee,
        "commission_amount": commission, "rider_cost": rider_cost, "payment_fee": pay_fee,
        "status": np.where(cancelled, "cancelled", "delivered"),
        "promised_eta_min": eta, "updated_at": o.order_ts + pd.Timedelta(minutes=60),
    })
    latent = pd.DataFrame({
        "order_id": o.order_id, "customer_id": o.customer_id, "order_seq": o.order_seq,
        "is_late": late & ~cancelled, "distance_km": dist, "first_order_flat": flat_first,
    })
    return orders, latent