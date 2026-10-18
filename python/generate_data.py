import numpy as np
import pandas as pd
from config import SEED, INTERIM
from gen_dimensions import make_merchants, make_riders, make_promotions
from gen_customers import make_customers
from gen_orders import make_orders
from gen_delivery import make_delivery


def quarter(ts):
    m = (ts.dt.year - 2025) * 12 + ts.dt.month
    return np.select([m.between(10, 12), m.between(13, 15)], ["Q-1", "Q0"], default="other")


def check_orders(orders, latent, customers):
    o = orders.merge(latent[["order_id", "order_seq", "is_late", "first_order_flat"]], on="order_id")
    o["q"] = quarter(o.order_ts)
    v = o[o.status != "cancelled"].copy()

    print("\nTotal orders:", len(orders), "| cancelled:", (orders.status == "cancelled").sum())
    print("Valid orders per quarter:\n", v.groupby("q").size())
    print("\nLate rate by quarter:\n", v.groupby("q").is_late.mean().round(3))
    s = v.groupby("q")[["discount_amount", "order_value"]].sum()
    print("\nDiscount rate by quarter:\n", (s.discount_amount / s.order_value).round(3))
    v["cm_pre"] = (v.commission_amount + v.delivery_fee - v.discount_amount
                   - v.rider_cost - v.payment_fee)
    print("\nCM per order BEFORE refunds and support cost:\n", v.groupby("q").cm_pre.mean().round(2))

    v = v.sort_values(["customer_id", "order_ts"])
    v["rk"] = v.groupby("customer_id").cumcount()
    f = v[v.rk == 0].set_index("customer_id")
    f["second_ts"] = v[v.rk == 1].set_index("customer_id").order_ts
    f["repeat90"] = (f.second_ts - f.order_ts) <= pd.Timedelta(days=90)
    f = f[f.order_ts < "2026-04-01"].copy()
    f["channel"] = customers.set_index("customer_id").acquisition_channel
    f["q"] = quarter(f.order_ts)
    g = f[f.q != "other"]

    print("\n90-day repeat rate by cohort quarter:\n", g.groupby("q").repeat90.mean().round(3))
    print("\nRepeat rate by channel and quarter:\n",
          g.pivot_table(index="channel", columns="q", values="repeat90", aggfunc="mean").round(2))
    print("\nRepeat rate, first order late vs on-time:\n", g.groupby("is_late").repeat90.mean().round(3))
    print("\nRepeat rate, first_order_flat vs not:\n", g.groupby("first_order_flat").repeat90.mean().round(3))

def check_delivery(orders, latent, deliv):
    d = (deliv.merge(orders[["order_id", "zone", "status", "promised_eta_min"]], on="order_id")
         .merge(latent[["order_id", "is_late"]], on="order_id"))
    d = d[d.status != "cancelled"].copy()
    mins = lambda a, b: (d[a] - d[b]).dt.total_seconds() / 60

    d["total"] = mins("delivered_ts", "placed_ts")
    d["late_ts"] = d.total > d.promised_eta_min + 10
    print("\nLate flag vs timestamps, mismatches:", int((d.late_ts != d.is_late).sum()))

    seq = ["placed_ts", "merchant_accepted_ts", "food_ready_ts", "picked_up_ts", "delivered_ts"]
    bad = sum(int((d[b] < d[a]).sum()) for a, b in zip(seq[:-1], seq[1:]))
    bad += int((d.rider_assigned_ts > d.picked_up_ts).sum())
    print("Timestamp order violations:", bad)

    d["m"] = (d.placed_ts.dt.year - 2025) * 12 + d.placed_ts.dt.month
    d["q"] = np.select([d.m.between(10, 12), d.m.between(13, 15)], ["Q-1", "Q0"], default="other")
    d["grp"] = np.where(d.zone.isin(["C", "F"]), "C/F", "other zones")
    d["prep"] = mins("food_ready_ts", "merchant_accepted_ts")
    d["assign"] = mins("rider_assigned_ts", "placed_ts")
    d["last_leg"] = mins("delivered_ts", "picked_up_ts")
    hr = d.placed_ts.dt.hour + d.placed_ts.dt.minute / 60
    d["peak"] = d.zone.isin(["C", "F"]) & (hr >= 18) & (hr < 21.5)

    g = d[d.q != "other"]
    print("\nMean minutes: rider assignment and merchant prep, by zone group and quarter")
    print(g.pivot_table(index="grp", columns="q", values=["assign", "prep"], aggfunc="mean").round(1))
    print("\nZones C/F only: last-leg minutes and late rate, evening peak vs rest")
    print(g[g.grp == "C/F"].pivot_table(index="peak", columns="q",
                                         values=["last_leg", "is_late"], aggfunc="mean").round(2))


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    merchants = make_merchants(rng)
    riders = make_riders(rng)
    promotions = make_promotions()
    customers, traits = make_customers(rng)
    orders, latent = make_orders(rng, customers, traits, merchants, promotions)
    deliv = make_delivery(rng, orders, latent, merchants, riders)

    merchants.to_csv(INTERIM / "merchants.csv", index=False)
    riders.to_csv(INTERIM / "riders.csv", index=False)
    promotions.to_csv(INTERIM / "promotions.csv", index=False)
    customers.to_csv(INTERIM / "customers.csv", index=False)
    traits.to_csv(INTERIM / "customer_traits.csv", index=False)   # hidden: never used in Phase 3
    orders.to_csv(INTERIM / "orders.csv", index=False)
    latent.to_csv(INTERIM / "order_latent.csv", index=False)      # hidden: never used in Phase 3
    deliv.to_csv(INTERIM / "delivery_events.csv", index=False)

    print("merchants:", merchants.shape, "| riders:", riders.shape, "| promotions:", promotions.shape,
          "| customers:", customers.shape, "| orders:", orders.shape)
    check_orders(orders, latent, customers)
    check_delivery(orders, latent, deliv)


if __name__ == "__main__":
    main()