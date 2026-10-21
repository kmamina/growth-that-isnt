# Phase 5 Findings: Promos, Segments, the A/B Test and Priced Levers

## 1. Segments (who is worth saving?)

| Segment (lapsing = no order since 2026-02-15) | Customers | Takeaway |
|---|---|---|
| Loyal, lapsing | 932 | Historically $36.78 CM per customer. Matches the A/B test pool. |
| Deal seekers, lapsing | 6,962 | Negative CM per order (-$0.38). Not worth a discount. |
| Other, lapsing | 8,093 | Healthy ($3.84 per order) and **not tested** in the experiment. |
| RFM `at_risk_high_freq` | 2,496 | 8.6 orders each, $24.39 CM each, quiet for about 226 days. |
| K-means cluster 1 | 8,725 | 1.3 orders, 98% promo, $0.28 CM per customer. |
| K-means cluster 3 | 726 | 67% of their orders were late, -$10.91 CM per customer. Needs an operational fix, not a coupon. |

K-means: k=4 chosen for interpretability (silhouette 0.397). Silhouette was slightly higher at k=5 and k=6 (0.452, 0.458), so k=4 is not claimed to be optimal.

## 2. A/B test: $5 win-back credit

Outcome: a valid order from 2026-04-01 up to 2026-06-30 00:00 (90 days). Randomised 50/50 within segment. Balance check: all standardised mean differences below 0.09.

| Measure | Loyal, lapsing | Deal seekers |
|---|---|---|
| Customers (treatment / control) | 465 / 467 | 1,498 / 1,499 |
| Control reorder rate | 9.4% | 7.5% |
| Treatment reorder rate | 21.9% | 8.9% |
| Lift | **+12.5 pts** (95% CI 7.9 to 17.1, p < 0.001) | +1.4 pts (95% CI -0.6 to 3.4, p = 0.16) |
| Minimum detectable effect | 5.4 pts | 2.7 pts |
| Offer spend | $420 (84 redeemers) | $400 (80 redeemers) |
| Cost per incremental reorder | $7.22 | not reported (lift not significant) |
| Net 90-day CM per treated customer | +$0.17 (CI -0.25 to 0.60) | +$0.01 (CI -0.23 to 0.25) |

- Lift differs by segment: 11.1 points (z = 4.35, p < 0.0001).
- Policy view, scaled to the full lapsing pools: send to loyal only = +$161 net CM (CI -235 to 556).

## 3. Priced levers

| Lever | Basis | Low ($) | High ($) | Confidence |
|---|---|---|---|---|
| 1. Remove or redesign `first_order_flat` | per quarter of new customers | 910 | 11,708 | Medium: cost sign is measured, size depends on an unmeasured loss rate |
| 2. Fix C/F evening-peak lateness | per quarter | 3,197 | 6,394 | Medium: gap is large but associational; cost of the fix unknown |
| 3. Fix the two dark stores (DarkStore_007, DarkStore_013) | per quarter | 964 | 1,927 | High on cost; excludes any customer-loss effect |
| 4. Win-back offer, loyal lapsing only | per 90 days | -235 | 556 | High that it moves behaviour, low that it pays back in 90 days |

Assumptions:
- **Lever 1:** the floor ($910) assumes every flat-promo customer is lost and still beats keeping them. The mid case assumes 20% are lost and the stayers are worth 80% of a normal new customer. Neither is measured.
- **Lever 2:** 1,161 excess late orders at about $4.86 lower CM each, plus about $749 of retention. Break-even spend is $1.40 per C/F peak-hour order.
- **Lever 3:** 204 excess tickets at about $9.43 each (refund plus $2.50 support cost).

Channel quality (Q0 new customers, 90-day CM per customer): referral $6.60, organic $6.16, search $3.94, affiliate $2.21, paid social $2.00 (31% of new customers).

## Summary (draft, rewrite in your own words)

1. **Biggest lever:** the first-order flat promo. It loses money per customer even over 90 days (-$0.35 against +$6.54 for other new customers), and its cost sign is measured. The size of the gain depends on how many of those customers would leave, so I would pilot a redesign before cutting it fully.
2. **Why win-back is not a profit lever:** the $5 credit changes behaviour for loyal lapsing customers (+12.5 points), but part of the spend goes to customers who would have reordered anyway. Net 90-day CM is about break-even and the interval includes zero. The case would rest on later value or a smaller credit, and the loyal pool is only 932 customers.
3. **What the data cannot tell me:** acquisition cost (so channel profitability is unknown), value beyond 90 days, the cost of fixing lateness or the two stores, and whether the late-versus-on-time margin gap is fully causal.

## Limitations
- Promo and lateness comparisons are observational. The A/B test is the only causal evidence.
- Free-delivery and loyalty-credit per-order CM are affected by a generator artifact and are not findings.
- Lever values are per quarter and are not additive without checking for overlap (for example, late orders in C/F also drive refunds counted elsewhere).