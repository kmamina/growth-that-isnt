# Planted Findings (Answer Key for the Synthetic Data)

> **Purpose:** These are the effects built into the synthetic dataset. They are not analysis results. Phase 3 must recover or challenge them independently. The generator creates every effect probabilistically; no headline number is typed in.

## A. Headline trends

Q-1 = months 10-12 (2025-10-01 to 2025-12-31). Q0 = months 13-15 (2026-01-01 to 2026-03-31).

| Metric | Q-1 | Q0 | Tolerance |
|---|---|---|---|
| GMV | baseline | +18% | ±1.5 pts |
| 90-day repeat rate (by first-valid-order cohort) | 41% | 32% | ±1.5 pts |
| Refund rate | 3.0% | 5.5% | ±0.5 pts |
| Discount rate (% of GMV) | 9% | 14% | ±1 pt |
| Late rate (overall) | ~12.5% | ~14.5% | ±1 pt |
| CM per order | $1.20 | $0.60 | Q0 falls 40-60% |
| New customers | baseline | +30% | ±5 pts |
| Paid-social share of new customers | 20% | 30% | ±2 pts |

**Why the overall late rate moves only about 2 points:** the lateness in finding 1 hits roughly 9% of all orders (2 of 8 zones, about 35% of orders in the evening peak). A small overall change hides a severe local problem.

**New-customer channel mix (targets):**

| Channel | Q-1 mix | Q0 mix |
|---|---|---|
| paid_social | 20% | 30% |
| organic | 30% | 30% |
| search | 20% | 18% |
| referral | 18% | 12% |
| affiliate | 12% | 10% |

## B. Planted findings

| # | Finding | Parameters | How I'll verify (Phase 3) |
|---|---|---|---|
| 1 | Evening-peak lateness in Zones C and F | Orders placed 18:00-21:30 in Zones C and F: late rate ~14% in Q-1, ~38% in Q0. All other zone/hour combinations: ~12% in both quarters. Customers whose **first** valid order is late have a 90-day repeat rate of ~20%, versus ~40% for on-time first orders. **Mechanism:** the extra delay sits mainly in the picked_up to delivered leg (+8 to 12 min from congestion and long routes) | Late-rate heatmap by zone x hour x quarter. Repeat rate late vs on-time first orders, logistic regression controlling for zone, hour, promo and channel |
| 2 | `first_order_flat` attracts one-timers and loses money | Share of first orders using it: 10% in Q-1, 35% in Q0. Its users repeat at ~15% vs ~40% baseline. CM per order about -$2 to -$4 | Repeat rate and CM per order by promo type. Incrementality in Phase 5, not assumed causal |
| 3 | Hidden complaint theme: missing items in grocery | ~25% of tickets with category `other` mention missing or short items, on grocery orders. Spike in Q0, concentrated in dark stores in Zones D and G (at least one dark store exists in each). Not concentrated in C or F | GenAI theme classification validated on ~100 hand-labelled tickets. Theme share by store and quarter |
| 4 | Retention offer works for one segment only | Assigned 2026-04-01, 50/50 within segment. Outcome: **reorder rate within 90 days of assignment**. Loyal-but-lapsing: control ~25%, treatment ~37% (+12 pts). Deal seekers: control ~20%, treatment ~20% (~0 lift). Offer cost $5 per redeemed offer in both segments, $0 if not redeemed | A/B test by segment: lift, confidence interval, cost per incremental order, net CM |
| 5 | Rider supply is a red herring | Rider assignment time (placed to assigned) rises ~2 min in Zones C and F only, flat elsewhere. Merchant prep time flat everywhere in both quarters | Assignment-time and prep-time trend by zone. Regression shows they add little beyond the late flag |
| 6 | Acquisition quality is the problem, not volume | Underlying channel repeat rates are in the table below. Paid-social share of new customers rises 20% to 30% | Repeat rate by channel and cohort month. Quantify how much of the overall drop is channel mix |

**Channel repeat rates.** The Q0 column is the *observed* rate after all effects. The generator needs the higher Q-1 base rates so the 41% to 32% fall emerges.

| Channel | Q-1 base rate | Q0 observed (target) |
|---|---|---|
| referral | ~55% | ~48% |
| organic | ~47% | ~40% |
| search | ~40% | ~33% |
| affiliate | ~32% | ~25% |
| paid_social | ~30% | ~22% |

Channel base rates are reduced in Q0 by lateness (finding 1) and promo mix (finding 2). Phase 2 calibrates until the headline repeat rates land within tolerance.

**Refund driver:** refund probability rises with late orders and with missing-item tickets, which is why the refund rate moves from 3% to 5.5%.

## C. Customer segments (behaviour before 2026-04-01 only)

| Segment | Definition |
|---|---|
| Loyal but lapsing | At least 4 lifetime valid orders, at most 20% of them used a promo, no valid order in the 45 days before 2026-04-01 |
| Deal seekers | At least 60% of lifetime valid orders used a promo |
| Other | Everyone else |

**Experiment eligibility:** no valid order in the 45 days before 2026-04-01, and a member of Loyal-but-lapsing or Deal-seekers. The generator gives each customer a hidden promo-sensitivity trait so there are enough deal seekers.

## D. Rules the generator must follow

1. Effects come from probabilities, not hard-coded outcomes, so results show noise.
2. The overall repeat rate is a result of channel mix, lateness and promo effects. Calibrate until it lands at 41% and 32%.
3. Findings 1, 3 and 5 sit in different places on purpose: 1 and 5 in Zones C and F, 3 in Zones D and G. Finding 1 and 5 are separated by mechanism: delay sits in delivery, not assignment.
4. No stakeholder is fully right:
   - VP Growth: acquisition volume does rise.
   - COO: delivery hurts, but only in two zones at peak.
   - CFO: promos hurt margin, but one promo type is the real problem.
   - Head of CX: there is a real hidden theme.
5. Fixed random seed (42).
6. Planted percentages are target ranges, not exact values for every subgroup.
7. Phase 3 computes everything from the data; this file is only the answer key.
8. Observed values after calibration are in docs/06_generation_results.md.

## E. Expected story (direction of the investigation, not a conclusion)

Zesto is growing, but growth quality is falling. Volume comes from more paid-social customers who repeat less. A first-order promo attracts one-timers and loses money. Lateness is concentrated at the evening peak in two zones, and a separate grocery-complaint pattern sits in two other zones. Rider supply alone does not explain the drop. The retention offer works for loyal-but-lapsing customers and wastes money on deal seekers.