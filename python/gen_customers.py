import numpy as np
import pandas as pd
from config import (ZONES, ZONE_WEIGHTS, DATA_START, NEW_CUSTOMERS_PER_MONTH,
                    CHANNELS, channel_mix, PROMO_SENS_MEAN, HOUR_WEIGHTS)


def make_customers(rng):
    month0 = pd.Timestamp(DATA_START)
    hour_p = np.array(HOUR_WEIGHTS, dtype=float)
    hour_p = hour_p / hour_p.sum()

    parts = []
    for m, n in enumerate(NEW_CUSTOMERS_PER_MONTH, start=1):
        start = month0 + pd.DateOffset(months=m - 1)
        end = month0 + pd.DateOffset(months=m)
        days_in_month = (end - start).days

        channels = rng.choice(CHANNELS, size=n, p=channel_mix(m))
        days = rng.integers(0, days_in_month, size=n)
        hours = rng.choice(24, size=n, p=hour_p)
        minutes = rng.integers(0, 60, size=n)
        seconds = rng.integers(0, 60, size=n)
        first_ts = (start + pd.to_timedelta(days, unit="D")
                    + pd.to_timedelta(hours, unit="h")
                    + pd.to_timedelta(minutes, unit="m")
                    + pd.to_timedelta(seconds, unit="s"))

        means = np.array([PROMO_SENS_MEAN[c] for c in channels])
        part = pd.DataFrame({
            "first_order_ts": first_ts,
            "cohort_month": m,
            "acquisition_channel": channels,
            "home_zone": rng.choice(ZONES, size=n, p=ZONE_WEIGHTS),
            "device": rng.choice(["ios", "android", "web"], size=n, p=[0.45, 0.45, 0.10]),
            "is_subscriber": (rng.random(n) < 0.06).astype(int),
            "signup_lead_days": rng.integers(0, 3, size=n),
            # hidden traits
            "promo_sensitivity": rng.beta(means * 5, (1 - means) * 5),
            "orders_per_month": np.clip(rng.gamma(2.0, 1.1, size=n), 0.2, 10.0),
            "lifetime_days": (rng.exponential(240, size=n) + 30).round(),
            "will_reduce": rng.random(n) < 0.25,
        })
        parts.append(part)

    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values("first_order_ts").reset_index(drop=True)
    df["customer_id"] = np.arange(1, len(df) + 1)

    df["first_order_date"] = df["first_order_ts"].dt.date
    df["signup_date"] = (df["first_order_ts"] - pd.to_timedelta(df["signup_lead_days"], unit="D")).dt.date

    customers = df[["customer_id", "signup_date", "acquisition_channel", "home_zone",
                    "first_order_date", "device", "is_subscriber"]].copy()
    traits = df[["customer_id", "first_order_ts", "cohort_month", "promo_sensitivity",
                 "orders_per_month", "lifetime_days", "will_reduce"]].copy()
    return customers, traits
