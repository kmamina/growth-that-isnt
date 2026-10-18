import duckdb
import pandas as pd
from config import INTERIM, ROOT

DB = ROOT / "data" / "zesto.duckdb"


def main():
    con = duckdb.connect(str(DB), read_only=True)
    key_o = pd.read_csv(INTERIM / "orders.csv", parse_dates=["order_ts"])
    key_c = pd.read_csv(INTERIM / "customers.csv")
    key_d = pd.read_csv(INTERIM / "delivery_events.csv",
                        parse_dates=["delivered_ts", "placed_ts"])

    co = con.execute("SELECT * FROM clean_orders").fetchdf()
    cc = con.execute("SELECT * FROM clean_customers").fetchdf()
    cd = con.execute("SELECT * FROM clean_delivery_events").fetchdf()

    rows = []

    def check(name, ok, n_bad):
        rows.append((name, "PASS" if ok else "FAIL", n_bad))

    # orders: same ids, same count
    check("order_id set matches answer key", set(co.order_id) == set(key_o.order_id), 0)
    m = co.merge(key_o, on="order_id", suffixes=("", "_key"))

    # zone
    bad = int((m.zone != m.zone_key).sum())
    check("zone matches answer key", bad == 0, bad)

    # order_ts
    bad = int((m.order_ts != m.order_ts_key).sum())
    check("order_ts matches answer key", bad == 0, bad)

    # status (cleaned status vs key status)
    bad = int((m.status != m.status_key).sum())
    check("status matches answer key", bad == 0, bad)

    # order_value, only for rows we did not flag invalid
    ok_rows = m[m.value_valid == 1]
    bad = int((ok_rows.order_value.round(2) != ok_rows.order_value_key.round(2)).sum())
    check("order_value matches key (valid rows)", bad == 0, bad)

    # merchant_id: cleaned NULL exactly where invalid
    bad = int(((m.merchant_id_valid == 0) & m.merchant_id.notna()).sum())
    check("invalid merchant_id nulled", bad == 0, bad)

        # customers first_order_date: expected = first date among orders that are valid
    # under the KPI definition (not cancelled, value_valid = 1), taken from the answer key
    valid_ids = co.loc[(co.status != "cancelled") & (co.value_valid == 1), "order_id"]
    exp = (key_o[key_o.order_id.isin(valid_ids)]
           .groupby("customer_id").order_ts.min().dt.date.rename("expected"))
    mc = cc.merge(exp, on="customer_id", how="left")
    got = pd.to_datetime(mc.first_order_date).dt.date
    bad = int(((got != mc.expected) & ~(got.isna() & mc.expected.isna())).sum())
    check("first_order_date matches key (valid-order rule)", bad == 0, bad)
    
    # delivered_ts: matches key except where we deliberately nulled it
    md = cd.merge(key_d, on="order_id", suffixes=("", "_key"))
    keep = md.delivery_dq_flag.isin(["sequence_error", "extreme_duration", "missing"]) == False
    bad = int((md.loc[keep, "delivered_ts"].fillna(pd.Timestamp(0))
               != md.loc[keep, "delivered_ts_key"].fillna(pd.Timestamp(0))).sum())
    check("delivered_ts matches key (unflagged rows)", bad == 0, bad)

    res = pd.DataFrame(rows, columns=["check", "result", "rows_wrong"])
    print(res.to_string(index=False))
    res.to_csv(ROOT / "reports" / "cleaning_verification.csv", index=False)
    con.close()


if __name__ == "__main__":
    main()