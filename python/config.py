from pathlib import Path

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
INTERIM = ROOT / "data" / "interim"
RAW = ROOT / "data" / "raw"

DATA_START = "2025-01-01"
DATA_END = "2026-06-30"

ZONES = list("ABCDEFGH")
ZONE_WEIGHTS = [0.14, 0.13, 0.14, 0.12, 0.12, 0.14, 0.11, 0.10]  # sums to 1.0

N_MERCHANTS = 300
N_RIDERS = 600

# New customers per month, months 1 to 18 (month 1 = Jan 2025).
# Q-1 = months 10-12 (5,700 total). Q0 = months 13-15 (7,410, which is +30%).
NEW_CUSTOMERS_PER_MONTH = [
    1000, 1100, 1200, 1250, 1300, 1400, 1500, 1600, 1700,   # months 1-9
    1900, 1900, 1900,                                         # months 10-12 (Q-1)
    2470, 2470, 2470,                                         # months 13-15 (Q0)
    2500, 2500, 2500,                                         # months 16-18
]

CHANNELS = ["paid_social", "organic", "search", "referral", "affiliate"]

# New-customer channel mix: paid_social, organic, search, referral, affiliate
MIX_EARLY = [0.15, 0.32, 0.21, 0.20, 0.12]   # months 1-9
MIX_Q1    = [0.20, 0.30, 0.20, 0.18, 0.12]   # months 10-12 (Q-1)
MIX_Q0    = [0.30, 0.30, 0.18, 0.12, 0.10]   # months 13-18


def channel_mix(month):
    if month <= 9:
        return MIX_EARLY
    if month <= 12:
        return MIX_Q1
    return MIX_Q0


# Average promo sensitivity (0 to 1) by channel. Discount-driven channels score higher.
PROMO_SENS_MEAN = {"paid_social": 0.55, "affiliate": 0.55, "search": 0.40,
                   "organic": 0.30, "referral": 0.25}

# Relative order demand for each hour 0 to 23 (lunch and dinner peaks).
# About 37% of orders fall between 18:00 and 21:30.
HOUR_WEIGHTS = [1, 0.5, 0.3, 0.2, 0.2, 0.5, 1, 2, 3, 3, 3, 5,
                9, 9, 6, 4, 4, 6, 11, 13, 13, 10, 5, 2]

# ---- Step 2.3: order behaviour ----
LATE_BASE = 0.12            # late probability outside the problem zones/hours
LATE_PEAK_Q1 = 0.14         # zones C,F, 18:00-21:30, months <= 12
LATE_PEAK_Q0 = 0.38         # same slots, months >= 13

# Underlying 90-day repeat probability of an on-time, non-flat first order
BASE_REPEAT = {"referral": 0.63, "organic": 0.54, "search": 0.46,
               "affiliate": 0.37, "paid_social": 0.34}
LATE_MULT = 0.5             # late first order halves repeat probability
FLAT_MULT = 0.33            # first_order_flat users repeat about a third as often
FLAT_SHARE_Q1 = 0.10        # share of first orders using first_order_flat (months <= 12)
FLAT_SHARE_Q0 = 0.35        # months >= 13
LATE_REPEAT_P = 0.20        # non-repeaters who still return after day 90

GROCERY_SHARE = 0.18
CANCEL_P = 0.04             # only for order number 3 and up

PROMO_P0 = 0.30             # promo use probability = (P0 + P1 * sensitivity) * multiplier
PROMO_P1 = 0.45
PROMO_Q0_MULT = 1.45        # months >= 13 (drives discount rate up)
PROMO_WEIGHTS = {2: 3, 3: 3, 4: 1, 5: 2, 6: 1.5, 7: 3, 8: 2, 9: 1, 10: 2, 12: 2}

# ---- Step 2.5: tickets and refunds ----
SUPPORT_COST = 2.50           # per order with at least one ticket (KPI doc)
SEVERE_OVER_MIN = 10          # "severely late" = 10+ min beyond the late threshold

# Ticket probability per valid order
TK_LATE_MILD, TK_LATE_SEVERE, TK_LATE_NONLATE = 0.12, 0.80, 0.004
TK_MISSING_FOOD, TK_MISSING_GROCERY, TK_MISSING_SPIKE = 0.003, 0.010, 0.50
TK_WRONG, TK_QUALITY, TK_PAYMENT, TK_OTHER = 0.005, 0.008, 0.005, 0.020

# Probability a ticket ends in a refund
RF_LATE_MILD, RF_LATE_SEVERE, RF_LATE_NONLATE = 0.25, 0.95, 0.20
REFUND_P = {"missing": 0.85, "wrong_item": 0.80, "quality": 0.50,
            "payment": 0.40, "other": 0.10}
# Refund size as a fraction of order value (low, high)
REFUND_FRAC = {"late": (0.30, 0.60), "missing": (0.15, 0.50), "wrong_item": (0.30, 0.70),
               "quality": (0.40, 1.00), "payment": (0.50, 1.00), "other": (0.20, 0.80)}

MISSING_AS_OTHER = 0.70       # share of missing-item tickets logged as category "other"
TEXT_NULL_P = 0.10            # share of tickets with no complaint text

# ---- Step 2.6: experiment ----
EXPERIMENT_ID = "EXP_WINBACK_2026Q2"
OFFER_COST = 5.0
EXP_MAX_PER_SEGMENT = 3000
EXP_LIFT = {"loyal_lapsing": 0.12, "deal_seeker": 0.0}   # planted lift (reorder rate, absolute)
EXP_REDEEM_BASE = 0.60       # share of "would have ordered anyway" treated customers who use the credit
EXP_EXTRA_ORDERS = 0.8       # mean extra orders in the window for customers the offer brought back


# ---- Step 2.7: data-quality injection rates ----
DQ_RATES = {
    1: 0.005,   # duplicate order_id (orders)
    2: 0.010,   # missing delivered_ts (delivery_events)
    3: 0.003,   # delivered_ts before picked_up_ts
    4: 0.002,   # order_value <= 0
    5: 0.020,   # zone text inconsistent
    6: 0.003,   # merchant_id not in merchants
    7: 0.002,   # summed ticket refunds exceed order_value
    8: 0.020,   # customers.first_order_date wrong
    9: 0.001,   # delivery time over 600 minutes
    10: 0.050,  # complaint_text empty string
    11: 0.003,  # orders.order_ts differs from placed_ts
    12: 0.010,  # status disagrees with ticket refunds
}
ZONE_VARIANTS = ["{z}", "{z_lower}", "Zone {z}", " {z} "]