import duckdb
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
IMG = ROOT / "images"
pd.set_option("display.width", 160)

t = pd.read_csv(ROOT / "reports" / "ticket_themes.csv")
t = t[t.q.isin(["Q-1", "Q0"])]
miss = t[t.theme == "missing_items"]
oth = t[t.category == "other"]

# ---- headline numbers ----
counts = miss.groupby(["q", "category"]).size().unstack(fill_value=0)
counts["total"] = counts.sum(axis=1)
counts["pct_hidden_in_other"] = (counts["other"] / counts["total"] * 100).round(1)
print("Missing-item tickets by quarter (category as filed):\n", counts)
share = (oth.theme == "missing_items").groupby(oth.q).mean() * 100
print("\nShare of 'other' tickets that are really missing items (%):\n", share.round(1))

# ---- chart 1: filed vs hidden ----
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
counts[["missing_item", "other"]].rename(
    columns={"missing_item": "filed as missing_item", "other": "hidden in 'other'"}
).plot.bar(stacked=True, ax=ax[0], rot=0, color=["#4C78A8", "#E45756"])
ax[0].set_title("Missing-item tickets by category filed")
ax[0].set_xlabel("")
share.plot.bar(ax=ax[1], rot=0, color="#E45756")
ax[1].set_title("Share of 'other' tickets that are missing items (%)")
ax[1].set_xlabel("")
plt.tight_layout()
plt.savefig(IMG / "hidden_theme_overview.png", dpi=150)
plt.close()

# ---- chart 2: rate per 100 grocery orders by zone ----
con = duckdb.connect(str(DB), read_only=True)
g = con.execute("""SELECT zone, q, COUNT(*) AS grocery_orders FROM v_orders_q
                   WHERE order_type='grocery' AND q IN ('Q-1','Q0') GROUP BY 1,2""").fetchdf()
m = con.execute("SELECT merchant_id, merchant_name, zone AS m_zone FROM clean_merchants").fetchdf()
con.close()

num = miss.groupby(["zone", "q"]).size().rename("tickets").reset_index()
r = g.merge(num, on=["zone", "q"], how="left").fillna({"tickets": 0})
r["per_100_orders"] = r.tickets / r.grocery_orders * 100
piv = r.pivot(index="zone", columns="q", values="per_100_orders").round(1)
print("\nMissing-item tickets per 100 grocery orders:\n", piv)
piv.plot.bar(figsize=(8, 4), rot=0, color=["#9ecae1", "#E45756"])
plt.title("Missing-item tickets per 100 grocery orders, by zone")
plt.ylabel("per 100 grocery orders")
plt.tight_layout()
plt.savefig(IMG / "hidden_theme_by_zone.png", dpi=150)
plt.close()

# ---- chart 3: which stores in Q0 ----
q0 = miss[(miss.q == "Q0") & miss.merchant_id.notna()].copy()
q0["merchant_id"] = q0.merchant_id.astype(int)
top = (q0.groupby("merchant_id").size().rename("tickets").reset_index()
       .merge(m, on="merchant_id").sort_values("tickets", ascending=False).head(8))
top["label"] = top.merchant_name + " (zone " + top.m_zone + ")"
print("\nTop stores for missing-item tickets in Q0:\n", top[["label", "tickets"]].to_string(index=False))
print("Top 2 stores' share of Q0 missing-item tickets: %.0f%%" % (100 * top.tickets.head(2).sum() / len(q0)))
top.iloc[::-1].plot.barh(x="label", y="tickets", legend=False, figsize=(8, 4), color="#E45756")
plt.title("Q0 missing-item tickets by store")
plt.xlabel("tickets")
plt.ylabel("")
plt.tight_layout()
plt.savefig(IMG / "hidden_theme_by_store.png", dpi=150)
plt.close()
print("\nCharts saved in images/")