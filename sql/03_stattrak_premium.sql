-- Does StatTrak sell for more? Median price for StatTrak vs non-StatTrak,
-- split by wear so we compare like with like.
-- Run on the Databricks SQL endpoint over silver_sales.
SELECT
    wear,
    ROUND(percentile(CASE WHEN stattrak     THEN price END, 0.5), 2) AS median_stattrak,
    ROUND(percentile(CASE WHEN NOT stattrak THEN price END, 0.5), 2) AS median_normal,
    COUNT(CASE WHEN stattrak     THEN 1 END)                         AS stattrak_sales,
    COUNT(CASE WHEN NOT stattrak THEN 1 END)                         AS normal_sales
FROM silver_sales
WHERE wear <> ''
GROUP BY wear
ORDER BY wear;
