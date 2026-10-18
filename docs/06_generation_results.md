# Generation Results (target vs achieved)

Generator frozen at git tag `generator-v1` (seed 42).

| Metric | Target | Achieved |
|---|---|---|
| GMV growth, Q0 vs Q-1 | +18% ±1.5 | +17.9% |
| 90-day repeat rate (Q-1 → Q0 cohorts) | 41% → 32% | 41.8% → 32.9% |
| Discount rate | 9% → 14% | 9.0% → 13.5% |
| Refund rate | 3.0% → 5.5% | 3.5% → 5.2% |
| Late rate | 12.5% → 14.5% | 12.2% → 14.3% |
| CM per order | falls 40-60% | $2.86 → $1.72 (-40%) |
| New customers | +30% | +30% (5,700 → 7,410) |
| Late first order vs on-time repeat | ~20% vs ~40% | 19% vs 39% |
| first_order_flat vs other repeat | ~15% vs ~40% | 14% vs 44% |
| first_order_flat CM per order | negative | -$1.46 (others +$2.39) |
| Loyal-but-lapsing lift | ~+12 pts | +12.3 pts (CI 7.8 to 16.9) |
| Deal-seeker lift | ~0 | +1.4 pts (CI -0.6 to 3.4) |

Row counts: customers 32,660; orders about 189,400 (raw, with duplicates); tickets about 15,600.
Hidden files in `data/interim/` (`*_latent.csv`, `customer_traits.csv`) are never read in Phase 3.