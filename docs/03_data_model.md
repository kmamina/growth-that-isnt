# Data Model

## Tables

### customers (~25,000 rows)
Primary key: customer_id
Columns: customer_id, signup_date, acquisition_channel, home_zone, first_order_date, device, is_subscriber
Channels: organic, paid_social, referral, search, affiliate

### merchants (~300 rows)
Primary key: merchant_id
Columns: merchant_id, merchant_name, merchant_type, cuisine_category, zone, avg_prep_time_target_min, commission_pct, onboarded_date

### riders (~600 rows)
Primary key: rider_id
Columns: rider_id, home_zone, join_date, employment_type, active_flag

### promotions (~12 rows)
Primary key: promo_id
Columns: promo_id, promo_name, promo_type, discount_value, start_date, end_date, min_order_value, target_audience

### orders (~300,000 rows, plus some injected duplicates)
Primary key: order_id
Foreign keys: customer_id, merchant_id, promo_id (promo_id can be empty)
Columns: order_id, customer_id, merchant_id, promo_id, order_ts, zone, order_type, items_count, order_value, discount_amount, delivery_fee, commission_amount, rider_cost, payment_fee, status, promised_eta_min, updated_at

### delivery_events (1 row per order)
Primary key and foreign key: order_id
Foreign key: rider_id
Columns: order_id, rider_id, placed_ts, merchant_accepted_ts, food_ready_ts, rider_assigned_ts, picked_up_ts, delivered_ts, distance_km

### support_tickets (~40,000 rows)
Primary key: ticket_id
Foreign keys: order_id, customer_id
Columns: ticket_id, order_id, customer_id, created_ts, category, complaint_text, refund_amount, resolution_status

### experiment_assignments (~6,000 rows)
Primary key: customer_id
Columns: customer_id, experiment_id, variant, assigned_date, offer_cost

## How the tables connect
- One customer has many orders
- One merchant has many orders
- One order has one delivery_events row
- One rider handles many deliveries
- One order can have zero or more support tickets
- An order can use one promotion, or none
- Some customers are in the experiment, each with one assignment

## Decisions
1. orders.order_ts and delivery_events.placed_ts are the same moment. If they differ, that is a data-quality issue.
2. These are not stored; we calculate them in SQL: refund amount per order (sum of tickets), support cost ($2.50 per order with a ticket), late flag, contribution margin, and customer segments.
3. A/B test: customers are assigned on 2026-04-01. They are customers who were active in Q0 but ordering less often. The result is whether they place a valid order within 90 days (by 2026-06-30).
4. Caveat: the offer also affects reactivation in months 16 to 18, so reactivation numbers for assigned customers are not a clean baseline.
5. Orders run from 2025-01-01 to 2026-06-30, with real timestamps (date and time), not just dates.

## ER diagram
See images/er_diagram.png