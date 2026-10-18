-- Issue 1: duplicate order_id
SELECT 1 AS issue_id, 'duplicate order_id (extra rows)' AS issue,
       COUNT(*) - COUNT(DISTINCT order_id) AS detected
FROM raw_orders;

-- Issue 2: missing delivered_ts on non-cancelled orders
SELECT 2, 'missing delivered_ts on valid orders', COUNT(*)
FROM raw_orders o
JOIN raw_delivery_events d USING (order_id)
WHERE o.status <> 'cancelled' AND d.delivered_ts IS NULL;

-- Issue 3: delivered_ts earlier than picked_up_ts
SELECT 3, 'delivered_ts before picked_up_ts', COUNT(*)
FROM raw_delivery_events
WHERE delivered_ts < picked_up_ts;

-- Issue 4: order_value zero or negative (distinct orders)
SELECT 4, 'order_value <= 0', COUNT(DISTINCT order_id)
FROM raw_orders WHERE order_value <= 0;

-- Issue 5: zone not a single letter A-H
SELECT 5, 'inconsistent zone text', COUNT(*)
FROM raw_orders
WHERE zone NOT IN ('A','B','C','D','E','F','G','H');

-- Issue 6: merchant_id not in merchants
SELECT 6, 'merchant_id not in merchants', COUNT(*)
FROM raw_orders o
LEFT JOIN raw_merchants m USING (merchant_id)
WHERE m.merchant_id IS NULL;

-- Issue 7: summed ticket refunds exceed order_value
SELECT 7, 'summed refunds exceed order_value', COUNT(*)
FROM (
  SELECT o.order_id, MAX(o.order_value) AS ov, SUM(t.refund_amount) AS refund
  FROM (SELECT DISTINCT ON (order_id) * FROM raw_orders ORDER BY order_id, updated_at DESC) o
  JOIN raw_support_tickets t USING (order_id)
  GROUP BY o.order_id
) x
WHERE refund > ov;

-- Issue 8: first_order_date differs from earliest order date
SELECT 8, 'first_order_date mismatch', COUNT(*)
FROM raw_customers c
JOIN (SELECT customer_id, MIN(CAST(order_ts AS DATE)) AS first_dt
      FROM raw_orders WHERE status <> 'cancelled' GROUP BY customer_id) f USING (customer_id)
WHERE CAST(c.first_order_date AS DATE) <> f.first_dt;

-- Issue 9: delivery longer than 600 minutes
SELECT 9, 'delivery time > 600 min', COUNT(*)
FROM raw_delivery_events
WHERE date_diff('minute', placed_ts, delivered_ts) > 600;

-- Issue 10: empty-string complaint text (not observable after CSV load)
SELECT 10, 'complaint_text empty string', COUNT(*)
FROM raw_support_tickets WHERE complaint_text = '';

-- Issue 11: orders.order_ts differs from delivery_events.placed_ts
SELECT 11, 'order_ts <> placed_ts', COUNT(*)
FROM (SELECT DISTINCT ON (order_id) * FROM raw_orders ORDER BY order_id, updated_at DESC) o
JOIN raw_delivery_events d USING (order_id)
WHERE o.order_ts <> d.placed_ts;

-- Issue 12: status disagrees with summed ticket refunds
SELECT 12, 'status vs ticket refund mismatch', COUNT(*)
FROM (SELECT DISTINCT ON (order_id) * FROM raw_orders ORDER BY order_id, updated_at DESC) o
LEFT JOIN (SELECT order_id, SUM(refund_amount) AS refund
           FROM raw_support_tickets GROUP BY order_id) t USING (order_id)
WHERE o.status <> 'cancelled'
  AND ((o.status = 'refunded') <> (COALESCE(t.refund, 0) > 0));