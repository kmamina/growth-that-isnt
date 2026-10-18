# Data Quality Issues Plan

Issues are injected **after the clean data is generated**. The generator writes `data/raw/injection_log.csv`, listing every row and column intentionally corrupted. Phase 3 can then compare the injection log with the cleaning report to test whether the data-quality process detected and recovered the planted issues.

## A. Injected data-quality issues

| # | Table | Issue | Rate | Detection (SQL/Python) | Cleaning rule |
|---|---|---|---|---|---|
| 1 | `orders` | Duplicate `order_id` with different `updated_at` values. The older duplicate also differs in a business-relevant field such as `status` or `order_value`. | 0.5% | `GROUP BY order_id HAVING COUNT(*) > 1` | Keep the record with the latest `updated_at`; remove the older duplicate and log the removal |
| 2 | `delivery_events` | Missing `delivered_ts` on delivered/refunded orders | 1% | `delivered_ts IS NULL AND status IN ('delivered','refunded')` | Keep the order; exclude it from delivery-time and late-order metrics; flag the missing timestamp |
| 3 | `delivery_events` | `delivered_ts` earlier than `picked_up_ts` | 0.3% | `delivered_ts < picked_up_ts` | Detect before cleaning, record `delivery_dq_flag = 'sequence_error'`, then set `delivered_ts` to `NULL` and exclude from delivery-time and late-order metrics |
| 4 | `orders` | `order_value` is zero or negative | 0.2% | `order_value <= 0` | Flag the record and exclude it from all KPI calculations, including first-order and repeat calculations |
| 5 | `orders` | Inconsistent zone text (`"C"`, `"c"`, `"Zone C"`, `" C "`) | **2%** | `DISTINCT zone` / pattern checks | Standardise the value to the single zone letter `A`–`H`; log the transformation |
| 6 | `orders` | `merchant_id` does not exist in `merchants` | 0.3% | `LEFT JOIN merchants ... WHERE merchant_id IS NULL` | Keep the order; set `merchant_id = NULL`, set `merchant_id_valid = 0`, and flag the invalid foreign key |
| 7 | `support_tickets` | Summed ticket refunds for an order exceed `order_value` | 0.2% | `SUM(refund_amount) per order > order_value` | Scale the order's ticket refunds down proportionally so their sum equals `order_value`; flag the correction |
| 8 | `customers` | `first_order_date` differs from the customer's earliest valid order date | 2% | Compare `customers.first_order_date` with `MIN(valid_order_date)` from valid orders | Recompute `first_order_date` from the customer's first valid order. If the customer has no valid order, set `first_order_date = NULL`; flag the correction |
| 9 | `delivery_events` | Delivery time of 600+ minutes | 0.1% | `delivered_ts - placed_ts > 600 minutes` | Detect before cleaning, record `delivery_dq_flag = 'extreme_duration'`, then set `delivered_ts` to `NULL` and exclude from delivery-time and late-order metrics |
| 10 | `support_tickets` | `complaint_text` contains an empty string instead of `NULL` | 5% | `complaint_text = ''` | Convert `''` to `NULL` and log the transformation |
| 11 | `orders` vs `delivery_events` | `orders.order_ts` differs from `delivery_events.placed_ts` | 0.3% | `orders.order_ts <> delivery_events.placed_ts` | Use `delivery_events.placed_ts` as the source of truth because it defines the order hour in the KPI definitions; overwrite `orders.order_ts` and flag the mismatch |
| 12 | `orders` vs `support_tickets` | Order status disagrees with aggregated ticket refunds | 1% | Compare `orders.status` with `SUM(support_tickets.refund_amount)` per order | Use the aggregated ticket refund amount as the refund source of truth and apply the KPI document's refund/status edge cases; flag the status mismatch |

### Injection-order dependency

The generator must apply the issues in a controlled order.

**Issue 4 must be handled before Issue 7**, because Issue 7 uses `order_value` as the upper bound for the total refund amount.

The recommended injection order is:

1. Generate clean data.
2. Inject Issue 4 (`order_value` corruption).
3. Inject Issue 7 (refund corruption based on the resulting order value).
4. Inject the remaining issues.
5. Write the final corrupted tables to `data/raw/`.
6. Write every injection to `data/raw/injection_log.csv`.

The cleaning process must then apply the corresponding validation rules in a documented order rather than assuming that all corruptions are independent.

---

## B. Cleaning rules

### Issue 1 — Duplicate orders

When multiple records share the same `order_id`:

- Sort by `updated_at` descending.
- Keep the record with the latest `updated_at`.
- Remove the older duplicate records.
- Log every removed record.
- The duplicate must differ in at least one business-relevant field such as `status` or `order_value`, so keeping the wrong record can materially affect the analysis.

The original and retained records should remain traceable through the cleaning report.

---

### Issue 2 — Missing delivery timestamp

If a valid order has a missing `delivered_ts`:

