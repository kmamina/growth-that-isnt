-- Per-customer quarterly totals (valid orders only)
CREATE OR REPLACE VIEW v_cust_q AS
SELECT customer_id,
  SUM(CASE WHEN q = 'Q-1' THEN order_value END) AS gmv_q1,
  COUNT(CASE WHEN q = 'Q-1' THEN 1 END)         AS n_q1,
  SUM(CASE WHEN q = 'Q0' THEN order_value END)  AS gmv_q0,
  COUNT(CASE WHEN q = 'Q0' THEN 1 END)          AS n_q0,
  MIN(order_ts)                                 AS first_ts
FROM v_orders_q
GROUP BY customer_id;

-- Bridge category per customer (KPI doc, Section 5)
CREATE OR REPLACE VIEW v_bridge AS
SELECT c.*,
  CASE
    WHEN n_q1 = 0 AND n_q0 > 0 AND f.first_ts >= '2026-01-01' THEN 'New'
    WHEN n_q1 = 0 AND n_q0 > 0 THEN 'Returning'
    WHEN n_q1 > 0 AND n_q0 = 0 THEN 'Lost'
    WHEN n_q1 > 0 AND n_q0 > 0 AND n_q0 <= 0.5 * n_q1 THEN 'Reduced'
    WHEN n_q1 > 0 AND n_q0 > 0 THEN 'Repeat'
  END AS category
FROM (SELECT customer_id,
        COALESCE(gmv_q1,0) AS gmv_q1, n_q1, COALESCE(gmv_q0,0) AS gmv_q0, n_q0
      FROM v_cust_q) c
JOIN (SELECT customer_id, MIN(order_ts) AS first_ts FROM v_valid_orders GROUP BY customer_id) f
  USING (customer_id)
WHERE n_q1 > 0 OR n_q0 > 0;

-- Churn snapshot at 2026-03-31 (KPI doc, Section 4)
CREATE OR REPLACE VIEW v_churn AS
WITH w AS (
  SELECT customer_id,
    COUNT(CASE WHEN order_ts >= '2025-10-03' AND order_ts < '2026-01-01' THEN 1 END) AS n_prev,
    COUNT(CASE WHEN order_ts >= '2026-01-01' AND order_ts < '2026-04-01' THEN 1 END) AS n_last
  FROM v_valid_orders GROUP BY customer_id
),
last_o AS (
  SELECT customer_id, is_late, is_refunded, has_ticket,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts DESC) AS rn
  FROM v_valid_orders WHERE order_ts < '2026-04-01'
),
react AS (
  SELECT DISTINCT customer_id FROM v_valid_orders WHERE order_ts >= '2026-04-01'
)
SELECT w.customer_id, w.n_prev, w.n_last,
  CASE WHEN n_prev > 0 AND n_last = 0 THEN 'Lost'
       WHEN n_prev > 0 AND n_last > 0 AND n_last <= 0.5 * n_prev THEN 'Reduced'
  END AS churn_type,
  CASE WHEN n_prev > 0 AND n_last = 0
        AND (l.is_late = 1 OR l.is_refunded = 1 OR l.has_ticket = 1) THEN 1 ELSE 0 END AS bad_experience,
  CASE WHEN n_prev > 0 AND n_last = 0 AND r.customer_id IS NOT NULL THEN 1 ELSE 0 END AS reactivated
FROM w
LEFT JOIN last_o l ON l.customer_id = w.customer_id AND l.rn = 1
LEFT JOIN react r ON r.customer_id = w.customer_id;