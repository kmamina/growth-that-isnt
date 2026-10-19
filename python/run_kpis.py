import duckdb
import pandas as pd
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
SQL = (ROOT / "sql" / "03_kpis.sql").read_text()


def main():
    con = duckdb.connect(str(DB))
    for s in [x.strip() for x in SQL.split(";") if "CREATE" in x]:
        con.execute("\n".join(l for l in s.splitlines() if not l.strip().startswith("--")))

    k = con.execute("SELECT * FROM v_kpi_quarter ORDER BY q").fetchdf()
    print(k.to_string(index=False))
    q = k.set_index("q")
    print("\nGMV growth Q0 vs Q-1: %.1f%%" % (100 * (q.gmv["Q0"] / q.gmv["Q-1"] - 1)))
    print("CM per order change: %.0f%%" % (100 * (q.cm_per_order["Q0"] / q.cm_per_order["Q-1"] - 1)))

    r = con.execute("SELECT * FROM v_repeat_cohort").fetchdf()
    r["q"] = r.cohort_month.map(lambda m: "Q-1" if m in ("2025-10", "2025-11", "2025-12")
                                else ("Q0" if m in ("2026-01", "2026-02", "2026-03") else "other"))
    r["repeaters"] = r.cohort_size * r.repeat_90d
    g = r[r.q != "other"].groupby("q")[["cohort_size", "repeaters"]].sum()
    print("\n90-day repeat rate by quarter cohort:\n", (g.repeaters / g.cohort_size).round(3))
    print("\nRepeat rate by cohort month:\n", r[["cohort_month", "cohort_size", "repeat_90d"]].to_string(index=False))
    k.to_csv(ROOT / "reports" / "kpi_by_quarter.csv", index=False)
    r.to_csv(ROOT / "reports" / "repeat_by_cohort.csv", index=False)
    con.close()


if __name__ == "__main__":
    main()