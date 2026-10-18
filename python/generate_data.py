import numpy as np
from config import SEED, INTERIM
from gen_dimensions import make_merchants, make_riders, make_promotions


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    merchants = make_merchants(rng)
    riders = make_riders(rng)
    promotions = make_promotions()

    merchants.to_csv(INTERIM / "merchants.csv", index=False)
    riders.to_csv(INTERIM / "riders.csv", index=False)
    promotions.to_csv(INTERIM / "promotions.csv", index=False)

    print("merchants:", merchants.shape, "| riders:", riders.shape, "| promotions:", promotions.shape)
    print("\nMerchant type counts:\n", merchants["merchant_type"].value_counts())
    print("\nDark stores per zone:\n", merchants[merchants.merchant_type == "dark_store"]["zone"].value_counts().sort_index())


if __name__ == "__main__":
    main()