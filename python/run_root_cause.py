import duckdb
import pandas as pd
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
SQL = (ROOT / "sql" / "05_root_cause.sql").read_text()
pd.set_option("display.width", 160)

PEAK = ("EXTRACT(hour FROM order_ts)+EXTRACT(minute FROM order_ts)/60.0")


def main():
    con = duckdb.connect(str(DB))
    for s in [x.strip() for x in SQL.split(";") if "CREATE" in x]:
        con.execute("\n".join(l for l in s.splitlines() if not l.strip().startswith("--")))
    q = lambda sql: con.execute(sql).fetchdf()

    print("H1 VP GROWTH: repeat rate by channel and quarter cohort")
    h1 = q("""SELECT channel, q, ROUND(AVG(repeat_90d),3) AS repeat_rate
              FROM v_first_orders WHERE q IN ('Q-1','Q0') GROUP BY 1,2""")
    print(h1.pivot(index="channel", columns="q", values="repeat_rate"))
    mix = q("""SELECT q, channel, COUNT(*) AS n FROM v_first_orders
               WHERE q IN ('Q-1','Q0') GROUP BY 1,2""")
    mix["share"] = mix.n / mix.groupby("q").n.transform("sum")
    print("\nNew-customer channel mix:\n",
          mix.pivot(index="channel", columns="q", values="share").round(3))

    print("\nH2 COO: first order late vs on-time, repeat rate")
    print(q("""SELECT is_late, COUNT(*) AS n, ROUND(AVG(repeat_90d),3) AS repeat_rate
               FROM v_first_orders WHERE is_late IS NOT NULL GROUP BY 1 ORDER BY 1"""))

    print("\nLate rate by zone group, slot and quarter")
    print(q(f"""SELECT CASE WHEN zone IN ('C','F') THEN 'C/F' ELSE 'other' END AS zones,
                       CASE WHEN {PEAK} >= 18 AND {PEAK} < 21.5 THEN 'peak' ELSE 'off-peak' END AS slot,
                       q, ROUND(AVG(is_late),3) AS late_rate
                FROM v_orders_q WHERE q IN ('Q-1','Q0') AND is_late IS NOT NULL
                GROUP BY 1,2,3 ORDER BY 1,2,3"""))

    print("\nRider assignment and merchant prep minutes")
    print(q("""SELECT CASE WHEN o.zone IN ('C','F') THEN 'C/F' ELSE 'other' END AS zones, o.q,
                      ROUND(AVG(date_diff('second', d.placed_ts, d.rider_assigned_ts)/60.0),2) AS assign_min,
                      ROUND(AVG(date_diff('second', d.merchant_accepted_ts, d.food_ready_ts)/60.0),2) AS prep_min
               FROM v_orders_q o JOIN clean_delivery_events d USING (order_id)
               WHERE o.q IN ('Q-1','Q0') GROUP BY 1,2 ORDER BY 1,2"""))

    print("\nH3 CFO: promo type on first orders")
    print(q("""SELECT COALESCE(promo_type,'no promo') AS promo_type, COUNT(*) AS n,
                      ROUND(AVG(repeat_90d),3) AS repeat_rate, ROUND(AVG(cm),2) AS cm_per_order
               FROM v_first_orders GROUP BY 1 ORDER BY n DESC"""))
    print("\nShare of first orders using first_order_flat")
    print(q("""SELECT q, ROUND(AVG(CASE WHEN promo_type='first_order_flat' THEN 1 ELSE 0 END),3) AS share
               FROM v_first_orders WHERE q IN ('Q-1','Q0') GROUP BY 1 ORDER BY 1"""))

    print("\nH4 CX: ticket categories by quarter")
    print(q("""SELECT o.q, t.category, COUNT(*) AS tickets
               FROM clean_support_tickets t JOIN v_orders_q o USING (order_id)
               WHERE o.q IN ('Q-1','Q0') GROUP BY 1,2 ORDER BY 1,3 DESC"""))
    con.close()


if __name__ == "__main__":
    main()