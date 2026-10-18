-- ⚠️ 重要：本文件是 SQLite 数据库的脚本，请用「跑SQL.bat」或 DB Browser 执行。
--    不要拿到 SSMS（SQL Server）里跑！两者语法不一样，会报语法错误。
--    比如 SQLite 的 "DROP VIEW IF EXISTS" 在 SQL Server 里要写成
--    "IF OBJECT_ID('xxx') IS NOT NULL DROP VIEW xxx"。

-- ============================================================
-- 03 评价表去重
-- ------------------------------------------------------------
-- 口径 5：同一订单有多条评价时，取 review_creation_date 最新的一条
--
-- 为什么要去重：原始评价表 99,224 行，但只涉及 98,673 个订单，
--               有 547 个订单写了 2 条以上评价。不去重就算平均分，
--               这些订单会被重复计算，评分和差评率都会偏
--
-- 预期：全量去重后 98,673 行；其中属于分析窗口的 95,568 行
--
-- 考点（面试区分度最高的一条）：窗口函数
--       ROW_NUMBER() OVER (PARTITION BY 订单 ORDER BY 时间 DESC)
--       意思是：把同一个订单的评价排成一队，按时间倒序编号，只留 1 号
--
--       对比 DISTINCT：DISTINCT 只能整行去重，
--       而"同一订单保留最新一条"必须用窗口函数，这是两者最大的区别
-- ============================================================

DROP VIEW IF EXISTS v_reviews_dedup;

CREATE VIEW v_reviews_dedup AS
SELECT
    order_id,
    review_score,
    review_creation_date
FROM (
    SELECT
        order_id,
        review_score,
        review_creation_date,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY review_creation_date DESC
        ) AS rn
    FROM olist_order_reviews
) ranked
WHERE rn = 1;
