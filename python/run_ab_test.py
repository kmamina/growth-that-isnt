import duckdb
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
SNAP, END = "2026-04-01", "2026-06-30"       # 90-day window, end exclusive
pd.set_option("display.width", 170)

con = duckdb.connect(str(DB), read_only=True)
a = con.execute("SELECT customer_id, variant, offer_cost FROM clean_experiment_assignments").fetchdf()
w = con.execute(f"""SELECT customer_id, COUNT(*) AS orders_w, SUM(cm) AS cm_w
                    FROM v_orders_q WHERE order_ts >= '{SNAP}' AND order_ts < '{END}'
                    GROUP BY 1""").fetchdf()
con.close()

seg = pd.read_csv(ROOT / "reports" / "customer_segments.csv")[
    ["customer_id", "rule_segment", "lapsing", "orders", "promo_share", "recency_days", "cm"]
].rename(columns={"orders": "pre_orders", "cm": "pre_cm"})

d = a.merge(seg, on="customer_id", how="left").merge(w, on="customer_id", how="left")
d[["orders_w", "cm_w"]] = d[["orders_w", "cm_w"]].fillna(0)
d["reorder"] = (d.orders_w > 0).astype(int)

print("Assigned customers by segment (recomputed from cleaned data) and arm:")
print(pd.crosstab(d.rule_segment.fillna("no valid pre-period order"), d.variant))
print("Assigned but not lapsing:", int((d.lapsing == False).sum()))
dropped = d[~d.rule_segment.isin(["loyal", "deal_seeker"])]
d = d[d.rule_segment.isin(["loyal", "deal_seeker"])].copy()
print("Excluded (segment changed after cleaning):", len(dropped), "| analysed:", len(d))

# ---- 1. Balance check on pre-period behaviour (standardised mean difference) ----
def smd(g, col):
    t, c = g[g.variant == "treatment"][col], g[g.variant == "control"][col]
    return (t.mean() - c.mean()) / np.sqrt((t.var() + c.var()) / 2)

bal = pd.DataFrame({s: {col: smd(d[d.rule_segment == s], col)
                        for col in ["pre_orders", "promo_share", "recency_days", "pre_cm"]}
                    for s in ["loyal", "deal_seeker"]}).round(3)
print("\nBALANCE (standardised mean difference, treatment minus control; |x| < 0.2 is fine):\n", bal)

# ---- 2. Lift, margin and cost by segment ----
pools = {s: int(((seg.rule_segment == s) & seg.lapsing).sum()) for s in ["loyal", "deal_seeker"]}
rows = []
for s in ["loyal", "deal_seeker"]:
    g = d[d.rule_segment == s]
    t, c = g[g.variant == "treatment"], g[g.variant == "control"]
    n1, n0 = len(t), len(c)
    p1, p0 = t.reorder.mean(), c.reorder.mean()
    lift = p1 - p0
    se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    pval = 2 * (1 - stats.norm.cdf(abs(lift / se)))
    dcm = t.cm_w.mean() - c.cm_w.mean()           # offer cost is already inside cm (as the discount)
    se_cm = np.sqrt(t.cm_w.var() / n1 + c.cm_w.var() / n0)
    spend, redeem = t.offer_cost.sum(), int((t.offer_cost > 0).sum())
    inc = lift * n1
    rows.append(dict(segment=s, n_treat=n1, n_control=n0, control_rate=p0, treat_rate=p1,
                     lift_pts=100 * lift, ci_low=100 * (lift - 1.96 * se), ci_high=100 * (lift + 1.96 * se),
                     p_value=pval, mde_pts=100 * 2.8 * np.sqrt(p0 * (1 - p0) * (1 / n1 + 1 / n0)),
                     redeemers=redeem, offer_spend=spend, incremental_reorders=inc,
                     redeemers_not_incremental=redeem - inc,
                     cost_per_incremental=(spend / inc) if (pval < 0.05 and inc > 0) else np.nan,
                     extra_orders_per_treated=t.orders_w.mean() - c.orders_w.mean(),
                     gross_cm_per_treated=dcm + spend / n1, net_cm_per_treated=dcm,
                     net_ci_low=dcm - 1.96 * se_cm, net_ci_high=dcm + 1.96 * se_cm,
                     se_cm=se_cm, lift_se=se, pool=pools[s]))
res = pd.DataFrame(rows).set_index("segment")
show = res.drop(columns=["se_cm", "lift_se"]).round(3).T
print("\nA/B RESULTS (reorder = valid order from 2026-04-01 up to 2026-06-30 00:00)\n", show)

# ---- 3. Do the segments really respond differently? ----
l, ds = res.loc["loyal"], res.loc["deal_seeker"]
z = (l.lift_pts / 100 - ds.lift_pts / 100) / np.sqrt(l.lift_se ** 2 + ds.lift_se ** 2)
print("\nDifference in lift, loyal minus deal seekers: %.1f pts (z = %.2f, p = %.4f)"
      % (l.lift_pts - ds.lift_pts, z, 2 * (1 - stats.norm.cdf(abs(z)))))

# ---- 4. Policy comparison: total 90-day net CM if applied to the whole eligible pool ----
def policy(segs):
    tot = sum(res.loc[s, "pool"] * res.loc[s, "net_cm_per_treated"] for s in segs)
    se = np.sqrt(sum((res.loc[s, "pool"] * res.loc[s, "se_cm"]) ** 2 for s in segs))
    return tot, tot - 1.96 * se, tot + 1.96 * se

pol = pd.DataFrame({"send to loyal only": policy(["loyal"]),
                    "send to loyal + deal seekers": policy(["loyal", "deal_seeker"])},
                   index=["net CM ($)", "ci_low", "ci_high"]).round(0).T
print("\nPOLICY (90-day net CM, scaled to pools of %d loyal and %d deal-seeker lapsing customers)\n"
      % (pools["loyal"], pools["deal_seeker"]), pol)

# ---- 5. Chart ----
fig, ax = plt.subplots(1, 2, figsize=(9.5, 3.8))
names = ["loyal lapsing", "deal seekers"]
cols = ["#4C78A8", "#E45756"]
ax[0].bar(names, res.lift_pts, yerr=[res.lift_pts - res.ci_low, res.ci_high - res.lift_pts],
          capsize=6, color=cols)
ax[0].axhline(0, color="k", lw=0.8)
ax[0].set_title("Reorder lift (points), 95% CI")
ax[1].bar(names, res.net_cm_per_treated,
          yerr=[res.net_cm_per_treated - res.net_ci_low, res.net_ci_high - res.net_cm_per_treated],
          capsize=6, color=cols)
ax[1].axhline(0, color="k", lw=0.8)
ax[1].set_title("Net 90-day CM per treated customer ($), 95% CI")
plt.tight_layout()
plt.savefig(ROOT / "images" / "ab_test_results.png", dpi=150)
plt.close()
res.round(4).to_csv(ROOT / "reports" / "ab_test_results.csv")
bal.to_csv(ROOT / "reports" / "ab_balance_check.csv")
pol.to_csv(ROOT / "reports" / "ab_policy.csv")
print("\nSaved reports/ab_test_results.csv and images/ab_test_results.png")