- Keep the order in other valid-order metrics when it otherwise qualifies.
- Do not calculate delivery time.
- Do not classify it as late.
- Exclude it from the late-rate denominator.
- Set or retain a delivery-quality flag identifying the missing timestamp.

---

### Issues 3 and 9 — Invalid delivery timestamps

Issues 3 and 9 both ultimately result in an invalid `delivered_ts`, but they must remain distinguishable.

**Detect the specific problem before nulling the timestamp.**

Use:

| `delivery_dq_flag` | Meaning |
|---|---|
| `missing` | `delivered_ts` was missing |
| `sequence_error` | `delivered_ts < picked_up_ts` |
| `extreme_duration` | Delivery duration is 600+ minutes |

After the reason is recorded:

- Set the invalid `delivered_ts` to `NULL`.
- Exclude the order from delivery-time and late-order calculations.
- Preserve the reason in `delivery_dq_flag`.

This prevents different data-quality problems from becoming indistinguishable after cleaning.

---

### Issue 4 — Invalid order value

If:

```text
order_value <= 0
```

then:

- Flag the order.
- Exclude it from all KPI calculations.
- Exclude it from GMV.
- Exclude it from valid-order counts.
- Exclude it from AOV, discount-rate, refund-rate, contribution-margin, and frequency calculations.
- Exclude it when determining a customer's first valid order.
- Exclude it from 90-day repeat calculations.
- Exclude it from customer cohort assignment.

**Important:** Rows excluded under Issue 4 must be counted separately in the cleaning report because removing a customer's first valid order can change their cohort month and repeat-rate classification.

---

### Issue 5 — Inconsistent zones

Standardise equivalent values such as:

```text
"C"
"c"
"Zone C"
" C "
```

to:

```text
"C"
```

The final zone domain must contain only:

```text
A, B, C, D, E, F, G, H
```

The cleaning report should record how many values were transformed.

---

### Issue 6 — Invalid merchant ID

If an `orders.merchant_id` does not exist in the `merchants` table:

- Keep the order.
- Set `merchant_id = NULL`.
- Set `merchant_id_valid = 0`.
- Flag the invalid foreign key.
- Do not insert a string such as `"unknown"` into the integer `merchant_id` column.

This preserves the column's data type while making the data-quality problem explicit.

---

### Issue 7 — Excess aggregated refunds

Refunds are evaluated at the **order level**, consistent with the KPI definition.

Calculate:

```text
total_refund_for_order =
SUM(support_tickets.refund_amount)
```

If:

```text
total_refund_for_order > order_value
```

then:

- Scale the ticket-level refund amounts proportionally so their sum equals `order_value`.
- Flag the order as a corrected refund issue.
- Preserve the original values in the injection/cleaning logs.

For example, if an order is worth `$50` and two tickets contain refunds of `$35` and `$25`, the total refund is `$60`. The two ticket refunds should be scaled proportionally so that their corrected total equals `$50`.

This maintains the ticket-level structure while enforcing the order-level constraint.

---

### Issue 8 — Incorrect first-order date

The customer's first order must be based on the **first valid order**, not simply the earliest order record.

Compare:

```text
customers.first_order_date
```

with:

```text
MIN(valid order date)
```

for that customer.

If they differ:

- Recompute `first_order_date`.
- Flag the correction.
- If the customer has no valid orders, set `first_order_date = NULL`.

Cancelled orders and other orders excluded by the valid-order definition must not determine the customer's first order.

---

### Issue 10 — Empty complaint text

Convert:

```text
''
```

to:

```text
NULL
```

This ensures missing complaint text has one consistent representation for SQL, Python, and GenAI processing.

Whitespace-only strings should also be treated as empty after trimming.

---

### Issue 11 — `order_ts` mismatch

The two timestamps have different roles:

- `delivery_events.placed_ts` is the source of truth for the order's placed timestamp used in KPI analysis.
- `orders.order_ts` is the field intentionally corrupted by this issue.

If:

```text
orders.order_ts <> delivery_events.placed_ts
```

then:

- Use `delivery_events.placed_ts`.
- Overwrite `orders.order_ts` with `delivery_events.placed_ts`.
- Set a data-quality flag.
- Record the original and corrected values in the cleaning report.

This ensures hourly analysis uses the same timestamp definition across SQL, Python, and Power BI.

---

### Issue 12 — Status/refund mismatch

The refund source of truth is:

```text
SUM(support_tickets.refund_amount)
```

per order.

Apply the KPI document's edge cases:

- If `orders.status = 'delivered'` but aggregated ticket refunds > 0, classify the order as refunded for KPI calculations and flag the mismatch.
- If `orders.status = 'refunded'` but aggregated ticket refunds = 0, classify the order as **not refunded** for KPI calculations and flag the mismatch.

The status field is therefore treated as a validation field rather than an independent refund source.

---

# C. Rules

1. **Issues are injected after clean data generation.**  
   The underlying business relationships are generated first. Data-quality problems are then added separately.

