import numpy as np
import pandas as pd
import config as cfg


def make_delivery(rng, orders, latent, merchants, riders):
    d = (orders[["order_id", "merchant_id", "zone", "order_ts", "status", "promised_eta_min"]]
         .merge(latent[["order_id", "is_late", "distance_km"]], on="order_id")
         .reset_index(drop=True))
    n = len(d)
    month = ((d.order_ts.dt.year - 2025) * 12 + d.order_ts.dt.month).to_numpy()
    hr = (d.order_ts.dt.hour + d.order_ts.dt.minute / 60).to_numpy()
    in_cf = d.zone.isin(["C", "F"]).to_numpy()
    peak_cf_q0 = in_cf & (hr >= 18) & (hr < 21.5) & (month >= 13)
    cf_q0 = in_cf & (month >= 13)
    eta = d.promised_eta_min.to_numpy().astype(float)
    late = d.is_late.to_numpy()
    cancelled = (d.status == "cancelled").to_numpy()

    # ---- total delivery time, built to match the late flag ----
    # late = more than eta + 10 minutes. Extra delay is larger in the C/F evening peak (Q0).
    exceed = np.where(peak_cf_q0, 1 + rng.exponential(14, n), 1 + rng.exponential(5, n))
    total = np.where(late, eta + 10 + exceed,
                     np.minimum(eta + rng.normal(-1, 4, n), eta + 9.0))

    # ---- early stages (minutes after placed) ----
    prep_target = (merchants.set_index("merchant_id").avg_prep_time_target_min
                   .reindex(d.merchant_id).to_numpy())
    accept = 0.5 + rng.gamma(2.0, 0.8, n)
    prep = prep_target * rng.lognormal(0, 0.15, n)          # flat across zones and quarters
    assign = rng.gamma(2.0, 1.5, n) + np.where(cf_q0, 2.0, 0.0)   # +2 min in C/F from Q0
    wait = rng.exponential(1.5, n)

    ready = accept + prep
    picked = np.maximum(ready, assign + 3.0) + wait
    # always leave at least 4 minutes for the last leg
    picked = np.minimum(picked, total - 4.0)
    ready = np.minimum(ready, picked - 0.2)
    accept = np.minimum(accept, ready - 0.2)
    assign = np.minimum(assign, picked - 3.0)

    def at(minutes):
        return d.order_ts + pd.to_timedelta(np.round(minutes * 60), unit="s")

    out = pd.DataFrame({"order_id": d.order_id})
    out["placed_ts"] = d.order_ts
    out["merchant_accepted_ts"] = at(accept)
    out["food_ready_ts"] = at(ready).where(~cancelled)
    out["rider_assigned_ts"] = at(assign).where(~cancelled)
    out["picked_up_ts"] = at(picked).where(~cancelled)
    out["delivered_ts"] = at(total).where(~cancelled)

    # ---- rider: random active rider from the order's zone ----
    rider_id = np.full(n, np.nan)
    zone_arr = d.zone.to_numpy()
    for z in cfg.ZONES:
        mask = (zone_arr == z) & ~cancelled
        pool = riders.loc[(riders.home_zone == z) & (riders.active_flag == 1), "rider_id"].to_numpy()
        rider_id[mask] = rng.choice(pool, size=int(mask.sum()))
    out["rider_id"] = pd.Series(rider_id).astype("Int64")
    out["distance_km"] = d.distance_km
    return out[["order_id", "rider_id", "placed_ts", "merchant_accepted_ts", "food_ready_ts",
                "rider_assigned_ts", "picked_up_ts", "delivered_ts", "distance_km"]]