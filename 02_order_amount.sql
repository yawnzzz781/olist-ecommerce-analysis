-- ⚠️ 重要：本文件是 SQLite 数据库的脚本，请用「跑SQL.bat」或 DB Browser 执行。
--    不要拿到 SSMS（SQL Server）里跑！两者语法不一样，会报语法错误。
--    比如 SQLite 的 "DROP VIEW IF EXISTS" 在 SQL Server 里要写成
--    "IF OBJECT_ID('xxx') IS NOT NULL DROP VIEW xxx"。

-- ============================================================
-- 02 按订单汇总金额
-- ------------------------------------------------------------
-- 口径 4：GMV = 只加 price，不含 freight_value
--         运费是物流成本，不是商品销售额。要另一口径就另建字段，禁止混用
--
-- 关键点：先按订单分组（GROUP BY order_id）再往上汇总。
--         订单明细表是「一单多件商品」，不分组直接求和，
--         订单数会被算重，客单价就错了
--
-- 预期：96,211 行；gmv 合计 13,181,027.13；运费合计 2,192,092.88
--
-- 考点：GROUP BY + 聚合函数（SUM / COUNT）、CAST 转类型、
--       用 IN (子查询) 过滤出目标订单
-- ============================================================

DROP VIEW IF EXISTS v_order_amount;

CREATE VIEW v_order_amount AS
SELECT
    order_id,
    ROUND(SUM(CAST(price AS REAL)), 2)          AS gmv,
    ROUND(SUM(CAST(freight_value AS REAL)), 2)  AS freight,
    COUNT(*)                                    AS items
FROM olist_order_items
WHERE order_id IN (SELECT order_id FROM v_valid_orders)
GROUP BY order_id;
