import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"
SNAP = pd.Timestamp("2026-04-01")
pd.set_option("display.width", 170)

con = duckdb.connect(str(DB), read_only=True)
df = con.execute("""
    SELECT customer_id, COUNT(*) AS orders, SUM(order_value) AS gmv, SUM(cm) AS cm,
           AVG(CASE WHEN discount_amount > 0 THEN 1.0 ELSE 0.0 END) AS promo_share,
           AVG(is_late) AS late_share, AVG(is_refunded) AS refund_share,
           MIN(order_ts) AS first_ts, MAX(order_ts) AS last_ts
    FROM v_orders_q WHERE order_ts < '2026-04-01' GROUP BY 1""").fetchdf()
con.close()

df[["late_share", "refund_share"]] = df[["late_share", "refund_share"]].fillna(0)
df["recency_days"] = (SNAP - df.last_ts).dt.days
df["cm_per_order"] = df.cm / df.orders
print("Customers with a valid order before 2026-04-01:", len(df))

# ---- A. Business rule segments (KPI/planted-findings definitions) ----
df["lapsing"] = df.last_ts < pd.Timestamp("2026-02-15")     # no order in 45 days before snapshot
base = np.select([df.promo_share >= 0.6, (df.orders >= 4) & (df.promo_share <= 0.2)],
                 ["deal_seeker", "loyal"], default="other")
df["rule_segment"] = base
print("\nRULE SEGMENTS x lapsing")
print(pd.crosstab(df.rule_segment, df.lapsing, margins=True))

prof = (df.groupby(["rule_segment", "lapsing"])
        .agg(customers=("customer_id", "size"), orders=("orders", "mean"),
             promo_share=("promo_share", "mean"), cm_per_order=("cm_per_order", "mean"),
             cm_per_customer=("cm", "mean"), late_share=("late_share", "mean")).round(2))
print("\nPROFILE BY RULE SEGMENT\n", prof)

# ---- B. RFM scores (1 to 5) ----
df["R"] = pd.qcut(df.recency_days.rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
df["F"] = pd.qcut(df.orders.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
df["M"] = pd.qcut(df.gmv.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
df["rfm_segment"] = np.select(
    [(df.R >= 4) & (df.F >= 4), (df.R <= 2) & (df.F >= 4),
     (df.R >= 4) & (df.F <= 2), (df.R <= 2) & (df.F <= 2)],
    ["champions", "at_risk_high_freq", "new_or_promising", "hibernating"], default="middle")
rfm = (df.groupby("rfm_segment")
       .agg(customers=("customer_id", "size"), recency_days=("recency_days", "mean"),
            orders=("orders", "mean"), cm_per_customer=("cm", "mean"),
            promo_share=("promo_share", "mean")).round(2).sort_values("customers", ascending=False))
print("\nRFM SEGMENTS\n", rfm)

# ---- C. k-means clustering (discovery, no business rules) ----
X = pd.DataFrame({"log_recency": np.log1p(df.recency_days), "log_orders": np.log1p(df.orders),
                  "promo_share": df.promo_share, "late_share": df.late_share,
                  "refund_share": df.refund_share})
Z = StandardScaler().fit_transform(X)
for k in (3, 4, 5, 6):
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(Z)
    print(f"k={k}: silhouette {silhouette_score(Z, km.labels_, sample_size=5000, random_state=42):.3f}")
km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(Z)
df["cluster"] = km.labels_
cl = (df.groupby("cluster")
      .agg(customers=("customer_id", "size"), recency_days=("recency_days", "mean"),
           orders=("orders", "mean"), promo_share=("promo_share", "mean"),
           late_share=("late_share", "mean"), cm_per_order=("cm_per_order", "mean"),
           cm_per_customer=("cm", "mean")).round(2))
print("\nK-MEANS CLUSTERS (k=4)\n", cl)
print("\nClusters vs rule segments:\n", pd.crosstab(df.cluster, df.rule_segment))

out = df[["customer_id", "orders", "gmv", "cm", "promo_share", "late_share", "refund_share",
          "recency_days", "lapsing", "rule_segment", "R", "F", "M", "rfm_segment", "cluster"]]
out.to_csv(ROOT / "reports" / "customer_segments.csv", index=False)
prof.to_csv(ROOT / "reports" / "segment_profile.csv")
rfm.to_csv(ROOT / "reports" / "rfm_segments.csv")
cl.to_csv(ROOT / "reports" / "cluster_profile.csv")
print("\nSaved reports/customer_segments.csv")