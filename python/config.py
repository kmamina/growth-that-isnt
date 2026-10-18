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