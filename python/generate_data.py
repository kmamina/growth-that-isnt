import numpy as np
import pandas as pd
from config import SEED, INTERIM, SUPPORT_COST
from gen_dimensions import make_merchants, make_riders, make_promotions
from gen_customers import make_customers
from gen_orders import make_orders
from gen_delivery import make_delivery
from gen_tickets import make_tickets
from gen_experiment import make_experiment, check_experiment
from inject_dq import inject
from config import RAW


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
    print("\nGMV by quarter:\n", s.order_value.round(0))

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


def check_tickets(orders, latent, tickets, tl):
    v = orders[orders.status != "cancelled"].merge(latent[["order_id", "first_order_flat"]], on="order_id")
    v["q"] = quarter(v.order_ts)
    v["refund"] = v.order_id.map(tickets.groupby("order_id").refund_amount.sum()).fillna(0)
    v["has_ticket"] = v.order_id.isin(tickets.order_id)

    print("\nTickets:", len(tickets), "| orders with a ticket:", int(v.has_ticket.sum()),
          "| text is NULL:", round(tickets.complaint_text.isna().mean(), 3))
    print("\nTicket rate by quarter:\n", v.groupby("q").has_ticket.mean().round(3))
    print("\nRefund rate by quarter (orders with refund > 0):\n",
          (v.refund > 0).groupby(v.q).mean().round(3))
    print("\nStatus counts:\n", orders.status.value_counts())
    print("Status vs refund mismatches:", int(((v.status == "refunded") != (v.refund > 0)).sum()))
    print("Refund greater than order value:", int((v.refund > v.order_value + 0.01).sum()))

    v["cm"] = (v.commission_amount + v.delivery_fee - v.discount_amount - v.refund
               - v.rider_cost - v.payment_fee - np.where(v.has_ticket, SUPPORT_COST, 0))
    print("\nCM per order by quarter (full KPI definition):\n", v.groupby("q").cm.mean().round(2))
    print("\nCM per order, first_order_flat vs not (all quarters):\n",
          v.groupby("first_order_flat").cm.mean().round(2))

    t = (tickets.merge(tl[["ticket_id", "true_theme"]], on="ticket_id")
         .merge(orders[["order_id", "order_ts", "zone", "order_type"]], on="order_id"))
    t["q"] = quarter(t.order_ts)
    oth = t[t.category == "other"]
    print("\nShare of 'other' tickets that are really missing-item, by quarter:\n",
          (oth.true_theme == "missing").groupby(oth.q).mean().round(3))
    g = v[v.order_type == "grocery"]
    mt = t[t.true_theme == "missing"]
    rate = (mt.groupby(["zone", "q"]).size() / g.groupby(["zone", "q"]).size()).unstack()
    print("\nMissing-item tickets per grocery order, by zone:\n", rate[["Q-1", "Q0"]].round(3))


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    merchants = make_merchants(rng)
    riders = make_riders(rng)
    promotions = make_promotions()
    customers, traits = make_customers(rng)
    orders, latent = make_orders(rng, customers, traits, merchants, promotions)
    deliv = make_delivery(rng, orders, latent, merchants, riders)
    tickets, tickets_latent, orders = make_tickets(rng, orders, latent, deliv, merchants)
    assignments, orders, latent, deliv, ex, seg = make_experiment(rng, orders, latent, deliv, merchants)

    merchants.to_csv(INTERIM / "merchants.csv", index=False)
    riders.to_csv(INTERIM / "riders.csv", index=False)
    promotions.to_csv(INTERIM / "promotions.csv", index=False)
    customers.to_csv(INTERIM / "customers.csv", index=False)
    orders.to_csv(INTERIM / "orders.csv", index=False)
    deliv.to_csv(INTERIM / "delivery_events.csv", index=False)
    tickets.to_csv(INTERIM / "support_tickets.csv", index=False)
    traits.to_csv(INTERIM / "customer_traits.csv", index=False)      # hidden: never used in Phase 3
    latent.to_csv(INTERIM / "order_latent.csv", index=False)         # hidden: never used in Phase 3
    tickets_latent.to_csv(INTERIM / "ticket_latent.csv", index=False)  # hidden: only for scoring GenAI
    assignments.to_csv(INTERIM / "experiment_assignments.csv", index=False)
    ex.to_csv(INTERIM / "experiment_latent.csv", index=False)     # hidden: never used in Phase 3

    RAW.mkdir(parents=True, exist_ok=True)
    c_raw, o_raw, d_raw, t_raw, log_df = inject(rng, customers, orders, deliv, tickets)
    merchants.to_csv(RAW / "merchants.csv", index=False)
    riders.to_csv(RAW / "riders.csv", index=False)
    promotions.to_csv(RAW / "promotions.csv", index=False)
    assignments.to_csv(RAW / "experiment_assignments.csv", index=False)
    c_raw.to_csv(RAW / "customers.csv", index=False)
    o_raw.to_csv(RAW / "orders.csv", index=False)
    d_raw.to_csv(RAW / "delivery_events.csv", index=False)
    t_raw.to_csv(RAW / "support_tickets.csv", index=False)
    log_df.to_csv(RAW / "injection_log.csv", index=False)
    print("\nInjected issues per issue_id:\n", log_df.groupby("issue_id").size())
    print("merchants:", merchants.shape, "| riders:", riders.shape, "| promotions:", promotions.shape,
          "| customers:", customers.shape, "| orders:", orders.shape, "| tickets:", tickets.shape)
    check_orders(orders, latent, customers)
    check_delivery(orders, latent, deliv)
    check_tickets(orders, latent, tickets, tickets_latent)
    check_experiment(orders, ex, seg)


if __name__ == "__main__":
    main()