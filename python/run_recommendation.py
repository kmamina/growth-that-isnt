import duckdb
import numpy as np
import pandas as pd
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
pd.set_option("display.width", 170)
con = duckdb.connect(str(DB), read_only=True)
q = lambda s: con.execute(s).fetchdf()

# ---------- shared: 90-day CM per new customer ----------
c90 = q("""SELECT f.customer_id, f.q, f.zone, f.hr, f.is_late, f.repeat_90d, f.channel,
                  SUM(o.cm) AS cm90
           FROM v_first_orders f
           JOIN v_orders_q o ON o.customer_id = f.customer_id
            AND o.order_ts >= f.first_ts AND o.order_ts <= f.first_ts + INTERVAL 90 DAY
           GROUP BY 1,2,3,4,5,6,7""")
levers = []

# ---------- Lever 1: first_order_flat promo (Q0 new-customer cohort) ----------
g = pd.read_csv(ROOT / "reports" / "group_90d_cm.csv")
q0 = g[g.q == "Q0"].set_index("grp")
n_flat, cf = q0.loc["first_order_flat", "customers"], q0.loc["first_order_flat", "cm90"]
oth = q0.loc[["other_promo", "no_promo"]]
c_o = (oth.customers * oth.cm90).sum() / oth.customers.sum()
print("LEVER 1: remove first_order_flat (Q0 cohort of %d flat-promo customers)" % n_flat)
print("  90-day CM per customer: flat %.2f vs other new customers %.2f" % (cf, c_o))
rows = []
for L in (0.0, 0.2, 0.5, 1.0):
    rows.append((f"{int(L*100)}% of flat customers lost", round(n_flat * ((1 - L) * c_o * 0.8 - cf))))
print(pd.DataFrame(rows, columns=["scenario (stayers worth 80%)", "change in 90-day CM ($)"]).to_string(index=False))
l1_low, l1_mid = round(-n_flat * cf), rows[1][1]
levers.append(("1. Remove or redesign first_order_flat", "per quarter of new customers", l1_low, l1_mid,
               "Floor = every flat customer lost. Mid = 20% lost, stayers worth 80%.",
               "Medium: cost sign is measured, size depends on unmeasured loss rate. Pilot first."))

# ---------- Lever 2: C/F evening-peak lateness ----------
o = q("SELECT zone, order_ts, is_late, cm FROM v_orders_q WHERE q='Q0' AND is_late IS NOT NULL")
h = o.order_ts.dt.hour + o.order_ts.dt.minute / 60
pk = o.zone.isin(["C", "F"]) & (h >= 18) & (h < 21.5)
base_o = o[~pk].is_late.mean()
n_pk, late_pk = int(pk.sum()), o[pk].is_late.mean()
excess_o = n_pk * (late_pk - base_o)
gap = o[pk & (o.is_late == 0)].cm.mean() - o[pk & (o.is_late == 1)].cm.mean()
order_saving = excess_o * gap

pkf = ((c90.q == "Q0") & c90.zone.isin(["C", "F"]) & (c90.hr >= 18) & (c90.hr < 21.5) & c90.is_late.notna())
base_f = c90[(c90.q == "Q0") & ~pkf & c90.is_late.notna()].is_late.mean()
n_pf, late_pf = int(pkf.sum()), c90[pkf].is_late.mean()
excess_f = n_pf * (late_pf - base_f)
rep_on = c90[c90.is_late == 0].repeat_90d.mean()
rep_late = c90[c90.is_late == 1].repeat_90d.mean()
val_rep = c90[c90.repeat_90d == 1].cm90.mean() - c90[c90.repeat_90d == 0].cm90.mean()
retention = excess_f * (rep_on - rep_late) * val_rep
total2 = order_saving + retention
print("\nLEVER 2: bring C/F evening-peak lateness back to the baseline rate (Q0)")
print("  peak orders %d | late rate %.1f%% vs baseline %.1f%% | excess late orders %.0f"
      % (n_pk, 100 * late_pk, 100 * base_o, excess_o))
