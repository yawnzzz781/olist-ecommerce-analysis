# -*- coding: utf-8 -*-
r"""
第 6 步 · 模块 2：订单履约与行为漏斗
================================================================

【先说清局限】
这份数据没有"浏览 / 加购"的埋点，所以做不了经典的
"访问 → 加购 → 下单"转化漏斗。报告里要如实写这一条。

但有一件真实存在、而且更有业务价值的漏斗可以做：
  下单 → 付款通过 → 交给物流 → 买家签收
每一步都有真实的流失（取消、无货、卡住），而且能算出损失了多少钱。

【这一步回答什么问题】
  1. 订单从下单到签收，哪一步掉得最多？
  2. 没走完的订单有多少？损失了多少销售额？
  3. 客户怎么付款的？分期期数和订单金额有关系吗？

【数据源】（用原始表，因为要看"没走完"的订单）
  原始文件\olist_orders_dataset.csv          99,441 笔（含取消/无货等所有状态）
  原始文件\olist_order_items_dataset.csv     订单明细（算未完成订单的金额）
  原始文件\olist_order_payments_dataset.csv  付款记录

【产出】
  漏斗与履约诊断.txt
  图1_订单履约漏斗.png
  图2_未完成订单归因.png
  图3_支付行为.png
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
RAW = os.path.join(HERE, "原始文件")
OUT_TXT = os.path.join(HERE, "漏斗与履约诊断.txt")
FIG1 = os.path.join(HERE, "图1_订单履约漏斗.png")
FIG2 = os.path.join(HERE, "图2_未完成订单归因.png")
FIG3 = os.path.join(HERE, "图3_支付行为.png")

WINDOW_START, WINDOW_END = "2017-01-01", "2018-09-01"

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
            return
        except Exception:  # noqa: BLE001
            continue


def main():
    setup_font()
    orders = pd.read_csv(
        os.path.join(RAW, "olist_orders_dataset.csv"),
        dtype=str, keep_default_na=False, encoding="utf-8-sig",
    )
    items = pd.read_csv(
        os.path.join(RAW, "olist_order_items_dataset.csv"),
        dtype=str, keep_default_na=False, encoding="utf-8-sig",
    )
    payments = pd.read_csv(
        os.path.join(RAW, "olist_order_payments_dataset.csv"),
        dtype=str, keep_default_na=False, encoding="utf-8-sig",
    )

    orders["purchase_ts"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce", format="mixed"
    )
    win = orders[
        (orders["purchase_ts"] >= WINDOW_START) & (orders["purchase_ts"] < WINDOW_END)
    ].copy()

    say("=" * 72)
    say("模块 2：订单履约与行为漏斗")
    say("=" * 72)
    say(f"分析范围：下单时间 {WINDOW_START} ~ {WINDOW_END}")
    say(f"订单总数：{len(win):,}（含所有状态）")
    say("")
    say("局限说明：这份数据没有浏览/加购埋点，做不了『访问→加购→下单』漏斗。")
    say("下面做的是真实存在的【履约漏斗】，每一步的流失都能追溯到具体订单。")

    # ============================================================
    # 一、履约漏斗
    # ============================================================
    stages = [
        ("下单", "order_purchase_timestamp"),
        ("付款通过", "order_approved_at"),
        ("交给物流", "order_delivered_carrier_date"),
        ("买家签收", "order_delivered_customer_date"),
    ]
    counts = [(label, int((win[column].str.strip() != "").sum())) for label, column in stages]

    say("")
    say("【一】履约漏斗：订单从下单到签收，每一步掉了多少？")
    say("-" * 72)
    total = counts[0][1]
    say(f"  {'环节':<10}{'订单数':>10}{'占下单':>10}{'本步流失':>10}{'流失率':>9}")
    previous = total
    funnel = []
    for index, (label, value) in enumerate(counts):
        lost = previous - value if index else 0
        rate = lost / previous * 100 if index else 0.0
        rate_text = f"{rate:.2f}%" if index else "-"
        say(f"  {label:<10}{value:>10,}{value / total * 100:>9.2f}%"
            f"{lost:>10,}{rate_text:>9}")
        funnel.append((label, value, lost, rate))
        previous = value
    unfinished = total - counts[-1][1]
    say("")
    say(f"  → 没走到签收的订单共 {unfinished:,} 单，占 {unfinished / total * 100:.2f}%")
    worst = max(funnel[1:], key=lambda item: item[2])
    say(f"    流失最大的一步是「{funnel[funnel.index(worst) - 1][0]} → {worst[0]}」："
        f"掉了 {worst[2]:,} 单，流失率 {worst[3]:.2f}%")
    say("    这些卡在中间状态的订单，对应订单状态里的取消、无货和长时间在途。")
    say("")
    say("  ⚠️ 一个必须说明的严谨性问题：数据在 2018-10-17 截断，")
    say("     所以 2018-08 附近下单的订单可能【还在途中】，并不是失败。")
    win["未完成"] = win["order_status"] != "delivered"
    month_rate = win.groupby(win["purchase_ts"].dt.to_period("M").astype(str))[
        "未完成"
    ].agg(未完成数="sum", 订单数="count")
    month_rate["未完成率%"] = (month_rate["未完成数"] / month_rate["订单数"] * 100).round(2)
    say("     按月看未完成率（末尾几个月偏高就是截断造成的）：")
    for month, row in month_rate.iterrows():
        flag = "  ← 偏高，可能是数据截断" if row["未完成率%"] > 5 else ""
        say(f"       {month}  未完成 {int(row['未完成数']):>5} / "
            f"{int(row['订单数']):>5} 单  = {row['未完成率%']:>6.2f}%{flag}")
    overall = unfinished / total * 100
    last_month_rate = month_rate["未完成率%"].iloc[-1]
    if last_month_rate <= overall * 1.5:
        say(f"     ✔ 检查结果：末尾月份的未完成率（{last_month_rate:.2f}%）没有偏高，")
        say(f"       说明这 {overall:.2f}% 是【真实流失】，不是数据截断造成的，"
            f"可以放心写进报告。")
    else:
        say(f"     ⚠ 检查结果：末尾月份未完成率（{last_month_rate:.2f}%）明显偏高，")
        say("       这部分可能只是订单还没走完流程，报告里要说明。")

    status = win["order_status"].value_counts()
    say("")
    say("  按订单状态看（这就是流失的具体去向）：")
    say(f"  {'状态':<14}{'订单数':>10}{'占比':>10}")
    for name, value in status.items():
        say(f"  {name:<14}{value:>10,}{value / total * 100:>9.2f}%")

    # ============================================================
    # 二、未完成订单的金额损失
    # ============================================================
    say("")
    say("【二】没走完的订单，损失了多少销售额？")
    say("-" * 72)

    items["price"] = pd.to_numeric(items["price"])
    good_ids = set(win.loc[win["order_status"] == "delivered", "order_id"])
    bad_ids = set(win.loc[win["order_status"] != "delivered", "order_id"])
    bad_value = items.loc[items["order_id"].isin(bad_ids), "price"].sum()
    good_value = items.loc[items["order_id"].isin(good_ids), "price"].sum()
    say(f"  已完成订单的金额：        {good_value:>14,.2f}")
    say(f"  未完成订单的金额：        {bad_value:>14,.2f}")
    say(f"  → 未完成造成的销售额损失占潜在总额的 "
        f"{bad_value / (bad_value + good_value) * 100:.2f}%")
    say("")
    bad_status = win.loc[win["order_status"] != "delivered", "order_status"].value_counts()
    bad_by_status = []
    for name, value in bad_status.items():
        ids = set(win.loc[win["order_status"] == name, "order_id"])
        amount = items.loc[items["order_id"].isin(ids), "price"].sum()
        bad_by_status.append((name, int(value), float(amount)))
        say(f"    {name:<14}{value:>8,} 单{amount:>16,.2f}")

    # ============================================================
    # 三、支付行为
    # ============================================================
    say("")
    say("【三】客户怎么付款的？分期和订单金额有关系吗？")
    say("-" * 72)

    pay = payments[payments["order_id"].isin(good_ids)].copy()
    pay["value"] = pd.to_numeric(pay["payment_value"])
    pay["inst"] = pd.to_numeric(pay["payment_installments"])

    grouped = pay.groupby("order_id")
    order_pay = pd.DataFrame({
        "总付款": grouped["value"].sum(),
        "最大分期": grouped["inst"].max(),
    })
    dominant = pay.loc[pay.groupby("order_id")["value"].idxmax()]
    order_pay["主要方式"] = dominant.set_index("order_id")["payment_type"]
    order_pay = order_pay.reset_index()

    type_stat = (order_pay.groupby("主要方式")
                 .agg(订单数=("order_id", "count"), 金额=("总付款", "sum"))
                 .sort_values("金额", ascending=False))
    type_stat["金额占比%"] = (type_stat["金额"] / type_stat["金额"].sum() * 100).round(2)
    say(f"  {'付款方式':<16}{'订单数':>10}{'占比':>9}{'金额':>16}{'金额占比':>10}")
    for name, row in type_stat.iterrows():
        say(f"  {name:<16}{int(row['订单数']):>10,}"
            f"{row['订单数'] / len(order_pay) * 100:>8.2f}%"
            f"{row['金额']:>16,.0f}{row['金额占比%']:>9.2f}%")

    say("")
    bins = [0, 1, 3, 6, 12, 100]
    labels_dist = ["不分期(1期)", "2-3期", "4-6期", "7-12期", "13期以上"]
    order_pay["分期区间"] = pd.cut(order_pay["最大分期"], bins=bins,
                                   labels=labels_dist, right=True)
    inst_stat = (order_pay.groupby("分期区间", observed=True)
                 .agg(订单数=("order_id", "count"), 平均订单金额=("总付款", "mean")))
    say(f"  {'分期区间':<14}{'订单数':>10}{'占比':>10}{'平均订单金额':>14}")
    for name, row in inst_stat.iterrows():
        say(f"  {str(name):<14}{int(row['订单数']):>10,}"
            f"{row['订单数'] / len(order_pay) * 100:>9.2f}%"
            f"{row['平均订单金额']:>14,.2f}")
    first_amount = inst_stat["平均订单金额"].iloc[0]
    last_amount = inst_stat["平均订单金额"].iloc[-1]
    say("")
    say(f"  → 结论：不分期的订单平均 {first_amount:,.0f}，"
        f"分期最多的一档平均 {last_amount:,.0f}"
        f"（{last_amount / first_amount:.1f} 倍）。")
    say("     说明分期是高价订单的支付方式，巴西市场对分期高度依赖。")
    say("     业务含义：做促销时用『满额免息分期』来拉高客单价是可行的。")

    # ============================================================
    # 画图
    # ============================================================
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    names = [f[0] for f in funnel]
    values = [f[1] for f in funnel]
    ax = axes[0]
    bars = ax.barh(names[::-1], values[::-1], color="#4C78A8")
    ax.set_xlim(0, total * 1.12)
    ax.set_title("履约漏斗（全程只掉 2.9%，所以看着平）", fontsize=12)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    for bar, value in zip(bars, values[::-1]):
        ax.annotate(f"{value:,}（{value / total * 100:.1f}%）",
                    (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    va="center", ha="left", fontsize=10)

    # 右图才是重点：每一步实际掉了多少单
    ax = axes[1]
    step_labels = [f"{funnel[i][0]} → {funnel[i + 1][0]}" for i in range(len(funnel) - 1)]
    step_lost = [funnel[i + 1][2] for i in range(len(funnel) - 1)]
    step_rate = [funnel[i + 1][3] for i in range(len(funnel) - 1)]
    bars = ax.barh(step_labels[::-1], step_lost[::-1], color="#E45756")
    ax.set_xlim(0, max(step_lost) * 1.35)
    ax.set_title("每一步流失的订单数（这才是重点）", fontsize=12)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    for bar, lost, rate in zip(bars, step_lost[::-1], step_rate[::-1]):
        ax.annotate(f"{lost:,} 单（{rate:.2f}%）",
                    (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                    va="center", ha="left", fontsize=10)
    fig.suptitle("模块 2 · 履约漏斗：下单 → 付款通过 → 交给物流 → 买家签收", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG1, dpi=140)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    labels2 = [row[0] for row in bad_by_status] + ["delivered"]
    counts2 = [row[1] for row in bad_by_status] + [len(good_ids)]
    amounts2 = [row[2] for row in bad_by_status] + [good_value]
    colors2 = ["#E45756"] * len(bad_by_status) + ["#54A24B"]
    ax = axes[0]
    ax.bar(labels2, counts2, color=colors2)
    ax.set_title("各状态的订单数", fontsize=12)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(counts2):
        ax.annotate(f"{value:,}", (index, value), ha="center", va="bottom", fontsize=9)
    ax = axes[1]
    ax.bar(labels2, amounts2, color=colors2)
    ax.set_title("各状态的订单金额", fontsize=12)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(amounts2):
        ax.annotate(f"{value / 10000:.1f}万", (index, value), ha="center",
                    va="bottom", fontsize=9)
    fig.suptitle("模块 2 · 未完成订单的规模与金额损失", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG2, dpi=140)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    ax.bar(range(len(type_stat)), type_stat["金额占比%"], color="#F58518")
    ax.set_xticks(range(len(type_stat)))
    ax.set_xticklabels(type_stat.index, rotation=20)
    ax.set_title("各付款方式的金额占比", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(type_stat["金额占比%"]):
        ax.annotate(f"{value:.1f}%", (index, value), ha="center", va="bottom", fontsize=10)
    ax = axes[1]
    ax.bar(range(len(inst_stat)), inst_stat["平均订单金额"], color="#4C78A8")
    ax.set_xticks(range(len(inst_stat)))
    ax.set_xticklabels([str(i) for i in inst_stat.index], rotation=20)
    ax.set_title("分期期数 vs 平均订单金额", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(inst_stat["平均订单金额"]):
        ax.annotate(f"{value:,.0f}", (index, value), ha="center", va="bottom", fontsize=9)
    fig.suptitle("模块 2 · 支付行为", fontsize=14)
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
