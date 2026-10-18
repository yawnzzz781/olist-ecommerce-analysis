# -*- coding: utf-8 -*-
r"""
数据体检脚本 —— 检查 9 个 CSV 的空白格子、奇怪数字、表与表的连接关系
================================================================

【这个脚本干什么】
把 Olist 的 9 个 CSV 全部读一遍，自动帮你完成三件事：
  1. 数出每一列有多少格是空的、占多少百分比
  2. 找出奇怪的值（负数、零、异常大的数、超出合理范围的日期）
  3. 检查哪些列能把两张表连起来，以及有没有连不上的记录

【怎么运行】
  【最简单】直接双击同文件夹里的 "运行数据体检.bat"，等它跑完就行。

  【手动运行】在命令行里：
     cd /d D:\我的电商分析项目
     "C:\Users\15414\Anaconda3\python.exe" 01_数据体检.py

  注意：python 必须用上面那个完整路径。你电脑上装了好几个 Anaconda，
  开始菜单里几个名字很像的 Anaconda Prompt 指向的是 2018 年的老版本
  （Python 3.6 + pandas 0.23），那个版本在 Windows 上读不了带中文的路径，
  会报 "OSError: Initializing from file failed"。

  跑完会在同一个文件夹里生成 "数据体检结果.txt"（证据文件，不要删）。

【跑完要对照检查】
  跑出来的关键数字应该和 README.md 里"复现校验"那一节一致。
  如果对不上，先检查 DATA_DIR 这一行写的路径对不对。

【想检查别的文件夹】
改下面 DATA_DIR 这一行就行。
"""

import os
from collections import Counter

import pandas as pd

# ============ 需要修改的地方：只改这一行 ============
DATA_DIR = r"D:\我的电商分析项目\原始文件"
# ==================================================

# 结果同时打印到屏幕，也写进这个文件
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "数据体检结果.txt")

lines = []


def say(text=""):
    """打印一行，同时记到结果文件里。"""
    print(text)
    lines.append(text)


def title(text):
    say("")
    say("=" * 70)
    say(text)
    say("=" * 70)


def load(filename):
    """
    读取 CSV 文件。

    三个关键设置，说明一下为什么这么写：
      encoding="utf-8-sig"   用这个编码读，不管文件开头有没有那 3 个隐藏字节
                             （BOM）都能正确读出来，一劳永逸。
      dtype=str              所有列都先按"文字"读进来，不自动猜类型。
      keep_default_na=False  空的格子就保持为空，不要自动变成 "NaN" 这种字符串，
                             这样我们才能数清楚到底有多少格是空的。
    """
    return pd.read_csv(
        os.path.join(DATA_DIR, filename),
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )


def is_number_column(series):
    """判断一列是不是数字列（忽略空白格）。"""
    filled = series[series.str.strip() != ""]
    if len(filled) == 0:
        return False
    converted = pd.to_numeric(filled, errors="coerce")
    return converted.notna().mean() > 0.999


def is_date_column(series):
    """判断一列是不是日期时间列。"""
    filled = series[series.str.strip() != ""]
    if len(filled) == 0:
        return False
    sample = filled.head(3000)
    converted = pd.to_datetime(sample, errors="coerce", format="mixed")
    return converted.notna().mean() > 0.99


