# Phase 3 Findings

## Stakeholder Verdicts

| Stakeholder | Verdict | Evidence |
|---|---|---|
| **VP Growth** (“retention is fine, buy more users”) | **Wrong** | Repeat fell in all 5 channels. Paid social is the worst channel (OR 0.48) and grew from 20% to 31% of new customers. More acquisition through it worsens the mix. |
| **COO** (“riders and delivery”) | **Right about where, wrong about how much** | Lateness is concentrated in the C/F evening peak (13% → 37%) and halves repeat (OR 0.35). It explains only about 0.4 of the 8.9 points overall, and rider assignment time has no effect. |
| **CFO** (“promos destroy margin”) | **Right, but one promo** | `first_order_flat` explains about 6.6 points, has a 14% repeat rate and CM of -$1.43 per order. Other promos barely affect repeat. |
| **Head of CX** (“unhappy, cause unknown”) | **Right, cause hidden** | Missing-item tickets tripled but sit mostly under `other`. Phase 4 finds this from the text. |

## Three Key Takeaways

**Headline:** Growth increased 17.9%, but 93% of it came from new customers while lost and reduced customers took away $309k.

**Biggest driver:** `first_order_flat` is the biggest driver of the retention problem, combining weak repeat behavior with negative contribution margin.

**Limitation:** These are observational associations, so the promo effect gets a proper incrementality check in Phase 5.