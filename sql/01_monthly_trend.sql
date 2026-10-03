-- Monthly market summary, run on the Databricks SQL endpoint over silver_sales.
-- How many sales, the typical (median) price, the average markup, and the share
-- of rows carrying a data-quality flag, per month.
SELECT
    date_format(sale_date, 'yyyy-MM')                               AS month,
    COUNT(*)                                                        AS sales,
    ROUND(percentile(price, 0.5), 2)                                AS median_price,
    ROUND(AVG(markup_pct), 2)                                       AS avg_markup_pct,
    ROUND(100.0 * AVG(CASE WHEN dq_missing_buff OR dq_missing_csfloat OR dq_extreme_markup
                           THEN 1 ELSE 0 END), 2)                   AS dq_rate_pct
FROM silver_sales
GROUP BY date_format(sale_date, 'yyyy-MM')
ORDER BY month;
