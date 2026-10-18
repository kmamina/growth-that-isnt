import numpy as np
import pandas as pd
from config import ZONES, ZONE_WEIGHTS, N_MERCHANTS, N_RIDERS

CUISINES = ["north_indian", "chinese", "pizza", "burgers",
            "biryani", "desserts", "healthy", "coffee_snacks"]


def make_merchants(rng):
    # Guarantee 2 dark stores in every zone, so zones D and G always have some
    # (finding 3 needs them). Fill the rest at random.
    combos = [(z, "dark_store") for z in ZONES for _ in range(2)]
    remaining = N_MERCHANTS - len(combos)
    zones = rng.choice(ZONES, size=remaining, p=ZONE_WEIGHTS)
    types = rng.choice(["restaurant", "dark_store"], size=remaining, p=[0.92, 0.08])
    combos += list(zip(zones, types))

    rows = []
    for i, (zone, mtype) in enumerate(combos, start=1):
        if mtype == "dark_store":
            cuisine = "grocery"
            prep = int(rng.integers(5, 10))
            commission = round(float(rng.uniform(0.10, 0.15)), 3)
            name = f"DarkStore_{i:03d}"
        else:
            cuisine = str(rng.choice(CUISINES))
            prep = int(rng.integers(12, 26))
            commission = round(float(rng.uniform(0.18, 0.28)), 3)
            name = f"Kitchen_{i:03d}"
        onboarded = pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 365)))
        rows.append(dict(
            merchant_id=i, merchant_name=name, merchant_type=mtype,
            cuisine_category=cuisine, zone=zone,
            avg_prep_time_target_min=prep, commission_pct=commission,
            onboarded_date=onboarded.date(),
        ))
    return pd.DataFrame(rows)


def make_riders(rng):
    zones = rng.choice(ZONES, size=N_RIDERS, p=ZONE_WEIGHTS)
    join_days = rng.integers(0, 760, size=N_RIDERS)  # 2024-03-01 up to about 2026-03-31
    rows = []
    for i in range(N_RIDERS):
        rows.append(dict(
            rider_id=i + 1,
            home_zone=zones[i],
            join_date=(pd.Timestamp("2024-03-01") + pd.Timedelta(days=int(join_days[i]))).date(),
            employment_type=str(rng.choice(["full_time", "part_time"], p=[0.6, 0.4])),
            active_flag=int(rng.random() < 0.92),
        ))
    return pd.DataFrame(rows)


def make_promotions():
    # promo_id, name, type, discount_value, start, end, min_order_value, audience
    data = [
        (1,  "Welcome Flat 6",    "first_order_flat", 6.0,  "2025-01-01", "2026-06-30", 12.0, "new_customers"),
        (2,  "Weekend 15 Off",    "pct_off",          0.15, "2025-01-01", "2026-06-30", 15.0, "all"),
        (3,  "Free Delivery",     "free_delivery",    0.0,  "2025-01-01", "2026-06-30", 18.0, "all"),
        (4,  "Family Bundle",     "bundle",           4.0,  "2025-03-01", "2026-06-30", 30.0, "all"),
        (5,  "Cashback 10",       "cashback",         0.10, "2025-02-01", "2026-06-30", 20.0, "all"),
        (6,  "Loyalty Credit",    "loyalty_credit",   3.0,  "2025-04-01", "2026-06-30", 15.0, "repeat_customers"),
        (7,  "Lunch 10 Off",      "pct_off",          0.10, "2025-01-01", "2026-06-30", 10.0, "all"),
        (8,  "Grocery Free Del",  "free_delivery",    0.0,  "2025-05-01", "2026-06-30", 25.0, "grocery_shoppers"),
        (9,  "Festive Bundle",    "bundle",           5.0,  "2025-10-01", "2025-11-15", 35.0, "all"),
        (10, "Winter Cashback",   "cashback",         0.12, "2025-12-01", "2026-02-28", 20.0, "all"),
        (11, "Win-back $5 Credit", "loyalty_credit",  5.0,  "2026-04-01", "2026-06-30", 6.0,  "experiment_treatment"),
        (12, "Referral Credit",   "loyalty_credit",   4.0,  "2025-01-01", "2026-06-30", 12.0, "referred_customers"),
    ]
    cols = ["promo_id", "promo_name", "promo_type", "discount_value",
            "start_date", "end_date", "min_order_value", "target_audience"]
    df = pd.DataFrame(data, columns=cols)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.date
    return df