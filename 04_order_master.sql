-- ⚠️ 重要：本文件是 SQLite 数据库的脚本，请用「跑SQL.bat」或 DB Browser 执行。
--    不要拿到 SSMS（SQL Server）里跑！两者语法不一样，会报语法错误。
--    比如 SQLite 的 "DROP VIEW IF EXISTS" 在 SQL Server 里要写成
--    "IF OBJECT_ID('xxx') IS NOT NULL DROP VIEW xxx"。

-- ============================================================
-- 04 拼成分析用的宽表（一行一订单）
-- ------------------------------------------------------------
-- 这是后面所有分析的取数入口：
--   Python 里一句 SELECT * FROM v_order_master 就能开始干活
--
-- 预期：96,211 行（和 v_valid_orders 一样，一行一订单，不能被连接放大）
--
-- 考点：
--   * 多表 JOIN：订单表 + 买家表 + 金额视图 + 评价视图
--   * JOIN 和 LEFT JOIN 的区别：必须用 LEFT JOIN！
--     有 643 个订单没有评价，用 JOIN 会把它们整行丢掉，行数就少了
--   * CASE WHEN 做条件判断（算是否超时）
--   * 日期函数 julianday() 算天数差，substr() 取年份月份
--   * 粒度意识：这张表一行 = 一个订单。所有参与 JOIN 的表
--     在 order_id 这一层必须都是唯一的，否则行数会被放大
-- ============================================================

DROP VIEW IF EXISTS v_order_master;

CREATE VIEW v_order_master AS
SELECT
    v.order_id,
    c.customer_unique_id,
    c.customer_state,
    c.customer_city,
    c.customer_zip_code_prefix,
    v.order_purchase_timestamp,
    substr(v.order_purchase_timestamp, 1, 7)  AS order_month,
    v.order_delivered_customer_date,
    v.order_estimated_delivery_date,
    CAST(
        julianday(v.order_delivered_customer_date)
        - julianday(v.order_purchase_timestamp)
    AS INTEGER)                               AS delivery_days,
    CASE
        WHEN v.order_delivered_customer_date IS NULL THEN NULL
        WHEN v.order_delivered_customer_date
             > v.order_estimated_delivery_date THEN 1
        ELSE 0
    END                                       AS is_late,
    a.gmv,
    a.freight,
    a.items,
    r.review_score
FROM v_valid_orders v
JOIN olist_customers c       ON c.customer_id = v.customer_id
LEFT JOIN v_order_amount a   ON a.order_id = v.order_id
LEFT JOIN v_reviews_dedup r  ON r.order_id = v.order_id;
