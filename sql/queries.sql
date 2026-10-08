-- Amazon India Sales & GST Analytics — SQL (SQLite)
-- Table: sales  (one row per order line, built from data/processed/sales_clean.csv.gz by sql/run_queries.py)
-- Net sales = status_group 'Shipped/Delivered' AND qty >= 1 AND amount > 0  (column is_net_sale = 1)

-- Q1. Headline KPIs
SELECT
    COUNT(*)                                                   AS order_lines,
    ROUND(SUM(CASE WHEN is_net_sale = 1 THEN amount END), 0)   AS net_sales_inr,
    COUNT(DISTINCT CASE WHEN is_net_sale = 1 THEN order_id END) AS net_orders,
    SUM(CASE WHEN is_net_sale = 1 THEN qty END)                AS units_sold,
    ROUND(100.0 * SUM(status_group = 'Cancelled') / COUNT(*), 2) AS cancellation_pct,
    ROUND(100.0 * SUM(status_group = 'Returned')  / COUNT(*), 2) AS return_pct
FROM sales;

-- Q2. Monthly net sales with month-over-month growth (window function: LAG)
WITH monthly AS (
    SELECT order_month,
           SUM(amount)                AS net_sales,
           COUNT(DISTINCT order_date) AS active_days
    FROM sales
    WHERE is_net_sale = 1 AND order_date BETWEEN '2022-04-01' AND '2022-06-28'
    GROUP BY order_month
)
SELECT order_month,
       ROUND(net_sales, 0)                AS net_sales_inr,
       ROUND(net_sales / active_days, 0)  AS sales_per_day,
       ROUND(100.0 * (net_sales - LAG(net_sales) OVER (ORDER BY order_month))
             / LAG(net_sales) OVER (ORDER BY order_month), 1) AS mom_growth_pct
FROM monthly
ORDER BY order_month;

-- Q3. Revenue share by category
SELECT category,
       ROUND(SUM(amount), 0) AS net_sales_inr,
       SUM(qty)              AS units,
       ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 1) AS share_pct
FROM sales
WHERE is_net_sale = 1
GROUP BY category
ORDER BY net_sales_inr DESC;

-- Q4. Top 10 states with running (cumulative) share
WITH st AS (
    SELECT ship_state, SUM(amount) AS net_sales
    FROM sales WHERE is_net_sale = 1
    GROUP BY ship_state
)
SELECT ship_state,
       ROUND(net_sales, 0) AS net_sales_inr,
       ROUND(100.0 * net_sales / SUM(net_sales) OVER (), 1) AS share_pct,
       ROUND(100.0 * SUM(net_sales) OVER (ORDER BY net_sales DESC) / SUM(net_sales) OVER (), 1) AS cumulative_share_pct
FROM st
ORDER BY net_sales DESC
LIMIT 10;

-- Q5. Top 3 cities inside each of the top 5 states (window function: ROW_NUMBER)
WITH city AS (
    SELECT ship_state, ship_city, SUM(amount) AS net_sales,
           ROW_NUMBER() OVER (PARTITION BY ship_state ORDER BY SUM(amount) DESC) AS rn
    FROM sales WHERE is_net_sale = 1
    GROUP BY ship_state, ship_city
),
top_states AS (
    SELECT ship_state FROM sales WHERE is_net_sale = 1
    GROUP BY ship_state ORDER BY SUM(amount) DESC LIMIT 5
)
SELECT c.ship_state, c.rn AS city_rank, c.ship_city, ROUND(c.net_sales, 0) AS net_sales_inr
FROM city c JOIN top_states t ON c.ship_state = t.ship_state
WHERE c.rn <= 3
ORDER BY c.ship_state, c.rn;

-- Q6. Cancellation rate by fulfilment method
SELECT fulfilment,
       COUNT(*) AS order_lines,
       SUM(status_group = 'Cancelled') AS cancelled,
       ROUND(100.0 * SUM(status_group = 'Cancelled') / COUNT(*), 2) AS cancellation_pct
FROM sales
GROUP BY fulfilment;

-- Q7. Cancellation rate by category (only categories with 1,000+ order lines)
SELECT category,
       COUNT(*) AS order_lines,
       ROUND(100.0 * SUM(status_group = 'Cancelled') / COUNT(*), 2) AS cancellation_pct
FROM sales
GROUP BY category
HAVING COUNT(*) >= 1000
ORDER BY cancellation_pct DESC;

-- Q8. GST by rate slab (5% vs 12%)
SELECT CAST(gst_rate * 100 AS INT) || '%' AS gst_slab,
       COUNT(*)                     AS lines,
       ROUND(SUM(amount), 0)        AS gross_sales_inr,
       ROUND(SUM(taxable_value), 0) AS taxable_value_inr,
       ROUND(SUM(gst_amount), 0)    AS gst_inr,
       ROUND(100.0 * SUM(amount) / SUM(SUM(amount)) OVER (), 1) AS share_of_sales_pct
FROM sales
WHERE is_net_sale = 1
GROUP BY gst_rate;

-- Q9. GST split: CGST / SGST (intra-state) vs IGST (inter-state)
SELECT supply_type,
       COUNT(*)              AS lines,
       ROUND(SUM(cgst), 0)   AS cgst_inr,
       ROUND(SUM(sgst), 0)   AS sgst_inr,
       ROUND(SUM(igst), 0)   AS igst_inr
FROM sales
WHERE is_net_sale = 1
GROUP BY supply_type;

-- Q10. Monthly GST liability by component (what a GSTR-3B summary would need)
SELECT order_month,
       ROUND(SUM(taxable_value), 0) AS taxable_value_inr,
       ROUND(SUM(cgst), 0) AS cgst_inr,
       ROUND(SUM(sgst), 0) AS sgst_inr,
       ROUND(SUM(igst), 0) AS igst_inr,
       ROUND(SUM(gst_amount), 0) AS total_gst_inr
FROM sales
WHERE is_net_sale = 1
GROUP BY order_month
ORDER BY order_month;

-- Q11. B2B vs B2C
SELECT CASE WHEN is_b2b = 1 THEN 'B2B' ELSE 'B2C' END AS customer_type,
       COUNT(*) AS lines,
       ROUND(SUM(amount), 0) AS net_sales_inr,
       ROUND(AVG(amount), 0) AS avg_line_value_inr
FROM sales
WHERE is_net_sale = 1
GROUP BY customer_type;

-- Q12. Best day of week (strftime('%w'): 0 = Sunday)
SELECT CASE strftime('%w', order_date)
           WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday'
           WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' ELSE 'Saturday' END AS weekday,
       ROUND(SUM(amount), 0) AS net_sales_inr
FROM sales
WHERE is_net_sale = 1 AND order_date BETWEEN '2022-04-01' AND '2022-06-28'
GROUP BY weekday
ORDER BY net_sales_inr DESC;
