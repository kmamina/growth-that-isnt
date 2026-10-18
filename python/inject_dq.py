import numpy as np
import pandas as pd
import config as cfg

LOG = []


def log(issue, table, keys, col, orig, new):
    for k, o, n in zip(keys, orig, new):
        LOG.append((issue, table, k, col, o, n))


def pick(rng, pool, rate, used):
    """Pick rate * len(pool) ids from pool, avoiding ids already used by another issue."""
    avail = np.setdiff1d(pool, list(used))
    k = max(1, int(round(rate * len(pool))))
    ids = rng.choice(avail, size=min(k, len(avail)), replace=False)
    used.update(ids.tolist())
    return ids


def inject(rng, customers, orders, deliv, tickets):
    orders = orders.copy()
    deliv = deliv.copy()
    tickets = tickets.copy()
    customers = customers.copy()
    R = cfg.DQ_RATES
    used_orders, used_deliv = set(), set()

    valid = orders[orders.status != "cancelled"]
    valid_ids = valid.order_id.to_numpy()

    # ---- 4: order_value <= 0 (done first so later issues avoid these rows) ----
    ids = pick(rng, valid_ids, R[4], used_orders)
    idx = orders.order_id.isin(ids)
    orig = orders.loc[idx, "order_value"].to_numpy()
    new = np.where(rng.random(len(orig)) < 0.5, 0.0, -orig)
    orders.loc[idx, "order_value"] = new
    log(4, "orders", orders.loc[idx, "order_id"], "order_value", orig, new)

    # ---- 7: summed ticket refunds exceed order_value ----
    ref = tickets.groupby("order_id").refund_amount.sum()
    cand = ref[ref > 0].index.to_numpy()
    cand = np.setdiff1d(cand, list(used_orders))
    ids = pick(rng, cand, R[7] * len(valid_ids) / max(len(cand), 1), used_orders)
    for oid in ids:
        ov = float(orders.loc[orders.order_id == oid, "order_value"].iloc[0])
        rows = tickets.index[(tickets.order_id == oid) & (tickets.refund_amount > 0)]
        r = rows[0]
        orig = tickets.at[r, "refund_amount"]
        new = round(ov * 1.3, 2)
        tickets.at[r, "refund_amount"] = new
        log(7, "support_tickets", [tickets.at[r, "ticket_id"]], "refund_amount", [orig], [new])

    # ---- 6: merchant_id not in merchants ----
    ids = pick(rng, valid_ids, R[6], used_orders)
    idx = orders.order_id.isin(ids)
    orig = orders.loc[idx, "merchant_id"].to_numpy()
    new = rng.integers(9000, 9999, size=len(orig))
    orders.loc[idx, "merchant_id"] = new
    log(6, "orders", orders.loc[idx, "order_id"], "merchant_id", orig, new)

    # ---- 5: zone text inconsistent ----
    ids = pick(rng, orders.order_id.to_numpy(), R[5], used_orders)
    idx = orders.order_id.isin(ids)
    orig = orders.loc[idx, "zone"].to_numpy()
    kind = rng.integers(1, 4, size=len(orig))   # 1 lower, 2 "Zone X", 3 " X "
    new = np.array([o.lower() if k == 1 else (f"Zone {o}" if k == 2 else f" {o} ")
                    for o, k in zip(orig, kind)])
    orders.loc[idx, "zone"] = new
    log(5, "orders", orders.loc[idx, "order_id"], "zone", orig, new)

    # ---- 11: orders.order_ts differs from delivery_events.placed_ts ----
    ids = pick(rng, valid_ids, R[11], used_orders)
    idx = orders.order_id.isin(ids)
    orig = orders.loc[idx, "order_ts"]
    shift = pd.to_timedelta(rng.integers(1, 30, size=len(orig)), unit="m")
    new = orig + shift
    orders.loc[idx, "order_ts"] = new
    log(11, "orders", orders.loc[idx, "order_id"], "order_ts", orig.astype(str), new.astype(str))

    # ---- 12: status disagrees with ticket refunds (flip status) ----
    ref_by = tickets.groupby("order_id").refund_amount.sum()
    refunded_ids = np.setdiff1d(ref_by[ref_by > 0].index.to_numpy(), list(used_orders))
    deliv_ids = np.setdiff1d(valid[~valid.order_id.isin(ref_by.index)].order_id.to_numpy(), list(used_orders))
    k = max(1, int(round(R[12] * len(valid_ids))))
    a = rng.choice(refunded_ids, size=min(k // 2, len(refunded_ids)), replace=False)   # refunded -> delivered
    b = rng.choice(deliv_ids, size=min(k - len(a), len(deliv_ids)), replace=False)      # delivered -> refunded
    used_orders.update(a.tolist() + b.tolist())
    for ids, new_status in ((a, "delivered"), (b, "refunded")):
        idx = orders.order_id.isin(ids)
        orig = orders.loc[idx, "status"].to_numpy()
        orders.loc[idx, "status"] = new_status
        log(12, "orders", orders.loc[idx, "order_id"], "status", orig, [new_status] * len(orig))

    # ---- 2, 3, 9: delivery timestamps ----
    dv = deliv[deliv.order_id.isin(valid_ids) & ~deliv.order_id.isin(used_orders)]
    dids = dv.order_id.to_numpy()
    for issue in (2, 3, 9):
        ids = pick(rng, dids, R[issue], used_deliv)
        idx = deliv.order_id.isin(ids)
        orig = deliv.loc[idx, "delivered_ts"]
        if issue == 2:
            new = pd.Series([pd.NaT] * len(orig), index=orig.index)
        elif issue == 3:
            new = deliv.loc[idx, "picked_up_ts"] - pd.to_timedelta(rng.integers(1, 15, size=len(orig)), unit="m")
        else:
            new = deliv.loc[idx, "placed_ts"] + pd.to_timedelta(rng.integers(601, 1500, size=len(orig)), unit="m")
        deliv.loc[idx, "delivered_ts"] = new
        log(issue, "delivery_events", deliv.loc[idx, "order_id"], "delivered_ts",
            orig.astype(str), new.astype(str))

    # ---- 10: empty string instead of NULL ----
    null_idx = tickets.index[tickets.complaint_text.isna()]
    k = max(1, int(round(R[10] * len(tickets))))
    chosen = rng.choice(null_idx, size=min(k, len(null_idx)), replace=False)
    log(10, "support_tickets", tickets.loc[chosen, "ticket_id"], "complaint_text",
        [None] * len(chosen), [""] * len(chosen))
    tickets.loc[chosen, "complaint_text"] = ""

    # ---- 8: customers.first_order_date wrong ----
    ids = pick(rng, customers.customer_id.to_numpy(), R[8], set())
    idx = customers.customer_id.isin(ids)
    orig = customers.loc[idx, "first_order_date"]
    new = pd.to_datetime(orig) + pd.to_timedelta(rng.integers(-40, 40, size=len(orig)), unit="D")
    new = new.dt.date
    customers.loc[idx, "first_order_date"] = new
    log(8, "customers", customers.loc[idx, "customer_id"], "first_order_date", orig.astype(str), new.astype(str))

    # ---- 1: duplicate order_id, older version differs ----
    ids = pick(rng, orders.order_id.to_numpy(), R[1], used_orders)
    dup = orders[orders.order_id.isin(ids)].copy()
    dup["updated_at"] = dup["updated_at"] - pd.Timedelta(minutes=45)
    flip = rng.random(len(dup)) < 0.5
    dup.loc[flip, "status"] = np.where(dup.loc[flip, "status"] == "delivered", "cancelled", "delivered")
    dup.loc[~flip, "order_value"] = (dup.loc[~flip, "order_value"] * 0.8).round(2)
    orders = pd.concat([orders, dup], ignore_index=True)
    log(1, "orders", dup.order_id, "updated_at", ["latest"] * len(dup), ["older duplicate added"] * len(dup))

    log_df = pd.DataFrame(LOG, columns=["issue_id", "table_name", "row_key", "column_name",
                                        "original_value", "injected_value"])
    return customers, orders, deliv, tickets, log_df