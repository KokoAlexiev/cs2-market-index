-- Data-quality breakdown: how many rows hit each flag, and the overall rate.
-- Run on the Databricks SQL endpoint over silver_sales.
SELECT
    COUNT(*)                                                            AS total_rows,
    SUM(CAST(dq_missing_buff    AS INT))                                AS missing_buff,
    SUM(CAST(dq_missing_csfloat AS INT))                                AS missing_csfloat,
    SUM(CAST(dq_extreme_markup  AS INT))                                AS extreme_markup,
    SUM(CAST((dq_missing_buff OR dq_missing_csfloat OR dq_extreme_markup) AS INT)) AS any_flag,
    ROUND(100.0 * AVG(CASE WHEN dq_missing_buff OR dq_missing_csfloat OR dq_extreme_markup
                           THEN 1 ELSE 0 END), 2)                       AS any_flag_pct
FROM silver_sales;