def main():
    files = sorted(f for f in os.listdir(DATA_DIR) if f.lower().endswith(".csv"))
    if not files:
        print("在下面这个文件夹里没找到 CSV 文件：")
        print(DATA_DIR)
        return

    tables = {}

    # ---------------- 第 1 部分：总览 ----------------
    title("第 1 部分：9 个文件总览")
    say("%-45s%10s%7s%12s" % ("文件名", "行数", "列数", "完全重复行"))
    for name in files:
        df = load(name)
        tables[name] = df
        say("%-45s%10d%7d%12d" % (name, len(df), df.shape[1], df.duplicated().sum()))

    # ---------------- 第 2 部分：空白格子 ----------------
    title("第 2 部分：哪些列有空白格子")
    found_any = False
    for name, df in tables.items():
        blanks = {}
        for col in df.columns:
            blank_count = int((df[col].str.strip() == "").sum())
            if blank_count > 0:
                blanks[col] = blank_count
        if blanks:
            found_any = True
            say("")
            say("--- %s （共 %d 行）---" % (name, len(df)))
            for col, count in sorted(blanks.items(), key=lambda kv: -kv[1]):
                percent = count / len(df) * 100
                say("   %-32s 空 %8d 格   占 %6.2f%%" % (col, count, percent))
    if not found_any:
        say("所有文件都没有空白格子。")

    # ---------------- 第 3 部分：奇怪的值 ----------------
    title("第 3 部分：奇怪的值（负数、零、极端大值、异常日期）")
    for name, df in tables.items():
        problems = []
        for col in df.columns:
            series = df[col]
            if is_number_column(series):
                values = pd.to_numeric(
                    series[series.str.strip() != ""], errors="coerce"
                ).dropna()
                if (values < 0).sum() > 0:
                    problems.append(
                        "   %s: 有 %d 个负数（最小 %s）" % (col, (values < 0).sum(), values.min())
                    )
                if (values == 0).sum() > 0:
                    problems.append("   %s: 有 %d 个零" % (col, (values == 0).sum()))
                q99 = values.quantile(0.99)
                if q99 > 0 and values.max() > q99 * 5:
                    problems.append(
                        "   %s: 最大值 %s 远大于 99%% 分位 %.2f，可能有极端值"
                        % (col, values.max(), q99)
                    )
            elif is_date_column(series):
                dates = pd.to_datetime(
                    series[series.str.strip() != ""], errors="coerce", format="mixed"
                ).dropna()
                problems.append("   %s: 时间范围 %s ~ %s" % (col, dates.min(), dates.max()))
                strange = dates[(dates.dt.year < 2010) | (dates.dt.year > 2026)]
                if len(strange) > 0:
                    problems.append(
                        "   %s: 有 %d 个时间超出 2010-2026 年" % (col, len(strange))
                    )
        if problems:
            say("")
            say("--- %s ---" % name)
            for line in problems:
                say(line)

    # ---------------- 第 4 部分：主键唯一性 ----------------
    title("第 4 部分：哪些列能唯一标识一行（主键检查）")
    key_tests = [
        ("olist_orders_dataset.csv", ["order_id"], "订单编号"),
        ("olist_order_items_dataset.csv", ["order_id", "order_item_id"], "订单编号+明细序号"),
        ("olist_order_payments_dataset.csv", ["order_id", "payment_sequential"], "订单编号+付款序号"),
        ("olist_order_reviews_dataset.csv", ["review_id"], "评价编号"),
        ("olist_order_reviews_dataset.csv", ["order_id"], "订单编号"),
        ("olist_customers_dataset.csv", ["customer_id"], "下单编号"),
        ("olist_customers_dataset.csv", ["customer_unique_id"], "顾客编号"),
        ("olist_products_dataset.csv", ["product_id"], "商品编号"),
        ("olist_sellers_dataset.csv", ["seller_id"], "卖家编号"),
        ("product_category_name_translation.csv", ["product_category_name"], "品类名"),
    ]
    for filename, keys, label in key_tests:
        df = tables.get(filename)
        if df is None:
            continue
        if any(k not in df.columns for k in keys):
            continue
        duplicated = int(df.duplicated(subset=keys).sum())
        if duplicated == 0:
            verdict = "唯一（可以当主键）"
        else:
            verdict = "不唯一（重复 %d 行）" % duplicated
        say("%-45s %-18s -> %s" % (filename, label, verdict))

    # ---------------- 第 5 部分：表与表的连接 ----------------
    title("第 5 部分：哪些列能把两张表连起来（连接匹配率）")
    joins = [
        ("olist_order_items_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
        ("olist_order_payments_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
        ("olist_order_reviews_dataset.csv", "order_id", "olist_orders_dataset.csv", "order_id"),
        ("olist_orders_dataset.csv", "customer_id", "olist_customers_dataset.csv", "customer_id"),
        ("olist_order_items_dataset.csv", "product_id", "olist_products_dataset.csv", "product_id"),
        ("olist_order_items_dataset.csv", "seller_id", "olist_sellers_dataset.csv", "seller_id"),
        ("olist_customers_dataset.csv", "customer_zip_code_prefix",
         "olist_geolocation_dataset.csv", "geolocation_zip_code_prefix"),
        ("olist_products_dataset.csv", "product_category_name",
         "product_category_name_translation.csv", "product_category_name"),
    ]
    for child_file, child_key, parent_file, parent_key in joins:
        child = tables.get(child_file)
        parent = tables.get(parent_file)
        if child is None or parent is None:
            continue
        if child_key not in child.columns or parent_key not in parent.columns:
            continue
        # 注意：这里用 - {""} 把空白格排除掉，因为空白不是一种"值"，不该参与匹配
        child_set = set(child[child_key].str.strip()) - {""}
        parent_set = set(parent[parent_key].str.strip()) - {""}
        unmatched = child_set - parent_set
        rate = (len(child_set) - len(unmatched)) / len(child_set) * 100
        say("")
        say("%s . %s   ->   %s . %s" % (
            child_file.replace("_dataset.csv", ""), child_key,
            parent_file.replace("_dataset.csv", ""), parent_key,
        ))
        say("    子表有 %d 个不同取值，其中 %d 个在父表里找不到（匹配率 %.2f%%）"
            % (len(child_set), len(unmatched), rate))
        if 0 < len(unmatched) <= 10:
            say("    找不到的具体是：%s" % sorted(unmatched))

    # ---------------- 第 6 部分：常用分布 ----------------
    title("第 6 部分：几个常用分布（写报告时可以直接引用）")
    orders = tables.get("olist_orders_dataset.csv")
    reviews = tables.get("olist_order_reviews_dataset.csv")
    if orders is not None and "order_status" in orders.columns:
        say("订单状态分布：")
        for status, count in sorted(Counter(orders["order_status"]).items(), key=lambda kv: -kv[1]):
            say("   %-14s %8d 单" % (status, count))
        delivered = orders[orders["order_status"] == "delivered"]
        say("")
        say("已送达订单数：%d" % len(delivered))
        blank_delivered = (
            delivered["order_delivered_customer_date"].str.strip() == ""
        ).sum()
        say("已送达但签收时间为空：%d 单" % blank_delivered)
    if reviews is not None and "review_score" in reviews.columns:
        say("")
        say("评分分布：")
        for score, count in sorted(Counter(reviews["review_score"]).items()):
            say("   %s 分  %8d 条" % (score, count))
        say("")
        say("写了评论内容的评价数：%d"
            % (reviews["review_comment_message"].str.strip() != "").sum())

    # 写文件
    # encoding="utf-8-sig" 会写入 BOM，这样用记事本 / Excel 打开都不会乱码
    with open(OUT_FILE, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print("")
    print("=" * 70)
    print("检查完成，结果已保存到：%s" % OUT_FILE)
    print("=" * 70)


if __name__ == "__main__":
    main()
