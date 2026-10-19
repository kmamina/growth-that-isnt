CREATE OR REPLACE VIEW v_first_orders AS
WITH ranked AS (
  SELECT q.*, ROW_NUMBER() OVER (PARTITION BY q.customer_id ORDER BY q.order_ts) AS rn
  FROM v_orders_q q
),
s AS (SELECT customer_id, order_ts AS second_ts FROM ranked WHERE rn = 2)
SELECT r.customer_id, r.order_ts AS first_ts, r.q, r.zone, r.order_type, r.promo_id,
       r.is_late, r.discount_amount, r.cm,
       CASE WHEN s.second_ts IS NOT NULL
             AND s.second_ts <= r.order_ts + INTERVAL 90 DAY THEN 1 ELSE 0 END AS repeat_90d,
       EXTRACT(hour FROM r.order_ts) + EXTRACT(minute FROM r.order_ts) / 60.0 AS hr,
       c.acquisition_channel AS channel,
       p.promo_type
FROM ranked r
LEFT JOIN s USING (customer_id)
JOIN clean_customers c USING (customer_id)
LEFT JOIN clean_promotions p ON p.promo_id = r.promo_id
WHERE r.rn = 1 AND r.order_ts < '2026-04-01';
