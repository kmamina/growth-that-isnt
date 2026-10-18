import duckdb
from config import RAW, ROOT

DB = ROOT / "data" / "zesto.duckdb"
TABLES = ["customers", "merchants", "riders", "promotions", "orders",
          "delivery_events", "support_tickets", "experiment_assignments"]


def main():
    con = duckdb.connect(str(DB))

    # 1. Load every raw CSV as a table named raw_<name>
    for t in TABLES:
        path = (RAW / f"{t}.csv").as_posix()
        con.execute(f"CREATE OR REPLACE TABLE raw_{t} AS "
                    f"SELECT * FROM read_csv_auto('{path}', header=true)")

    # 2. Row counts and column types
    print("ROW COUNTS")
    for t in TABLES:
        n = con.execute(f"SELECT COUNT(*) FROM raw_{t}").fetchone()[0]
        print(f"  raw_{t}: {n:,}")

    print("\nCOLUMN TYPES (orders, delivery_events)")
    for t in ["orders", "delivery_events"]:
        cols = con.execute(f"DESCRIBE raw_{t}").fetchall()
        print(f"  {t}:", ", ".join(f"{c[0]}:{c[1]}" for c in cols))

    # 3. Null counts, only columns that have nulls
    print("\nNULL COUNTS (columns with at least one null)")
    for t in TABLES:
        cols = [c[0] for c in con.execute(f"DESCRIBE raw_{t}").fetchall()]
        sel = ", ".join(f"COUNT(*) - COUNT({c}) AS {c}" for c in cols)
        row = con.execute(f"SELECT {sel} FROM raw_{t}").fetchdf().iloc[0]
        row = row[row > 0]
        print(f"  {t}:", dict(row) if len(row) else "none")

    # 4. First look at suspicious columns
    print("\nDISTINCT zone values in orders:",
          con.execute("SELECT COUNT(DISTINCT zone) FROM raw_orders").fetchone()[0])
    print(con.execute("SELECT status, COUNT(*) n FROM raw_orders GROUP BY 1 ORDER BY 2 DESC").fetchdf())
    print("\norders: rows vs distinct order_id:",
          con.execute("SELECT COUNT(*), COUNT(DISTINCT order_id) FROM raw_orders").fetchone())
    print("order_ts range:",
          con.execute("SELECT MIN(order_ts), MAX(order_ts) FROM raw_orders").fetchone())
    print("order_value min / max:",
          con.execute("SELECT MIN(order_value), MAX(order_value) FROM raw_orders").fetchone())
    con.close()


if __name__ == "__main__":
    main()