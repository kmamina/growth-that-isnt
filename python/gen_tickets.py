import numpy as np
import pandas as pd
import config as cfg

END_EXCL = pd.Timestamp(cfg.DATA_END) + pd.Timedelta(days=1)

TEXTS = {
    "late": [
        "Order arrived very late", "Delivery took over an hour",
        "Food was cold because the rider was so slow", "Rider got lost and the order was delayed",
        "Waited far longer than the estimated time", "Delivery was late again at dinner time",
        "Still waiting, the app kept showing a delay"],
    "missing": [
        "Two items were missing from my order", "Paid for 6 items but only received 4",
        "Milk and eggs were not in the bag", "Order was short by a few items, please check",
        "Half my groceries did not arrive", "Missing items again, this is the second time",
        "Bag felt light and some items were not delivered",
        "Vegetables I ordered were not inside the package"],
    "wrong_item": [
        "Received someone else's order", "Wrong item delivered",
        "Asked for chicken but got veg", "Got a different size than ordered"],
    "quality": [
        "Food was stale", "Vegetables were not fresh", "Packaging was leaking",
        "The meal tasted off", "Item was damaged on arrival"],
    "payment": [
        "Charged twice for one order", "Payment deducted but order failed",
        "Wrong amount charged", "Refund to my card has not arrived yet"],
    "other": [
        "Promo code did not apply at checkout", "App crashed while placing the order",
        "Need an invoice for this order", "Please update my delivery address",
        "How do I change my registered phone number?", "Rider was impolite on the phone",
        "Loyalty points are not showing in my account", "Cannot find my order history"],
}


def make_tickets(rng, orders, latent, deliv, merchants):
    d = (orders[["order_id", "customer_id", "merchant_id", "order_ts", "order_type",
                 "order_value", "status", "promised_eta_min"]]
         .merge(latent[["order_id", "is_late"]], on="order_id")
         .merge(deliv[["order_id", "delivered_ts"]], on="order_id"))
    d = d[d.status != "cancelled"].reset_index(drop=True)
    n = len(d)

    month = ((d.order_ts.dt.year - 2025) * 12 + d.order_ts.dt.month).to_numpy()
    late = d.is_late.to_numpy()
    over = ((d.delivered_ts - d.order_ts).dt.total_seconds() / 60
            - d.promised_eta_min - 10).to_numpy()
    severe = late & (over >= cfg.SEVERE_OVER_MIN)
    grocery = (d.order_type == "grocery").to_numpy()
    ov = d.order_value.to_numpy()

    # Finding 3: two problem dark stores, one in zone D and one in zone G
    dark = merchants[merchants.merchant_type == "dark_store"]
    problem = [int(dark[dark.zone == z].merchant_id.min()) for z in ("D", "G")]
    spike = grocery & d.merchant_id.isin(problem).to_numpy() & (month >= 13)

    p_late = np.where(late, np.where(severe, cfg.TK_LATE_SEVERE, cfg.TK_LATE_MILD), cfg.TK_LATE_NONLATE)
    p_missing = np.where(grocery, cfg.TK_MISSING_GROCERY, cfg.TK_MISSING_FOOD)
    p_missing = np.where(spike, cfg.TK_MISSING_SPIKE, p_missing)

    draws = {
        "late": rng.random(n) < p_late,
        "missing": rng.random(n) < p_missing,
        "wrong_item": rng.random(n) < cfg.TK_WRONG,
        "quality": rng.random(n) < cfg.TK_QUALITY,
        "payment": rng.random(n) < cfg.TK_PAYMENT,
        "other": rng.random(n) < cfg.TK_OTHER,
    }

    frames = []
    for theme, mask in draws.items():
        idx = np.flatnonzero(mask)
        k = len(idx)
        if theme == "late":
            pr = np.where(severe[idx], cfg.RF_LATE_SEVERE,
                          np.where(late[idx], cfg.RF_LATE_MILD, cfg.RF_LATE_NONLATE))
        else:
            pr = cfg.REFUND_P[theme]
        refunded = rng.random(k) < pr
        lo, hi = cfg.REFUND_FRAC[theme]
        refund = np.where(refunded, rng.uniform(lo, hi, k) * ov[idx], 0.0)

        if theme == "missing":
            category = np.where(rng.random(k) < cfg.MISSING_AS_OTHER, "other", "missing_item")
        else:
            category = np.full(k, theme)

        delay = rng.uniform(5, 90, k) if theme == "late" else 5 + rng.exponential(180, k)
        created = (d.delivered_ts.iloc[idx].reset_index(drop=True)
                   + pd.to_timedelta(np.round(delay * 60), unit="s"))
        created = created.where(created < END_EXCL, END_EXCL - pd.Timedelta(seconds=1))

        text = rng.choice(TEXTS[theme], size=k)
        text = np.where(rng.random(k) < cfg.TEXT_NULL_P, None, text)

        frames.append(pd.DataFrame({
            "order_id": d.order_id.to_numpy()[idx], "customer_id": d.customer_id.to_numpy()[idx],
            "created_ts": created, "category": category, "complaint_text": text,
            "refund_amount": refund, "true_theme": theme, "order_value": ov[idx]}))

    t = (pd.concat(frames, ignore_index=True)
         .sort_values(["created_ts", "order_id"]).reset_index(drop=True))

    # Cap total refunds per order at the order value (clean data must be clean)
    cum = t.groupby("order_id").refund_amount.cumsum()
    excess = (cum - t.order_value).clip(lower=0)
    t["refund_amount"] = (t.refund_amount - excess).clip(lower=0).round(2)

    t["ticket_id"] = np.arange(1, len(t) + 1)
    t["resolution_status"] = np.where(
        t.refund_amount > 0, "refunded",
        rng.choice(["resolved", "rejected"], size=len(t), p=[0.8, 0.2]))

    # Orders with a refund become status 'refunded'; updated_at moves to the refund time
    refund_by_order = t.groupby("order_id").refund_amount.sum()
    last_refund_ts = t[t.refund_amount > 0].groupby("order_id").created_ts.max()
    orders = orders.copy()
    m = orders.order_id.isin(refund_by_order[refund_by_order > 0].index)
    orders.loc[m, "status"] = "refunded"
    orders.loc[m, "updated_at"] = orders.loc[m, "order_id"].map(last_refund_ts) + pd.Timedelta(minutes=30)

    tickets = t[["ticket_id", "order_id", "customer_id", "created_ts", "category",
                 "complaint_text", "refund_amount", "resolution_status"]]
    ticket_latent = t[["ticket_id", "order_id", "true_theme"]]
    return tickets, ticket_latent, orders