2. **Rate budget:**  
   The planned issue rates keep the corrupted rows below approximately 5% per table.

   For `orders`, the rates are:

   - Issue 1: 0.5%
   - Issue 4: 0.2%
   - Issue 5: 2.0%
   - Issue 6: 0.3%
   - Issue 11: 0.3%
   - Issue 12: 1.0%

   Total planned issue rate = **4.3%** before accounting for possible overlap.

   The generator should track actual injected rows rather than assuming the percentages are additive because multiple issues may affect the same row.

3. **Every rule must remain consistent with `docs/02_kpi_definitions.md`.**  
   Cleaning must not introduce a different definition of valid orders, refunds, repeat rate, delivery metrics, or customer activity.

4. **Cleaning never deletes silently.**  
   Every removed, corrected, standardised, or excluded record must be counted in the cleaning report.

5. **Preserve auditability.**  
   When a value is changed, the original problem must remain identifiable through the injection log, a data-quality flag, or the cleaning report.

6. **Do not change KPI definitions to fit dirty data.**  
   The cleaning process should make the raw data usable for the existing KPI definitions. It must not redefine the KPIs simply to accommodate corrupted records.

7. **Use the injection log as the validation reference.**  
   Phase 3 should compare `injection_log.csv` with the cleaning report to determine how many planted issues were detected, corrected, excluded, or missed.

8. **Detect invalid timestamp types before nulling them.**  
   Issues 2, 3, and 9 may result in `delivered_ts = NULL` after cleaning, but their original causes must remain distinguishable through `delivery_dq_flag`.

9. **Issue 4 is handled before Issue 7.**  
   Refund validation depends on a valid `order_value`.

10. **Issue 4 exclusions are separately reported.**  
    Because an invalid `order_value` can remove a customer's first valid order, the cleaning report must show how many cohort assignments or repeat calculations were potentially affected.

11. **The generator must use a fixed random seed.**  
    Use seed **42** so the injected data and all downstream results are reproducible.

12. **The generator should record actual injected rows.**  
    The configured rates are targets. The injection log is the authoritative record of what was actually changed.

---

# D. Injection log schema

Phase 2 writes:

```text
data/raw/injection_log.csv
```

The file must contain the following columns:

| Column | Meaning |
|---|---|
| `issue_id` | Issue number from 1 to 12, matching the issue table |
| `table_name` | Table that was corrupted |
| `row_key` | Primary key of the corrupted row (`order_id`, `ticket_id`, or `customer_id`) |
| `column_name` | Column that was changed |
| `original_value` | Value before injection |
| `injected_value` | Value after injection |

For issues that involve multiple columns or an order-level aggregate, the generator may write multiple log rows for the same `row_key`, one for each changed column.

For Issue 7, the log should identify the affected ticket-level `refund_amount` values because the corruption occurs at ticket level while the validation rule is evaluated at order level.

For Issue 1, the duplicate record should be logged clearly enough to identify both the original retained record and the duplicate record that was injected.

---

# E. Expected cleaning report

Phase 3 should produce a summary similar to:

| Issue | Rows injected | Rows detected | Rows corrected/excluded | Detection rate |
|---|---:|---:|---:|---:|
| Duplicate `order_id` | — | — | — | — |
| Missing `delivered_ts` | — | — | — | — |
| Invalid delivery timestamp sequence | — | — | — | — |
| Invalid `order_value` | — | — | — | — |
| Inconsistent zone | — | — | — | — |
| Invalid merchant ID | — | — | — | — |
| Excess aggregated refund | — | — | — | — |
| Incorrect first-order date | — | — | — | — |
| Extreme delivery duration | — | — | — | — |
| Empty complaint text | — | — | — | — |
| `order_ts` mismatch | — | — | — | — |
| Status/refund mismatch | — | — | — | — |

The report should also include a separate summary of **Issue 4 exclusions**, because those records can affect:

- customer first-valid-order dates
- cohort assignment
- 90-day repeat calculations
- customer-level retention metrics

The final cleaning report should allow the following question to be answered:

> **What problems were planted, how many were detected, what was changed or excluded, and did the cleaning process recover the injected issues without silently altering the data or changing the KPI definitions?**

---

# F. Phase 3 validation standard

The cleaning process should be considered successful only if:

1. Every intentionally injected issue can be traced through `injection_log.csv`.
2. Each issue has a corresponding detection rule.
3. Each detected issue has a documented cleaning action.
4. No KPI definition is changed to accommodate a dirty record.
5. Invalid records are not silently removed.
6. Corrections remain auditable.
7. Issue 4 exclusions are separately quantified.
8. Delivery timestamp problems remain distinguishable after cleaning.
9. Refund validation is performed at the order level.
10. The cleaned dataset produces the same business metrics as the clean underlying dataset, except where the planted issue intentionally changes which records should be excluded under the documented KPI rules.
11. The final cleaning report shows the number of injected, detected, corrected, and excluded records for every issue.