# -*- coding: utf-8 -*-
r"""
第 5 步：搭建指标体系，产出「月度指标总表」
================================================================

【这一步在干什么】
把上一版清洗好的数据（order_master），汇总成一张"每月一行、每列一个指标"的表。
这张表是后面所有分析和看板的地基 —— 图表都是从这里来的。

【指标是怎么搭起来的】
                  GMV（北极星：卖了多少钱）
                    │
        ┌───────────┴───────────┐
        │                       │
      订单数  ×              客单价
        │
   ┌────┴────┐
   │         │
 下单人数 × 人均订单数

  另外盯着 5 个"健康度"指标：
   复购率、超时率、平均配送天数、平均评分、差评率

【口径】（和《数据问题清单》第七节一致，全篇统一）
  GMV       只加商品价格，不含运费
  订单数     = 已送达且在下单时间窗内的订单数
  下单人数   用 customer_unique_id 去重（不是 customer_id）
  客单价     GMV / 订单数
  复购率     当月下单 ≥2 次的人数 / 当月下单人数
  超时率     签收时间晚于承诺时间的订单占比（缺签收时间的 8 单不计入分母）
  平均评分 / 差评率   差评 = 评分 ≤2 分；没有评分的订单不计入分母

【怎么运行】
  双击项目里的「运行指标总表.bat」

【产出】
  指标总表.csv      每月一行，直接可以用 Excel 打开
  指标总表.txt      文字版（含整体概览和关键解读）
  核心指标趋势.png   4 个核心指标的月度趋势图
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "原始文件副本", "cleaned", "order_master.csv")
OUT_CSV = os.path.join(HERE, "指标总表.csv")
OUT_TXT = os.path.join(HERE, "指标总表.txt")
OUT_PNG = os.path.join(HERE, "核心指标趋势.png")

lines = []


def say(text=""):
    print(text)
    lines.append(text)


def pick_font():
    for name in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC"]:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            return name
        except Exception:  # noqa: BLE001
            continue
    return None


def main():
    if not os.path.exists(SRC):
        print("找不到清洗后的数据：", SRC)
        print("请先双击「运行数据清洗.bat」")
        return

    df = pd.read_csv(SRC, encoding="utf-8-sig")
    # 只转换确实存在的列（pandas 版和 SQL 版的列名现在统一了，但多一层保险）
    for column in ["gmv", "freight", "items", "categories",
                   "review_score", "is_late", "delivery_days"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    say("=" * 72)
    say("第 5 步：月度指标总表")
    say("=" * 72)
    say(f"数据源：{SRC}")
    say(f"共 {len(df)} 个订单，{df['order_month'].nunique()} 个月"
        f"（{df['order_month'].min()} ~ {df['order_month'].max()}）")

    # ---------------- 整体概览 ----------------
    total_gmv = df["gmv"].sum()
    total_orders = len(df)
    total_users = df["customer_unique_id"].nunique()
    orders_per_user = df.groupby("customer_unique_id").size()
    repeat_users = int((orders_per_user >= 2).sum())
    scored = df["review_score"].dropna()

    say("")
    say("【整体概览】20 个月合计")
    say("-" * 72)
    say(f"  GMV（不含运费）      {total_gmv:>15,.2f}")
    say(f"  运费合计             {df['freight'].sum():>15,.2f}"
        f"   （占 GMV 的 {df['freight'].sum() / total_gmv * 100:.1f}%）")
    say(f"  订单数               {total_orders:>15,}")
    say(f"  下单人数             {total_users:>15,}")
    say(f"  人均订单数           {total_orders / total_users:>15.2f}")
    say(f"  客单价               {total_gmv / total_orders:>15,.2f}")
    say(f"  复购人数             {repeat_users:>15,}"
        f"   （复购率 {repeat_users / total_users * 100:.2f}%）")
    say(f"  平均评分             {scored.mean():>15.3f}"
        f"   （{len(scored)} 个订单有评分，占 {len(scored) / total_orders * 100:.1f}%）")
    say(f"  差评率（≤2 分）      {(scored <= 2).mean() * 100:>15.2f}%")
    rate = df["is_late"].mean()
    say(f"  配送超时率           {rate * 100:>15.2f}%")
    say(f"  平均配送天数         {df['delivery_days'].mean():>15.1f} 天"
        f"   （中位数 {df['delivery_days'].median():.0f} 天）")

    # ---------------- 按月汇总 ----------------
    rows = []
    for month, group in df.groupby("order_month"):
        users = group["customer_unique_id"].nunique()
        per_user = group.groupby("customer_unique_id").size()
        repeat = int((per_user >= 2).sum())
        scores = group["review_score"].dropna()
        rows.append({
            "月份": month,
            "GMV": round(group["gmv"].sum(), 2),
            "订单数": len(group),
            "下单人数": users,
            "人均订单数": round(len(group) / users, 3),
            "客单价": round(group["gmv"].sum() / len(group), 2),
            "复购人数": repeat,
            "复购率%": round(repeat / users * 100, 2),
            "超时率%": round(group["is_late"].mean() * 100, 2),
            "平均配送天数": round(group["delivery_days"].mean(), 1),
            "平均评分": round(scores.mean(), 3) if len(scores) else None,
            "差评率%": round((scores <= 2).mean() * 100, 2) if len(scores) else None,
            "有评分率%": round(len(scores) / len(group) * 100, 2),
        })
    table = pd.DataFrame(rows)
    table["GMV环比%"] = (table["GMV"].pct_change() * 100).round(2)
    # 调整列顺序，环比放 GMV 后面
    order = ["月份", "GMV", "GMV环比%", "订单数", "下单人数", "人均订单数", "客单价",
             "复购人数", "复购率%", "超时率%", "平均配送天数", "平均评分", "差评率%", "有评分率%"]
    table = table[order]

    say("")
    say("【月度指标总表】")
    say("-" * 72)
    say(f"{'月份':<9}{'GMV':>12}{'环比%':>8}{'订单数':>8}{'人数':>8}"
        f"{'客单价':>8}{'复购率%':>8}{'超时率%':>8}{'评分':>7}")
    for _, row in table.iterrows():
        qoq = row["GMV环比%"]
        qoq_text = "  --" if pd.isna(qoq) else f"{qoq:>7.1f}"
        score = row["平均评分"]
        score_text = "  --" if pd.isna(score) else f"{score:>6.3f}"
        say(f"{row['月份']:<9}{row['GMV']:>12,.0f}{qoq_text}{int(row['订单数']):>8}"
            f"{int(row['下单人数']):>8}{row['客单价']:>8,.0f}"
            f"{row['复购率%']:>8.2f}{row['超时率%']:>8.2f}{score_text}")

    table.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    say("")
    say(f"月度总表已写出：{OUT_CSV}（{len(table)} 行）")

    # ---------------- 画趋势图 ----------------
    font = pick_font()
    if font:
        plt.rcParams["font.sans-serif"] = [font]
        plt.rcParams["axes.unicode_minus"] = False
    months = list(table["月份"])
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    panels = [
        (axes[0][0], "GMV", "每月 GMV（销售额）", "#4C78A8"),
        (axes[0][1], "订单数", "每月订单数", "#54A24B"),
        (axes[1][0], "客单价", "每月客单价（每笔多少钱）", "#F58518"),
        (axes[1][1], "平均评分", "每月平均评分（1-5 分）", "#E45756"),
    ]
    for ax, column, title, color in panels:
        ax.plot(months, table[column], marker="o", color=color, linewidth=2, markersize=4)
        ax.set_title(title, fontsize=12)
        ax.grid(linestyle="--", alpha=0.4)
        ax.tick_params(axis="x", rotation=90, labelsize=8)
    fig.suptitle("Olist 核心指标月度趋势（2017-01 ~ 2018-08）", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=140)
    say(f"趋势图已写出：{OUT_PNG}")

    # ---------------- 几行拿来就能用的解读 ----------------
    say("")
    say("【直接能用的 4 条结论】")
    say("-" * 72)
    first, last = table.iloc[0], table.iloc[-1]
    say(f"  1. GMV 从 {first['月份']} 的 {first['GMV']:,.0f} 涨到 "
        f"{last['月份']} 的 {last['GMV']:,.0f}，约 {last['GMV'] / first['GMV']:.1f} 倍")
    say(f"  2. 订单数 {first['订单数']:,} → {last['订单数']:,}（{last['订单数'] / first['订单数']:.1f} 倍），"
        f"客单价 {first['客单价']:,.0f} → {last['客单价']:,.0f}"
        f"（{last['客单价'] / first['客单价'] - 1:+.1%}）")
    say("     → 说明增长主要靠「更多订单」，不是「每单花更多钱」")
    peak = table.loc[table["GMV"].idxmax()]
    say(f"  3. GMV 最高的是 {peak['月份']}（{peak['GMV']:,.0f}），"
        f"比前一个月高 {peak['GMV环比%']:.0f}% —— 典型的黑五效应")
    late = table.loc[table["超时率%"].idxmax()]
    worst_score = table.loc[table["平均评分"].idxmin()]
    say(f"  4. 超时率最高 {late['超时率%']:.1f}%（{late['月份']}），"
        f"评分最低 {worst_score['平均评分']:.2f}（{worst_score['月份']}）"
        f" → 履约和体验是下一步要重点挖的方向")

    with open(OUT_TXT, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print(f"\n文字版已保存：{OUT_TXT}")


if __name__ == "__main__":
    main()
