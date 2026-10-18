-- ⚠️ 重要：本文件是 SQLite 数据库的脚本，请用「跑SQL.bat」或 DB Browser 执行。
--    不要拿到 SSMS（SQL Server）里跑！两者语法不一样，会报语法错误。
--    比如 SQLite 的 "DROP VIEW IF EXISTS" 在 SQL Server 里要写成
--    "IF OBJECT_ID('xxx') IS NOT NULL DROP VIEW xxx"。

-- ============================================================
-- 01 筛出有效的分析订单
-- ------------------------------------------------------------
-- 口径 1：只算 order_status = 'delivered'（未送达的订单没有成交意义）
-- 口径 2：下单时间在 2017-01-01 ~ 2018-09-01 之间（左闭右开）
--         左右两端的数据不完整，2016 年只有零星订单，
--         2018-09 之后数据被截断，详见《数据问题清单》第七节
-- 预期结果：96,211 行
--
-- 考点：WHERE 的多个条件用 AND 连接；日期在 SQLite 里是文本，
--       因为格式是标准的 YYYY-MM-DD HH:MM:SS，直接比大小结果就是对的
-- ============================================================

DROP VIEW IF EXISTS v_valid_orders;

CREATE VIEW v_valid_orders AS
SELECT
    order_id,
    customer_id,
    order_purchase_timestamp,
    order_estimated_delivery_date,
    order_delivered_customer_date
FROM olist_orders
WHERE order_status = 'delivered'
  AND order_purchase_timestamp >= '2017-01-01'
  AND order_purchase_timestamp <  '2018-09-01';
