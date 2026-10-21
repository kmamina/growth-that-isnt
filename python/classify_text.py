import re
import duckdb
import pandas as pd
from config import ROOT

DB = ROOT / "data" / "zesto.duckdb"

# Ordered rules: first match wins. Patterns are lower-case regexes.
RULES = [
    ("missing_items", r"missing|short by|not inside|did not arrive|not in the bag|only received|not delivered|felt light|forgot|incomplete"),
    ("wrong_item",    r"wrong item|someone else|different size|asked for|instead of"),
    ("payment_issue", r"charged|payment|refund to my card|wrong amount|billed"),
    ("late_delivery", r"\blate\b|delay|over an hour|so slow|longer than|lost and|still waiting|forever"),
    ("food_quality",  r"stale|not fresh|leaking|tasted off|damaged|soggy"),
    ("rider_behaviour", r"impolite|shouted"),
    ("app_account",   r"app crashed|promo code|invoice|address|phone number|order history|loyalty points|freez"),
]


def classify(text):
    if text is None or (isinstance(text, float) and pd.isna(text)) or not str(text).strip():
        return "no_text"
    t = str(text).lower()
    for theme, pat in RULES:
        if re.search(pat, t):
            return theme
    return "other_unclear"


def main():
    con = duckdb.connect(str(DB), read_only=True)
    df = con.execute("""
        SELECT t.ticket_id, t.order_id, t.category, t.complaint_text,
               o.q, o.zone, o.order_type, o.merchant_id
        FROM clean_support_tickets t
        LEFT JOIN v_orders_q o USING (order_id)""").fetchdf()
    con.close()

    df["theme"] = df.complaint_text.map(classify)
    print("Theme counts:\n", df.theme.value_counts())
    print("\nCategory x theme (rows = original category):")
    print(pd.crosstab(df.category, df.theme))

    oth = df[df.category == "other"]
    print("\nShare of 'other' tickets that are really missing_items, by quarter:")
    print((oth.theme == "missing_items").groupby(oth.q).mean().round(3))

    print("\nMissing-item tickets per grocery order, by zone and quarter:")
    g = pd.read_csv(ROOT / "reports" / "grocery_orders_by_zone_q.csv") if False else None
    mt = df[(df.theme == "missing_items") & df.q.isin(["Q-1", "Q0"])]
    print(mt.groupby(["zone", "q"]).size().unstack().fillna(0).astype(int))

    df.to_csv(ROOT / "reports" / "ticket_themes.csv", index=False)


if __name__ == "__main__":
    main()