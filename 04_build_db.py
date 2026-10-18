# -*- coding: utf-8 -*-
r"""
第 4 步（SQL 版）：把 9 个 CSV 装进 SQLite，然后用 SQL 做清洗
================================================================

【这个脚本干什么】
  1. 把 原始文件\ 里的 9 个 CSV 导入成一个 SQLite 数据库 olist.db
  2. 按顺序执行 sql\ 目录下的 4 个 SQL 文件，建出 4 个视图
     （第 5 个文件是建索引，让查询从 7 秒降到 1 秒以内）
  2.5 把 v_order_master 视图物化成表 order_master
     （视图每次查询要现算约 5 秒；物化成表后查询 0.01 秒，练习时体验完全不同）
  3. 校验：把每个视图的行数和关键指标打印出来
  4. 和 pandas 版（03_clean.py 的产出）对比，确认两套实现算出来是同一个数
  5. 把 SQL 版宽表导出成 CSV，给 Power BI 用

【和 03_clean.py 的分工】
  03_clean.py  = pandas 版清洗（Python 干全部活）
  04_build_db.py + sql\ = SQL 版清洗（SQL 干筛选/连接/聚合/去重）
  两个都跑、数字对得上 → 交叉验证通过

【怎么运行】
  最简单：双击项目里的「运行建库和清洗.bat」
  手动：  "C:\Users\15414\Anaconda3\python.exe" 04_build_db.py

【产出】
  olist.db                         SQLite 数据库（9 张原始表 + 4 个视图）
  建库日志.txt                     全部输出（证据文件）
  原始文件副本\cleaned\order_master_sql.csv   SQL 版宽表（给 Power BI）
"""

import os
import sqlite3
import sys
import time

import pandas as pd

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "原始文件")
SQL_DIR = os.path.join(HERE, "sql")
DB_PATH = os.path.join(HERE, "olist.db")
CLEANED = os.path.join(HERE, "原始文件副本", "cleaned")
LOG_PATH = os.path.join(HERE, "建库日志.txt")

lines = []
results = []


def say(text=""):
    print(text)
    lines.append(text)


def check(label, actual, expect, tolerance=0.0):
    """actual 和 expect 是否一致。tolerance 用于小数对比。"""
    if expect is None:
        ok = True
        tail = "（只记录，不做判定）"
    else:
        ok = abs(actual - expect) <= tolerance
        tail = "" if ok else f"   <<< 预期 {expect}"
    say(f"    [{'OK' if ok else '!!'}] {label:<34} {actual}{tail}")
    results.append((label, actual, expect, ok))


