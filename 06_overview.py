# -*- coding: utf-8 -*-
r"""
第 6 步 · 模块 1：整体经营诊断
================================================================

【这一步回答什么问题】
  1. 生意在怎么长？增长是"更多人买"、"买得更频繁"还是"每单花更多"？
  2. 哪个品类在扛业绩？集中在少数品类还是分散？
  3. 生意集中在哪些地区？
  4. 新客和老客各贡献了多少？（判断增长是拉新拉来的还是复购撑起来的）

【为什么要拆这么细】
  老板问"GMV 怎么才能再涨 10%"，只报"GMV 涨了 7 倍"是没有用的。
  拆成 人数 × 人均订单数 × 客单价 之后，才知道该往哪个方向使劲。

【数据源】
  原始文件副本\cleaned\order_master.csv        96,211 行（一行一订单）
  原始文件副本\cleaned\order_items_clean.csv   109,880 行（一行一件商品，含品类）

【产出】
  经营诊断.txt                    结论文档
  图1_月度趋势与新老客贡献.png
  图2_品类帕累托.png
  图3_地域分布.png
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN = os.path.join(HERE, "原始文件副本", "cleaned")
MASTER = os.path.join(CLEAN, "order_master.csv")
ITEMS = os.path.join(CLEAN, "order_items_clean.csv")
OUT_TXT = os.path.join(HERE, "经营诊断.txt")
FIG1 = os.path.join(HERE, "图1_月度趋势与新老客贡献.png")
FIG2 = os.path.join(HERE, "图2_品类帕累托.png")
FIG3 = os.path.join(HERE, "图3_地域分布.png")

lines = []


def say(text=""):
    print(text)
    lines.append(text)


def setup_font():
    for name in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC"]:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return name
        except Exception:  # noqa: BLE001
            continue
    return None


def main():
    setup_font()
    if not (os.path.exists(MASTER) and os.path.exists(ITEMS)):
        print("找不到清洗后的数据，请先双击「运行数据清洗.bat」")
        return

    orders = pd.read_csv(MASTER, encoding="utf-8-sig")
    items = pd.read_csv(ITEMS, encoding="utf-8-sig")
    orders["gmv"] = pd.to_numeric(orders["gmv"])
    items["price"] = pd.to_numeric(items["price"])

    say("=" * 72)
    say("模块 1：整体经营诊断")
    say("=" * 72)
    say(f"订单 {len(orders):,} 笔 | 商品明细 {len(items):,} 行 | "
        f"{orders['order_month'].nunique()} 个月")

    # ============================================================
    # 一、增长拆解：人数 × 人均订单数 × 客单价
    # ============================================================
    say("")
    say("【一】增长是从哪来的？")
    say("-" * 72)

    monthly = orders.groupby("order_month").agg(
        GMV=("gmv", "sum"),
        订单数=("order_id", "count"),
        下单人数=("customer_unique_id", "nunique"),
    )
    monthly["客单价"] = monthly["GMV"] / monthly["订单数"]
    monthly["人均订单数"] = monthly["订单数"] / monthly["下单人数"]
    monthly["GMV"] = monthly["GMV"].round(2)

    first = monthly.iloc[0]
    last = monthly.iloc[-1]
    say(f"  对比第一个月（{monthly.index[0]}）和最后一个月（{monthly.index[-1]}）：")
    say("")
    say(f"  {'':<14}{'首月':>14}{'末月':>14}{'倍数':>10}")
    for label, column in [
        ("GMV", "GMV"),
        ("下单人数", "下单人数"),
        ("人均订单数", "人均订单数"),
        ("客单价", "客单价"),
    ]:
        ratio = last[column] / first[column]
        say(f"  {label:<14}{first[column]:>14,.2f}{last[column]:>14,.2f}{ratio:>9.2f}x")
    say("")
    say("  拆解：GMV = 下单人数 × 人均订单数 × 客单价")
    say(f"        {last['GMV'] / first['GMV']:.2f}x ≈ "
        f"{last['下单人数'] / first['下单人数']:.2f}x × "
        f"{last['人均订单数'] / first['人均订单数']:.2f}x × "
        f"{last['客单价'] / first['客单价']:.2f}x")
    say("")
    say("  → 结论：增长几乎全部来自【新客户变多】，而【每个客户花的钱在减少】。")
    say("     客单价 -11.4%、人均订单数长期在 1.0 附近，说明没有做深单客价值。")
    say("     这是一个典型的『靠拉新驱动、单客价值没有跟上』的增长模式。")

    # ============================================================
    # 二、新客 vs 老客贡献
    # ============================================================
    say("")
    say("【二】新客和老客各贡献了多少 GMV？")
    say("-" * 72)

    first_month = orders.groupby("customer_unique_id")["order_month"].min()
    orders["首次下单月"] = orders["customer_unique_id"].map(first_month)
    orders["客群"] = np.where(
        orders["order_month"] == orders["首次下单月"], "新客", "老客"
    )
    split = (orders.groupby(["order_month", "客群"])["gmv"].sum()
             .unstack(fill_value=0).reindex(columns=["新客", "老客"], fill_value=0))
    split["老客占比%"] = (split["老客"] / split.sum(axis=1) * 100).round(2)

    say(f"  全期：新客贡献 {orders.loc[orders['客群'] == '新客', 'gmv'].sum():,.0f}，"
        f"老客贡献 {orders.loc[orders['客群'] == '老客', 'gmv'].sum():,.0f}")
    say(f"  老客 GMV 占比全期平均只有 {split['老客占比%'].mean():.1f}%"
        f"（首月按定义全是新客，所以是 0%；到末月也只有 "
        f"{split['老客占比%'].iloc[-1]:.1f}%）")
    say("  → 结论：GMV 里老客贡献长期只有几个百分点，生意几乎是『全靠新客』。")
    say("     这也解释了为什么复购率只有 3% —— 老客这块基本没被经营起来。")

    # ============================================================
    # 三、品类结构（帕累托）
    # ============================================================
    say("")
    say("【三】哪些品类在扛业绩？")
    say("-" * 72)

    category = (items.groupby("category_en")
                .agg(GMV=("price", "sum"), 件数=("order_item_id", "count"))
                .sort_values("GMV", ascending=False))
    total_gmv = category["GMV"].sum()
    category["占比%"] = (category["GMV"] / total_gmv * 100).round(2)
    category["累计占比%"] = category["占比%"].cumsum().round(2)

    n80 = int((category["累计占比%"] < 80).sum() + 1)
    say(f"  一共 {len(category)} 个品类，销售收入 {total_gmv:,.0f}")
    say(f"  前 {n80} 个品类（占品类的 {n80 / len(category) * 100:.0f}%）"
        f"贡献了 80% 的销售收入 —— 典型的二八分布")
    say("")
    say(f"  {'排名':<5}{'品类':<32}{'GMV':>12}{'占比%':>8}{'累计%':>8}")
    for index, (name, row) in enumerate(category.head(10).iterrows(), 1):
        say(f"  {index:<5}{name[:30]:<32}{row['GMV']:>12,.0f}"
            f"{row['占比%']:>8.2f}{row['累计占比%']:>8.2f}")
    say("")
    say("  → 结论：品类高度集中，头部几个品类决定整体业绩。")
    say("     运营资源应该优先保证头部品类的库存和履约（这也是需要重点看差评的品类）。")

    # ============================================================
    # 四、地域分布
    # ============================================================
    say("")
    say("【四】生意集中在哪些地区？")
    say("-" * 72)

    state = (orders.groupby("customer_state")
             .agg(GMV=("gmv", "sum"), 订单数=("order_id", "count"),
                  下单人数=("customer_unique_id", "nunique"))
             .sort_values("GMV", ascending=False))
    state["客单价"] = (state["GMV"] / state["订单数"]).round(2)
    state["GMV占比%"] = (state["GMV"] / state["GMV"].sum() * 100).round(2)
    top3 = state["GMV占比%"].head(3).sum()
    top5 = state["GMV占比%"].head(5).sum()

    say(f"  一共 {len(state)} 个州，前 3 个州占 {top3:.1f}% GMV，"
        f"前 5 个州占 {top5:.1f}%")
    say("")
    say(f"  {'州':<6}{'GMV':>13}{'占比%':>9}{'订单数':>9}{'客单价':>9}")
    for name, row in state.head(8).iterrows():
        say(f"  {name:<6}{row['GMV']:>13,.0f}{row['GMV占比%']:>9.2f}"
            f"{int(row['订单数']):>9,}{row['客单价']:>9.2f}")
    say("")
    big = state[state["订单数"] >= 1000].sort_values("客单价")
    say("  订单量较大的州里，客单价的差异（订单数 ≥1000 的州）：")
    say(f"    最低：{big.index[0]} {big['客单价'].iloc[0]:.2f}"
        f"（订单 {int(big['订单数'].iloc[0]):,}）")
    say(f"    最高：{big.index[-1]} {big['客单价'].iloc[-1]:.2f}"
        f"（订单 {int(big['订单数'].iloc[-1]):,}）")
    say("")
    say("  → 结论：生意高度集中在东南部 —— SP 一个州就占 38.4%，"
        "前 3 个州合计 63.4%。")
    say("     而且【规模最大的州客单价反而最低】（SP 125.12，是全期大州里最低的），")
    say("     说明大州的增长靠的是低价高频商品，而不是高价值订单。")
    say("     扩张之前，先把 SP 这个占四成的大盘子做稳、把客单价拉起来更划算。")

    # ============================================================
    # 画图
    # ============================================================
    months = list(monthly.index)

    # 图 1：月度趋势 + 新老客贡献
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    ax = axes[0]
    ax.plot(months, monthly["GMV"], marker="o", color="#4C78A8", linewidth=2, label="GMV")
    ax.set_title("每月 GMV（销售额）", fontsize=13)
    ax.grid(linestyle="--", alpha=0.4)
    ax.tick_params(axis="x", rotation=90, labelsize=8)
    ax2 = ax.twinx()
    ax2.plot(months, monthly["客单价"], marker="s", color="#F58518",
             linewidth=1.5, linestyle="--", label="客单价")
    ax2.set_ylabel("客单价", color="#F58518")
    ax2.tick_params(axis="y", labelcolor="#F58518")

    ax = axes[1]
    ax.bar(months, split["新客"], color="#4C78A8", label="新客")
    ax.bar(months, split["老客"], bottom=split["新客"], color="#F58518", label="老客")
    ax.set_title("每月 GMV 拆解：新客 vs 老客", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.tick_params(axis="x", rotation=90, labelsize=8)
    fig.suptitle("模块 1 · 经营诊断（1）增长趋势与增长来源", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG1, dpi=140)

    # 图 2：品类帕累托
    top = category.head(15)
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(range(len(top)), top["GMV"], color="#4C78A8")
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels(top.index, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("GMV")
    ax.set_title("模块 1 · 经营诊断（2）品类结构：Top 15 品类与累计占比（帕累托）",
                 fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax2 = ax.twinx()
    ax2.plot(range(len(top)), top["累计占比%"], color="#E45756",
             marker="o", linewidth=2)
    ax2.set_ylabel("累计占比 %", color="#E45756")
    ax2.tick_params(axis="y", labelcolor="#E45756")
    ax2.axhline(80, color="#E45756", linestyle=":", alpha=0.7)
    ax2.annotate(
        f"全部 {len(category)} 个品类里，前 {n80} 个贡献 80% GMV",
        xy=(len(top) - 1, 80),
        xytext=(len(top) - 1, 60),
        ha="right",
        color="#E45756",
        fontsize=10,
        bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none", "pad": 2},
        arrowprops={"arrowstyle": "->", "color": "#E45756"},
    )
    fig.tight_layout()
    fig.savefig(FIG2, dpi=140)

    # 图 3：地域分布
    top_state = state.head(10)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars = ax.bar(top_state.index, top_state["GMV"], color="#54A24B")
    ax.set_title("模块 1 · 经营诊断（3）地域分布：GMV 前 10 的州", fontsize=13)
    ax.set_ylabel("GMV")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for bar, (name, row) in zip(bars, top_state.iterrows()):
        ax.annotate(f"{row['GMV占比%']:.1f}%",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG3, dpi=140)

    say("")
    say("【产出文件】")
    for path in [FIG1, FIG2, FIG3]:
        say(f"  {path}")

    with open(OUT_TXT, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print(f"\n结论已保存：{OUT_TXT}")


if __name__ == "__main__":
    main()
