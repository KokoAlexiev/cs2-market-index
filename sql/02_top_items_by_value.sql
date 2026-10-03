-- The 15 items that moved the most money over the whole period.
-- Run on the Databricks SQL endpoint over silver_sales.
SELECT
    item,
    COUNT(*)                            AS sales,
    ROUND(SUM(price), 2)                AS total_value,
    ROUND(percentile(price, 0.5), 2)    AS median_price
FROM silver_sales
GROUP BY item
ORDER BY total_value DESC
LIMIT 15;