def main():
    started = time.time()
    say("=" * 70)
    say("第 4 步（SQL 版）：建库 + SQL 清洗 + 交叉验证")
    say("=" * 70)
    say(f"数据来源：{SRC}")
    say(f"SQL 文件：{SQL_DIR}")
    say(f"数据库：  {DB_PATH}")

    if not os.path.isdir(SQL_DIR):
        say(f"\n找不到 sql 目录：{SQL_DIR}")
        return

    # 建库（每次重建，保证可重复运行）
    if os.path.exists(DB_PATH):
        say("\n检测到旧的 olist.db，先删掉重建（保证每次跑的结果一致）")
        try:
            os.remove(DB_PATH)
        except PermissionError:
            say("")
            say("[停止] 删不掉 olist.db —— 它正被别的程序占用。")
            say("  最常见的原因：在 Trae / DB Browser / 记事本 里打开了它。")
            say("  处理办法：把那些窗口关掉（Trae 要整个关掉或重启），再重跑本脚本。")
            say("  注意：你的数据库本身没问题，只是没法重建。")
            return
    con = sqlite3.connect(DB_PATH)

    # ---------------- 第 1 步：导入 CSV ----------------
    say("\n【第 1 步】把 9 个 CSV 导入数据库")
    say("-" * 70)
    total_rows = 0
    for name in sorted(os.listdir(SRC)):
        if not name.lower().endswith(".csv"):
            continue
        table = name.replace("_dataset.csv", "").replace(".csv", "")
        frame = pd.read_csv(
            os.path.join(SRC, name), dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
        frame.to_sql(table, con, if_exists="replace", index=False)
        total_rows += len(frame)
        say(f"    {table:<38} {len(frame):>8} 行 x {frame.shape[1]:>2} 列")
    say(f"    合计 {total_rows} 行")
    check("导入的总行数", total_rows, 1550922)
    con.commit()

    # ---------------- 第 2 步：执行 SQL ----------------
    say("\n【第 2 步】按顺序执行 sql 目录下的文件")
    say("-" * 70)
    sql_files = sorted(f for f in os.listdir(SQL_DIR) if f.lower().endswith(".sql"))
    for name in sql_files:
        # 用 utf-8-sig 读：sql 文件带 BOM（这样在 SSMS/记事本里中文不乱码），
        # 直接按 utf-8 读会把 BOM 字符当成 SQL 的一部分，第一条语句就废了
        script = open(os.path.join(SQL_DIR, name), encoding="utf-8-sig").read()
        con.executescript(script)
        say(f"    [已执行] {name}")
    con.commit()
    views = con.execute(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
    ).fetchall()
    say(f"    建出 {len(views)} 个视图：" + "、".join(v[0] for v in views))

    say("\n【第 2.5 步】把宽表视图物化成表（视图每次查询要现算，约 5 秒）")
    say("-" * 70)
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS order_master")
    con.execute("CREATE TABLE order_master AS SELECT * FROM v_order_master")
    for column in ["customer_state", "order_month", "customer_unique_id"]:
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_master_{column} ON order_master({column})"
        )
    con.commit()
    say(f"    完成，用时 {time.time() - t0:.0f} 秒")
    say("    视图 = 口径定义（改一处全篇生效）；表 = 查询快（练习和分析用它）")

    # ---------------- 第 3 步：校验 ----------------
    say("\n【第 3 步】校验（这些数字就是你的标准答案）")
    say("-" * 70)
    V = "SELECT order_id FROM v_valid_orders"

    def one(sql):
        return con.execute(sql).fetchone()[0]

    check("筛出有效订单 v_valid_orders",
          one("SELECT COUNT(*) FROM v_valid_orders"), 96211)
    check("涉及多少人（去重）",
          one("SELECT COUNT(DISTINCT customer_unique_id) FROM v_order_master"), 93104)
    check("有效订单的明细行数",
          one(f"SELECT COUNT(*) FROM olist_order_items WHERE order_id IN ({V})"), 109880)
    check("汇总后的订单数 v_order_amount",
          one("SELECT COUNT(*) FROM v_order_amount"), 96211)
    check("GMV 合计（不含运费）",
          one("SELECT ROUND(SUM(gmv), 2) FROM v_order_amount"), 13181027.13, 0.05)
    check("运费合计",
          one("SELECT ROUND(SUM(freight), 2) FROM v_order_amount"), 2192092.88, 0.05)
    check("评价去重后总行数 v_reviews_dedup",
          one("SELECT COUNT(*) FROM v_reviews_dedup"), None)
    check("其中属于分析窗口的",
          one(f"SELECT COUNT(*) FROM v_reviews_dedup WHERE order_id IN ({V})"), 95568)
    check("分析宽表行数 v_order_master",
          one("SELECT COUNT(*) FROM v_order_master"), 96211)
    check("物化表 order_master 行数",
          one("SELECT COUNT(*) FROM order_master"), 96211)
    check("宽表里没有评分的订单",
          one("SELECT COUNT(*) FROM v_order_master WHERE review_score IS NULL"), 643)
    check("宽表里的配送超时订单",
          one("SELECT COUNT(*) FROM v_order_master WHERE is_late = 1"), None)
    check("宽表平均评分",
          one("SELECT ROUND(AVG(CAST(review_score AS REAL)), 3) FROM v_order_master"),
          4.156, 0.001)

    # ---------------- 第 4 步：和 pandas 版对比 ----------------
    say("\n【第 4 步】和 pandas 版（03_clean.py 的产出）交叉验证")
    say("-" * 70)
    pandas_file = os.path.join(CLEANED, "order_master.csv")
    if os.path.exists(pandas_file):
        pdf = pd.read_csv(pandas_file, encoding="utf-8-sig")
        sql_count = one("SELECT COUNT(*) FROM v_order_master")
        sql_gmv = one("SELECT ROUND(SUM(gmv), 2) FROM v_order_master")
        pd_gmv = round(float(pdf["gmv"].sum()), 2)
        pd_count = len(pdf)
        say(f"    pandas 版 order_master.csv：{pd_count} 行，GMV 合计 {pd_gmv}")
        say(f"    SQL    版 v_order_master  ：{sql_count} 行，GMV 合计 {sql_gmv}")
        check("两版行数一致", sql_count, pd_count)
        check("两版 GMV 一致（允许 1 分钱误差）", sql_gmv, pd_gmv, 0.01)

        # 逐行对比订单编号集合
        sql_ids = pd.read_sql("SELECT order_id FROM v_order_master", con)["order_id"]
        only_in_sql = len(set(sql_ids) - set(pdf["order_id"]))
        only_in_pd = len(set(pdf["order_id"]) - set(sql_ids))
        check("只在 SQL 版出现的订单号", only_in_sql, 0)
        check("只在 pandas 版出现的订单号", only_in_pd, 0)
    else:
        say(f"    找不到 {pandas_file}，跳过对比（先跑一次 03_clean.py）")

    # ---------------- 第 5 步：导出给 Power BI ----------------
    say("\n【第 5 步】把 SQL 版宽表导出成 CSV")
    say("-" * 70)
    os.makedirs(CLEANED, exist_ok=True)
    out = os.path.join(CLEANED, "order_master_sql.csv")
    master = pd.read_sql("SELECT * FROM v_order_master", con)
    master.to_csv(out, index=False, encoding="utf-8-sig")
    say(f"    已写出 {out}（{len(master)} 行，{os.path.getsize(out):,} 字节）")

    con.close()

    # ---------------- 汇总 ----------------
    bad = [r for r in results if not r[3]]
    say("\n" + "=" * 70)
    if bad:
        say(f"有 {len(bad)} 项对不上，请先检查再往下做：")
        for label, actual, expect, _ok in bad:
            say(f"    {label}：实际 {actual}，预期 {expect}")
    else:
        say(f"全部 {len(results)} 项校验通过。")
        say("SQL 版和 pandas 版算出来是同一个数 —— 交叉验证通过。")
    say(f"总耗时 {time.time() - started:.0f} 秒")
    say("=" * 70)

    with open(LOG_PATH, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print(f"\n日志已保存：{LOG_PATH}")


if __name__ == "__main__":
    main()
