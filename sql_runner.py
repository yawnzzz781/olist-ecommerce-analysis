# -*- coding: utf-8 -*-
r"""
一个极简的 SQL 练习器：输入 SQL，直接看到结果表格。

为什么有这个东西：图形工具（DB Browser）下载太慢，这个让你今天就能开始练。
等图形工具装好之后也留着它 —— 随手试一条 SQL 比开大工具快。

用法：双击项目里的「跑SQL.bat」

能查的东西
  视图（练习推荐用这些）：
    v_order_master   ★ 分析主表，一行一订单
    v_valid_orders   有效订单（已送达 + 时间窗内）
    v_order_amount   每单的 gmv / freight / items
    v_reviews_dedup  去重后的评价
  原始表 9 张：olist_orders / olist_order_items / olist_customers /
              olist_order_reviews / olist_products / olist_sellers /
              olist_order_payments / olist_geolocation /
              product_category_name_translation
"""

import os
import sqlite3
import sys
import time

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "olist.db")

HELP = """
================================================================
 可用对象
================================================================
 练习请用这张表（查询 0.01 秒）：
   order_master      ★★ 一行一订单的分析主表
       字段：
       order_id / customer_unique_id / customer_state / customer_city /
       customer_zip_code_prefix / order_purchase_timestamp / order_month /
       order_delivered_customer_date / order_estimated_delivery_date /
       delivery_days / is_late / gmv / freight / items / review_score

   v_order_master    和上面字段一模一样，但是"视图"，每次查询要现算约 5 秒
                     （口径定义在这里，理解用；练习请用 order_master）
   v_valid_orders    有效订单（已送达 + 2017-01 ~ 2018-08）
   v_order_amount    每单的 gmv / freight / items
   v_reviews_dedup   去重后的评价（一单一条）

 原始表：
   olist_orders / olist_order_items / olist_customers / olist_order_reviews /
   olist_products / olist_sellers / olist_order_payments / olist_geolocation /
   product_category_name_translation

 小抄：
   看几行数据      SELECT * FROM order_master LIMIT 3;
   看字段名        SELECT * FROM order_master LIMIT 0;
================================================================
"""


def display_width(text):
    """中文按 2 个宽度算，表格才对得齐。"""
    width = 0
    for char in str(text):
        width += 2 if ord(char) > 0x2E80 else 1
    return width


def pad(text, width):
    text = str(text)
    return text + " " * max(0, width - display_width(text))


def print_table(cols, rows, limit=40):
    widths = [display_width(c) for c in cols]
    for row in rows[:limit]:
        for index, value in enumerate(row):
            shown = "NULL" if value is None else str(value)
            widths[index] = max(widths[index], display_width(shown))
    print()
    print(" " + " | ".join(pad(c, widths[i]) for i, c in enumerate(cols)))
    print(" " + "-+-".join("-" * width for width in widths))
    for row in rows[:limit]:
        cells = ["NULL" if v is None else v for v in row]
        print(" " + " | ".join(pad(cells[i], widths[i]) for i in range(len(cols))))
    if len(rows) > limit:
        print(f" … 还有 {len(rows) - limit} 行没显示（可以在 SQL 里加 LIMIT）")


def main():
    if not os.path.exists(DB):
        print("找不到数据库文件：", DB)
        print("请先双击「运行建库和清洗.bat」生成 olist.db")
        return

    con = sqlite3.connect(DB)
    print("=" * 64)
    print(" SQL 练习器 —— 连着你的 olist.db")
    print("=" * 64)
    print(HELP)
    print("怎么用：写 SQL → 回车 → 再按一次空回车执行。什么都不写直接回车就退出。")

    count = 0
    while True:
        print()
        print(f"--- 第 {count + 1} 条 ---")
        lines = []
        while True:
            try:
                line = input("sql> " if not lines else "  -> ")
            except EOFError:
                print("\n（输入结束）")
                return
            if line.strip() == "":
                break
            lines.append(line)
        sql = "\n".join(lines).strip().rstrip(";")
        if not sql:
            print("再见。记得把写好的 SQL 复制下来发我批改。")
            return
        count += 1
        started = time.time()
        try:
            cur = con.execute(sql)
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                print_table(cols, rows)
                print(f"\n 返回 {len(rows)} 行，用时 {time.time() - started:.3f} 秒")
            else:
                con.commit()
                print(f"\n 执行成功（影响 {cur.rowcount} 行），用时 {time.time() - started:.3f} 秒")
        except Exception as exc:  # noqa: BLE001
            print("\n SQL 出错：", exc)
            print(" 排查顺序：表名写对了吗 → 字段名写对了吗 → 逗号和引号配对了吗")


if __name__ == "__main__":
    main()
