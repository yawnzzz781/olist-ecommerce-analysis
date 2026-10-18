-- ⚠️ 重要：本文件是 SQLite 数据库的脚本，请用「跑SQL.bat」或 DB Browser 执行。
--    不要拿到 SSMS（SQL Server）里跑！两者语法不一样，会报语法错误。
--    比如 SQLite 的 "DROP VIEW IF EXISTS" 在 SQL Server 里要写成
--    "IF OBJECT_ID('xxx') IS NOT NULL DROP VIEW xxx"。

-- ============================================================
-- 05 给 JOIN 和排序用到的字段建索引
-- ------------------------------------------------------------
-- 为什么需要：视图是"每次查询时现算"，前面 4 个视图都是 JOIN 出来的。
--             不加索引，每次查 v_order_master 都要扫全表，7 秒才出结果。
--             给关联键建索引后，同样的查询 1 秒内就出来了。
--
-- 考点：索引 = 书的目录。它不改变查询结果，只让查找变快。
--       代价是占一点空间、写入稍慢。所以一般建在：
--         JOIN 用的关联键、WHERE 常筛的字段、ORDER BY 常排的字段
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_orders_status
    ON olist_orders(order_status);

CREATE INDEX IF NOT EXISTS idx_orders_customer
    ON olist_orders(customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_purchase
    ON olist_orders(order_purchase_timestamp);

CREATE INDEX IF NOT EXISTS idx_items_order
    ON olist_order_items(order_id);

CREATE INDEX IF NOT EXISTS idx_customers_customer
    ON olist_customers(customer_id);

CREATE INDEX IF NOT EXISTS idx_reviews_order_date
    ON olist_order_reviews(order_id, review_creation_date);
