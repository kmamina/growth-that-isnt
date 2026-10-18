-- 1. Orders: keep latest version of each order_id
CREATE OR REPLACE TABLE clean_orders AS
SELECT * EXCLUDE (rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) AS rn
  FROM raw_orders
) WHERE rn = 1;

-- 2. Zone: trim, upper-case, strip "ZONE "
UPDATE clean_orders
SET zone = REPLACE(UPPER(TRIM(zone)), 'ZONE ', '');

-- 3. order_ts: delivery_events.placed_ts is the source of truth
UPDATE clean_orders o
SET order_ts = d.placed_ts
FROM raw_delivery_events d
WHERE o.order_id = d.order_id AND o.order_ts <> d.placed_ts;

-- 4. Value check and 5. merchant validity flags
ALTER TABLE clean_orders ADD COLUMN value_valid INTEGER;
UPDATE clean_orders SET value_valid = CASE WHEN order_value > 0 THEN 1 ELSE 0 END;

ALTER TABLE clean_orders ADD COLUMN merchant_id_valid INTEGER;
UPDATE clean_orders SET merchant_id_valid =
  CASE WHEN merchant_id IN (SELECT merchant_id FROM raw_merchants) THEN 1 ELSE 0 END;
UPDATE clean_orders SET merchant_id = NULL WHERE merchant_id_valid = 0;

-- 6. Delivery events: reason flag first, then null the bad timestamps
CREATE OR REPLACE TABLE clean_delivery_events AS
SELECT *, CAST(NULL AS VARCHAR) AS delivery_dq_flag FROM raw_delivery_events;

UPDATE clean_delivery_events SET delivery_dq_flag = 'extreme_duration'
WHERE date_diff('minute', placed_ts, delivered_ts) > 600;

UPDATE clean_delivery_events SET delivery_dq_flag = 'sequence_error'
WHERE delivery_dq_flag IS NULL AND delivered_ts < picked_up_ts;

UPDATE clean_delivery_events SET delivery_dq_flag = 'missing'
WHERE delivery_dq_flag IS NULL AND delivered_ts IS NULL
  AND order_id IN (SELECT order_id FROM clean_orders WHERE status <> 'cancelled');

UPDATE clean_delivery_events SET delivered_ts = NULL
WHERE delivery_dq_flag IN ('extreme_duration', 'sequence_error');

-- 7. Refunds: scale ticket refunds so their sum never exceeds a valid order value
CREATE OR REPLACE TABLE clean_support_tickets AS
SELECT t.*, CAST(0 AS INTEGER) AS refund_scaled_flag FROM raw_support_tickets t;

UPDATE clean_support_tickets t
SET refund_amount = ROUND(t.refund_amount * o.order_value / s.total, 2),
    refund_scaled_flag = 1
FROM clean_orders o,
     (SELECT order_id, SUM(refund_amount) AS total FROM clean_support_tickets GROUP BY order_id) s
WHERE t.order_id = o.order_id AND t.order_id = s.order_id
  AND o.value_valid = 1 AND s.total > o.order_value AND s.total > 0;

-- 8. Status: ticket refunds are the source of truth
ALTER TABLE clean_orders ADD COLUMN status_flag INTEGER;
UPDATE clean_orders o
SET status_flag = CASE
  WHEN o.status <> 'cancelled'
   AND ((o.status = 'refunded') <> (COALESCE(r.refund, 0) > 0)) THEN 1 ELSE 0 END
FROM (SELECT o2.order_id, SUM(t.refund_amount) AS refund
      FROM clean_orders o2 LEFT JOIN clean_support_tickets t USING (order_id)
      GROUP BY o2.order_id) r
WHERE o.order_id = r.order_id;

UPDATE clean_orders o
SET status = CASE WHEN r.refund > 0 THEN 'refunded' ELSE 'delivered' END
FROM (SELECT order_id, SUM(refund_amount) AS refund FROM clean_support_tickets GROUP BY order_id) r
WHERE o.order_id = r.order_id AND o.status <> 'cancelled';

UPDATE clean_orders SET status = 'delivered'
WHERE status = 'refunded' AND order_id NOT IN (SELECT order_id FROM clean_support_tickets);

-- 9. Customers: first_order_date from first valid order
CREATE OR REPLACE TABLE clean_customers AS SELECT * FROM raw_customers;
UPDATE clean_customers c
SET first_order_date = f.first_dt
FROM (SELECT customer_id, MIN(CAST(order_ts AS DATE)) AS first_dt
      FROM clean_orders WHERE status <> 'cancelled' AND value_valid = 1
      GROUP BY customer_id) f
WHERE c.customer_id = f.customer_id;
UPDATE clean_customers SET first_order_date = NULL
WHERE customer_id NOT IN (SELECT customer_id FROM clean_orders
                          WHERE status <> 'cancelled' AND value_valid = 1);

-- 10. Complaint text: empty to NULL (no-op after CSV load, kept for completeness)
UPDATE clean_support_tickets SET complaint_text = NULL WHERE complaint_text = '';

-- Unchanged tables
CREATE OR REPLACE TABLE clean_merchants AS SELECT * FROM raw_merchants;
CREATE OR REPLACE TABLE clean_riders AS SELECT * FROM raw_riders;
CREATE OR REPLACE TABLE clean_promotions AS SELECT * FROM raw_promotions;
CREATE OR REPLACE TABLE clean_experiment_assignments AS SELECT * FROM raw_experiment_assignments;