print("  CM gap, on-time minus late order (refunds, support cost included): $%.2f -> order saving $%.0f"
      % (gap, order_saving))
print("  excess late first orders %.0f | repeat on-time %.1f%% vs late %.1f%% | value of a repeater $%.2f -> retention $%.0f"
      % (excess_f, 100 * rep_on, 100 * rep_late, val_rep, retention))
print("  Total per quarter, full fix: $%.0f | half fix: $%.0f | break-even spend per peak order: $%.2f"
      % (total2, total2 / 2, total2 / n_pk))
levers.append(("2. Fix C/F evening-peak lateness", "per quarter", round(total2 / 2), round(total2),
               "Low = half the excess removed. High = all of it. Break-even spend per peak order = $%.2f" % (total2 / n_pk),
               "Medium: late-vs-on-time gap is large and tested, but cost of the fix is unknown."))

# ---------- Lever 3: two dark stores with missing items ----------
t = pd.read_csv(ROOT / "reports" / "ticket_themes.csv")
m = t[(t.theme == "missing_items") & (t.q == "Q0") & t.merchant_id.notna()].copy()
m["merchant_id"] = m.merchant_id.astype(int)
top2 = m.groupby("merchant_id").size().nlargest(2).index.tolist()
ref = q("SELECT ticket_id, refund_amount FROM clean_support_tickets")
m = m.merge(ref, on="ticket_id", how="left")
cost_t = m.refund_amount.fillna(0).mean() + 2.50
go = q("SELECT merchant_id, zone, COUNT(*) AS n FROM v_orders_q WHERE q='Q0' AND order_type='grocery' GROUP BY 1,2")
rate_other = (~m.zone.isin(["D", "G"])).sum() / go[~go.zone.isin(["D", "G"])].n.sum()
orders_top = go[go.merchant_id.isin(top2)].n.sum()
tk_top = int(m.merchant_id.isin(top2).sum())
excess_t = tk_top - orders_top * rate_other
saving3 = excess_t * cost_t
print("\nLEVER 3: stores %s" % top2)
print("  Q0 missing-item tickets there %d | grocery orders %d | baseline rate elsewhere %.1f per 100"
      % (tk_top, orders_top, 100 * rate_other))
print("  excess tickets %.0f x $%.2f (refund + support) = $%.0f per quarter" % (excess_t, cost_t, saving3))
levers.append(("3. Fix the two dark stores", "per quarter", round(saving3 * 0.5), round(saving3),
               "Refunds + support cost on excess tickets only. Low = half fixed.",
               "High on the cost, but it excludes any customer-loss effect, which the data does not link."))

# ---------- Lever 4: targeted win-back ----------
pol = pd.read_csv(ROOT / "reports" / "ab_policy.csv", index_col=0)
lo, hi = pol.loc["send to loyal only", "ci_low"], pol.loc["send to loyal only", "ci_high"]
print("\nLEVER 4: win-back offer to loyal lapsing (90-day net CM, pool of 932): $%.0f (CI %.0f to %.0f)"
      % (pol.loc["send to loyal only", "net CM ($)"], lo, hi))
levers.append(("4. Win-back offer, loyal lapsing only", "per 90 days", round(lo), round(hi),
               "95% interval of net CM. Break-even in 90 days.",
               "High that it moves behaviour, low that it pays back within 90 days. Pilot a smaller credit."))

# ---------- Context: channel quality ----------
ch = (c90[c90.q == "Q0"].groupby("channel")
      .agg(customers=("customer_id", "size"), repeat_90d=("repeat_90d", "mean"), cm90=("cm90", "mean")).round(2))
print("\nCHANNEL QUALITY (Q0 new customers, 90-day CM per customer; no CAC in the data)\n", ch)

out = pd.DataFrame(levers, columns=["lever", "basis", "low_$", "high_$", "assumption", "confidence"])
print("\nSUMMARY\n", out[["lever", "basis", "low_$", "high_$"]].to_string(index=False))
out.to_csv(ROOT / "reports" / "recommendation_levers.csv", index=False)
ch.to_csv(ROOT / "reports" / "channel_quality.csv")
con.close()