SELECT * FROM branches;
SELECT * FROM expenses;
SELECT * FROM sales;
SELECT * FROM sales_items;
SELECT * FROM menu_items;

--Branch report

--	Total revenue per branch (completed sales only).
SELECT b.branch_id, b.branch_name, sum(s.total_amount) AS total_revenue
FROM branches b
JOIN sales s ON b.branch_id = s.branch_id
WHERE s.transaction_status = 'COMPLETED'
GROUP BY b.branch_id, b.branch_name
ORDER BY total_revenue DESC;

--•	Number of transactions by payment method.
SELECT payment_method, COUNT(*) AS transaction_count
FROM sales
GROUP BY payment_method
ORDER BY transaction_count DESC;

--•	Number of transactions by order channel.
SELECT order_channel, COUNT(*) AS transaction_count
FROM sales
GROUP BY order_channel
ORDER BY transaction_count DESC;

SELECT
    b.branch_id,
    b.branch_name,
    ROUND(
        AVG(
            EXTRACT(EPOCH FROM (
                s.customer_departure_time -
                s.customer_arrival_time
            )) / 60
        ),
        2
    ) AS average_dwell_time_minutes
FROM branches b
JOIN sales s
ON b.branch_id = s.branch_id
WHERE s.customer_departure_time > s.customer_arrival_time
GROUP BY b.branch_id, b.branch_name
ORDER BY average_dwell_time_minutes DESC;

--•	Number of failed transactions.
SELECT COUNT(*) AS failed_transaction_count
FROM sales
WHERE transaction_status = 'FAILED';

--•	Most frequently ordered items from order_items_clean.
SELECT m.menu_item_id, m.item_name, COUNT(s.*) AS order_count
FROM menu_items m
JOIN sales_items si ON m.menu_item_id = si.menu_item_id
JOIN sales s ON s.record_id = si.record_id
GROUP BY m.menu_item_id, m.item_name
ORDER BY order_count DESC;


--Regional report

--•	Compare revenue vs. expenses by branch.
SELECT b.branch_id, b.branch_name, 
       COALESCE(SUM(s.total_amount), 0) AS total_revenue,
       COALESCE(SUM(e.amount), 0) AS total_expenses
FROM branches b
LEFT JOIN sales s ON b.branch_id = s.branch_id
LEFT JOIN expenses e ON b.branch_id = e.branch_id
GROUP BY b.branch_id, b.branch_name;

--•	Calculate membership penetration (members ÷ total transactions).
SELECT 
    b.branch_id, 
    b.branch_name, 
    COUNT(s.membership_id) / NULLIF(COUNT(s.record_id),0) AS membership_penetration
FROM branches b
LEFT JOIN sales s ON b.branch_id = s.branch_id
GROUP BY b.branch_id, b.branch_name;

--•	Calculate discount usage rate (transactions with discounts ÷ total transactions).
SELECT 
    b.branch_id, 
    b.branch_name, 
    COUNT(CASE WHEN s.discount_applied > 0 THEN 1 END) / NULLIF(COUNT(s.record_id),0) AS discount_usage_rate
FROM branches b
LEFT JOIN sales s ON b.branch_id = s.branch_id
GROUP BY b.branch_id, b.branch_name;    

--•	Total network-wide revenue and expenses.
SELECT SUM(total_amount) AS total_network_revenue
FROM sales
WHERE transaction_status='COMPLETED';

SELECT SUM(amount) AS total_network_expenses
FROM expenses;

--Top 5 branches by Revenue
SELECT b.branch_name, SUM(s.total_amount) AS revenue
FROM branches b
JOIN sales s
ON b.branch_id=s.branch_id
WHERE s.transaction_status='COMPLETED'
GROUP BY b.branch_name
ORDER BY revenue DESC
LIMIT 5;

--Bottom 5 branches by Revenue
SELECT b.branch_name, SUM(s.total_amount) AS revenue
FROM branches b
JOIN sales s
ON b.branch_id=s.branch_id
WHERE s.transaction_status='COMPLETED'
GROUP BY b.branch_name
ORDER BY revenue ASC
LIMIT 5;

--•	Overall transaction status counts.
SELECT transaction_status, COUNT(*) AS transaction_count
FROM sales
GROUP BY transaction_status;

--•	Week-over-week revenue trend using customer_arrival_time.
SELECT DATE_TRUNC('week', customer_arrival_time) AS week,
        SUM(total_amount) AS revenue
FROM sales
WHERE transaction_status='COMPLETED'
GROUP BY week
ORDER BY week;