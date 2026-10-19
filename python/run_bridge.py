import duckdb
import pandas as pd
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
SQL = (ROOT / "sql" / "04_bridge_churn.sql").read_text()


def main():
    con = duckdb.connect(str(DB))
    for s in [x.strip() for x in SQL.split(";") if "CREATE" in x]:
        con.execute("\n".join(l for l in s.splitlines() if not l.strip().startswith("--")))

    b = con.execute("""
        SELECT category, COUNT(*) AS customers,
          ROUND(SUM(gmv_q1), 0) AS gmv_q1, ROUND(SUM(gmv_q0), 0) AS gmv_q0,
          ROUND(SUM(gmv_q0 - gmv_q1), 0) AS contribution
        FROM v_bridge GROUP BY category ORDER BY contribution DESC""").fetchdf()
    print("GMV BRIDGE (Q-1 to Q0)")
    print(b.to_string(index=False))

    exact = con.execute("""
    SELECT SUM(gmv_q0 - gmv_q1) FROM v_bridge""").fetchone()[0]
    tot = con.execute("""
        SELECT (SELECT SUM(order_value) FROM v_orders_q WHERE q='Q0')
             - (SELECT SUM(order_value) FROM v_orders_q WHERE q='Q-1')""").fetchone()[0]
    print("\nSum of components (unrounded): %.2f | total GMV change: %.2f | difference: %.4f"
          % (exact, tot, exact - tot))
    print("Customers with no category:",
          con.execute("SELECT COUNT(*) FROM v_bridge WHERE category IS NULL").fetchone()[0])

    c = con.execute("""
        SELECT churn_type, COUNT(*) AS customers,
               SUM(bad_experience) AS bad_experience, SUM(reactivated) AS reactivated
        FROM v_churn GROUP BY churn_type ORDER BY churn_type""").fetchdf()
    print("\nCHURN TYPES AT 2026-03-31")
    print(c.to_string(index=False))
    lost = c[c.churn_type == "Lost"].iloc[0]
    print("Lost = Bad-experience %d + Other %d = %d"
          % (lost.bad_experience, lost.customers - lost.bad_experience, lost.customers))

    b.to_csv(ROOT / "reports" / "gmv_bridge.csv", index=False)
    c.to_csv(ROOT / "reports" / "churn_types.csv", index=False)
    con.close()


if __name__ == "__main__":
    main()