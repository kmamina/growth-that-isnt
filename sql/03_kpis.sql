-- Valid orders: delivered or refunded, value > 0 (KPI doc, Section 0)
CREATE OR REPLACE VIEW v_valid_orders AS
SELECT o.*,
       COALESCE(r.refund, 0) AS refund_amount,
       CASE WHEN COALESCE(r.refund, 0) > 0 THEN 1 ELSE 0 END AS is_refunded,
       CASE WHEN r.n_tickets > 0 THEN 1 ELSE 0 END AS has_ticket,
       d.delivered_ts, d.delivery_dq_flag,
       date_diff('second', d.placed_ts, d.delivered_ts) / 60.0 AS delivery_min,
       CASE WHEN d.delivered_ts IS NULL THEN NULL
            WHEN date_diff('second', d.placed_ts, d.delivered_ts) / 60.0 > o.promised_eta_min + 10
            THEN 1 ELSE 0 END AS is_late
FROM clean_orders o
LEFT JOIN (SELECT order_id, SUM(refund_amount) AS refund, COUNT(*) AS n_tickets
           FROM clean_support_tickets GROUP BY order_id) r USING (order_id)
LEFT JOIN clean_delivery_events d USING (order_id)
WHERE o.status <> 'cancelled' AND o.value_valid = 1;

-- Quarter label from placed time
CREATE OR REPLACE VIEW v_orders_q AS
SELECT *,
  CASE WHEN order_ts >= '2025-10-01' AND order_ts < '2026-01-01' THEN 'Q-1'
       WHEN order_ts >= '2026-01-01' AND order_ts < '2026-04-01' THEN 'Q0'
       ELSE 'other' END AS q,
  commission_amount + delivery_fee - discount_amount - refund_amount
    - rider_cost - payment_fee - 2.50 * has_ticket AS cm
FROM v_valid_orders;

-- KPI summary by quarter
CREATE OR REPLACE VIEW v_kpi_quarter AS
SELECT q,
  COUNT(*)                                        AS valid_orders,
  ROUND(SUM(order_value), 0)                      AS gmv,
  ROUND(SUM(order_value) / COUNT(*), 2)           AS aov,
  ROUND(SUM(discount_amount) / SUM(order_value), 4) AS discount_rate,
  ROUND(AVG(is_refunded), 4)                      AS refund_rate,
  ROUND(AVG(is_late), 4)                          AS late_rate,
  ROUND(AVG(cm), 2)                               AS cm_per_order
FROM v_orders_q
GROUP BY q;

-- 90-day repeat rate by first-order cohort month (KPI doc, Section 2)
CREATE OR REPLACE VIEW v_repeat_cohort AS
WITH ranked AS (
  SELECT customer_id, order_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts) AS rn
  FROM v_valid_orders
),
f AS (
  SELECT a.customer_id, a.order_ts AS first_ts, b.order_ts AS second_ts
  FROM ranked a LEFT JOIN ranked b
    ON a.customer_id = b.customer_id AND b.rn = 2
  WHERE a.rn = 1
)
SELECT strftime(first_ts, '%Y-%m') AS cohort_month,
       COUNT(*) AS cohort_size,
       ROUND(AVG(CASE WHEN second_ts IS NOT NULL
                       AND second_ts <= first_ts + INTERVAL 90 DAY THEN 1 ELSE 0 END), 4) AS repeat_90d
FROM f
WHERE first_ts < '2026-04-01'
GROUP BY 1 ORDER BY 1;