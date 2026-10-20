import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
pd.set_option("display.width", 160)


def load():
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""
        SELECT f.customer_id, f.q, f.zone, f.order_type, f.is_late, f.repeat_90d,
               f.hr, f.channel, f.promo_type,
               date_diff('second', d.placed_ts, d.rider_assigned_ts) / 60.0 AS assign_min,
               date_diff('second', d.merchant_accepted_ts, d.food_ready_ts) / 60.0 AS prep_min
        FROM v_first_orders f
        JOIN v_orders_q o ON o.customer_id = f.customer_id AND o.order_ts = f.first_ts
        JOIN clean_delivery_events d ON d.order_id = o.order_id
        WHERE f.q IN ('Q-1','Q0') AND f.is_late IS NOT NULL""").fetchdf()
    con.close()
    df["late"] = df.is_late.astype(int)
    df["flat"] = (df.promo_type == "first_order_flat").astype(int)
    df["other_promo"] = (df.promo_type.notna() & (df.promo_type != "first_order_flat")).astype(int)
    df["cf"] = df.zone.isin(["C", "F"]).astype(int)
    df["peak"] = ((df.hr >= 18) & (df.hr < 21.5)).astype(int)
    df["grocery"] = (df.order_type == "grocery").astype(int)
    df["q0"] = (df.q == "Q0").astype(int)
    return df


def odds(m):
    ci = np.exp(m.conf_int())
    out = pd.DataFrame({"odds_ratio": np.exp(m.params), "ci_low": ci[0], "ci_high": ci[1],
                        "p_value": m.pvalues}).round(3)
    return out.drop(index="Intercept")


def main():
    df = load()
    base_f = ("repeat_90d ~ late + flat + other_promo + cf + peak + grocery"
              " + C(channel, Treatment('organic'))")

    m1 = smf.logit(base_f, df).fit(disp=0)
    print(f"MODEL 1: n = {len(df):,}. Odds ratio below 1 = lowers repeat.")
    t1 = odds(m1)
    print(t1)
    t1.to_csv(ROOT / "reports" / "regression_odds_ratios.csv")

    m2 = smf.logit(base_f + " + q0", df).fit(disp=0)
    print("\nMODEL 2: add a Q0 flag. Is anything left unexplained?")
    print(odds(m2).loc[["q0"]])

    m3 = smf.logit(base_f + " + assign_min + prep_min", df).fit(disp=0)
    print("\nMODEL 3: add rider assignment and prep minutes (finding 5 test)")
    print(odds(m3).loc[["late", "assign_min", "prep_min"]])

    # ---- decomposition: Q0 population, one factor set to its Q-1 distribution ----
    q1 = df[df.q == "Q-1"]
    q0 = df[df.q == "Q0"]
    act1, act0 = q1.repeat_90d.mean(), q0.repeat_90d.mean()
    p0 = m1.predict(q0).mean()
    print(f"\nDECOMPOSITION. Actual Q-1 {act1:.3f}, actual Q0 {act0:.3f}, "
          f"drop {100*(act1-act0):.1f} pts; model Q0 {p0:.3f}")

    def swap_binary(col):
        s = q1[col].mean()
        a, b = q0.copy(), q0.copy()
        a[col], b[col] = 1, 0
        return s * m1.predict(a).mean() + (1 - s) * m1.predict(b).mean()

    rows = []
    for col, label in [("flat", "first_order_flat share"), ("late", "late first-order share")]:
            rows.append((label, 100 * (swap_binary(col) - p0)))
    mix = q1.channel.value_counts(normalize=True)
    cf_ch = 0
    for ch, share in mix.items():
        d = q0.copy()
        d["channel"] = ch
        cf_ch += share * m1.predict(d).mean()
    rows.append(("channel mix", 100 * (cf_ch - p0)))
    res = pd.DataFrame(rows, columns=["factor", "pts_of_repeat_rate_lost"]).round(1)
    print(res.to_string(index=False))
    print("Factors overlap (e.g. paid-social customers use the flat promo more), so these don't sum exactly to the drop.")
    res.to_csv(ROOT / "reports" / "repeat_drop_decomposition.csv", index=False)

    print("\nLocal view: first-order repeat rate in C/F evening peak vs everywhere else")
    df["slot"] = np.where((df.cf == 1) & (df.peak == 1), "C/F peak", "everywhere else")
    print(df.pivot_table(index="slot", columns="q", values="repeat_90d", aggfunc="mean").round(3))


if __name__ == "__main__":
    main()