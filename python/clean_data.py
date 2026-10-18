import duckdb
import pandas as pd
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
SQL = (ROOT / "sql" / "02_clean.sql").read_text()


def one(con, q):
    return con.execute(q).fetchone()[0]


def main():
    con = duckdb.connect(str(DB))

    before = {
        "orders": one(con, "SELECT COUNT(*) FROM raw_orders"),
        "zone_messy": one(con, "SELECT COUNT(*) FROM raw_orders WHERE zone NOT IN ('A','B','C','D','E','F','G','H')"),
    }

    for stmt in [s.strip() for s in SQL.split(";") if s.strip() and not s.strip().startswith("--")
                 or "CREATE" in s or "UPDATE" in s or "ALTER" in s]:
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            con.execute(body)

    rep = [
        (1, "duplicate order rows removed", before["orders"] - one(con, "SELECT COUNT(*) FROM clean_orders")),
        (2, "missing delivered_ts flagged", one(con, "SELECT COUNT(*) FROM clean_delivery_events WHERE delivery_dq_flag='missing'")),
        (3, "sequence errors flagged and nulled", one(con, "SELECT COUNT(*) FROM clean_delivery_events WHERE delivery_dq_flag='sequence_error'")),
        (4, "invalid order_value flagged (excluded from KPIs)", one(con, "SELECT COUNT(*) FROM clean_orders WHERE value_valid=0")),
        (5, "zone text standardised", before["zone_messy"]),
        (6, "invalid merchant_id set to NULL", one(con, "SELECT COUNT(*) FROM clean_orders WHERE merchant_id_valid=0")),
        (7, "ticket refunds scaled", one(con, "SELECT COUNT(DISTINCT order_id) FROM clean_support_tickets WHERE refund_scaled_flag=1")),
        (8, "customers with first_order_date corrected",
            one(con, "SELECT COUNT(*) FROM clean_customers c JOIN raw_customers r USING (customer_id) "
                     "WHERE c.first_order_date IS DISTINCT FROM r.first_order_date")),
        (9, "extreme duration flagged and nulled", one(con, "SELECT COUNT(*) FROM clean_delivery_events WHERE delivery_dq_flag='extreme_duration'")),
        (10, "empty complaint text converted", 0),
        (11, "order_ts overwritten from placed_ts",
            one(con, "SELECT COUNT(*) FROM clean_orders o JOIN raw_orders r USING (order_id, updated_at) WHERE o.order_ts <> r.order_ts")),
        (12, "status corrected from ticket refunds", one(con, "SELECT SUM(status_flag) FROM clean_orders")),
    ]
    report = pd.DataFrame(rep, columns=["issue_id", "action", "rows_affected"])
    print(report.to_string(index=False))
    report.to_csv(ROOT / "reports" / "cleaning_report.csv", index=False)

    print("\nclean_orders:", one(con, "SELECT COUNT(*) FROM clean_orders"),
          "| distinct order_id:", one(con, "SELECT COUNT(DISTINCT order_id) FROM clean_orders"))
    print("distinct zones:", sorted(r[0] for r in con.execute("SELECT DISTINCT zone FROM clean_orders").fetchall()))
    con.close()


if __name__ == "__main__":
    main()