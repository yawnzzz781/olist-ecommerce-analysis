# -*- coding: utf-8 -*-
r"""
第 6 步 · 模块 4：同期群留存分析
================================================================

【什么是同期群（Cohort）】
把"第一个月来的人"分成一群，然后盯着这一群人在之后每个月还剩多少人回来买。
这样能回答一个普通趋势图回答不了的问题：
   新客的质量有没有随着规模扩张而变差？

【这份数据的特殊之处（必须提前预判）】
整体复购率只有 3%，所以标准的留存矩阵会几乎全是 0，热力图看不出东西。
应对办法有两个，缺一不可：
  1. 热力图照做，但要老实说明"整体留存极低"这个本身就是最重要的结论；
  2. 用【固定观察窗口】做分组对比 —— 只看"首单后 90 天内是否复购"，
     并且只统计首单距离数据截止日还有 90 天以上的用户，保证每个人被观察的时间一样长。

【这一步回答什么问题】
  1. 用户首购之后，还会不会回来？次月留存到底是多少？
  2. 不同月份来的用户群，留存有差别吗？
  3. 首单体验（配送有没有超时、评分高低）和"会不会再来"有关系吗？
     —— 这一问是本次分析最有价值的，它把履约、体验、留存串成了一条线。

【数据源】
  原始文件副本\cleaned\order_master.csv（96,211 行，含 is_late / review_score）

【产出】
  留存分析.txt
  同期群留存矩阵.csv
  图1_同期群留存热力图.png
  图2_留存曲线.png
  图3_首单体验与90天复购率.png
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from scipy.stats import chi2_contingency  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(HERE, "原始文件副本", "cleaned", "order_master.csv")
OUT_TXT = os.path.join(HERE, "留存分析.txt")
OUT_CSV = os.path.join(HERE, "同期群留存矩阵.csv")
FIG1 = os.path.join(HERE, "图1_同期群留存热力图.png")
FIG2 = os.path.join(HERE, "图2_留存曲线.png")
FIG3 = os.path.join(HERE, "图3_首单体验与90天复购率.png")

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
    orders = pd.read_csv(MASTER, encoding="utf-8-sig")
    orders["gmv"] = pd.to_numeric(orders["gmv"])
    orders["review_score"] = pd.to_numeric(orders["review_score"])
    orders["ts"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce", format="mixed"
    )
    data_end = orders["ts"].max()

    say("=" * 72)
    say("模块 4：同期群留存分析")
    say("=" * 72)
    say(f"订单 {len(orders):,} 笔 | 用户 {orders['customer_unique_id'].nunique():,} 人 | "
        f"数据截止 {data_end.date()}")

    # ============================================================
    # 一、同期群留存矩阵
    # ============================================================
    first = orders.groupby("customer_unique_id").agg(
        cohort=("order_month", "min"), first_ts=("ts", "min")
    )
    orders = orders.merge(first, on="customer_unique_id", how="left")
    # 月份差 = (年差 × 12 + 月差)。不用 PeriodIndex 相减：
    # pandas 3.0 里两个 PeriodIndex 相减返回的对象变了，不再能 .apply。
    cohort_period = pd.PeriodIndex(orders["cohort"], freq="M")
    order_period = pd.PeriodIndex(orders["order_month"], freq="M")
    orders["period"] = (
        (order_period.year - cohort_period.year) * 12
        + (order_period.month - cohort_period.month)
    )

    cohort_size = first["cohort"].value_counts().sort_index()
    matrix = (orders.groupby(["cohort", "period"])["customer_unique_id"]
              .nunique().unstack(fill_value=0))
    rate = (matrix.div(cohort_size, axis=0) * 100).round(2)

    say("")
    say("【一】同期群留存矩阵（每行是「哪个月第一次来的人」，列是第几个月）")
    say("-" * 72)
    say("  单位：该群当月还有多少人回来购买（%）")
    say("")
    show = rate.iloc[:, :7]
    header = "  " + "首购月".ljust(10) + "群大小".rjust(8) + "".join(
        f"第{c}月".rjust(8) for c in show.columns
    )
    say(header)
    for cohort, row in show.iterrows():
        cells = ""
        for column in show.columns:
            value = row.get(column)
            cells += ("     -" if pd.isna(value) else f"{value:>7.2f}").rjust(8)
        say(f"  {cohort:<10}{cohort_size[cohort]:>8,}{cells}")

    month1 = rate[1].dropna() if 1 in rate.columns else pd.Series(dtype=float)
    say("")
    say(f"  → 次月留存率：平均 {month1.mean():.2f}%"
        f"（最低 {month1.min():.2f}%，最高 {month1.max():.2f}%）")
    say(f"  → 全期 90 天内的复购率见下一节")
    say("")
    say(f"  ⚠️ 最重要的结论：**次月留存率平均只有 {month1.mean():.2f}%，"
        f"最好的一个月也只有 {month1.max():.2f}%** —— 几乎没有『复购引擎』。")
    say("     这不是某个月的问题，是这门生意的结构性问题——"
        "买过一次的人基本不会主动回来。")

    rate.to_csv(OUT_CSV, encoding="utf-8-sig")

    # ============================================================
    # 二、固定观察窗口：首单后 90 天内是否复购
    # ============================================================
    say("")
    say("【二】用固定窗口对比（首单后 90 天内是否复购）")
    say("-" * 72)
    say("  为什么要固定窗口：后面月份来的用户「还没被观察够时间」，"
        "直接比复购率会得出错误结论。")
    cutoff = data_end - pd.Timedelta(days=90)
    first_orders = orders.loc[orders.groupby("customer_unique_id")["ts"].idxmin()].copy()
    eligible = first_orders[first_orders["ts"] <= cutoff].copy()
    say(f"  数据截止日前 90 天以上首购的用户：{len(eligible):,} 人"
        f"（占全部用户 {len(eligible) / len(first_orders) * 100:.1f}%）")

    window = orders[orders["customer_unique_id"].isin(eligible["customer_unique_id"])].copy()
    # 注意：orders 里已经有一个叫 first_ts 的列（第一段算同期群时加的）。
    # 直接 merge 同名列会被 pandas 自动加 _x / _y 后缀，后面就取不到了。
    # 所以改用 map 取首单时间，彻底避开列名冲突。
    first_ts_map = eligible.set_index("customer_unique_id")["ts"]
    window["观察起点"] = window["customer_unique_id"].map(first_ts_map)
    window["days"] = (window["ts"] - window["观察起点"]).dt.days
    repeat_users = set(window.loc[
        (window["days"] > 0) & (window["days"] <= 90), "customer_unique_id"
    ])
    eligible["90天复购"] = eligible["customer_unique_id"].isin(repeat_users)
    base = eligible["90天复购"].mean() * 100
    say(f"  基准：90 天内复购率 = {base:.2f}%")

    # 按首单是否超时分组
    late_group = eligible[eligible["is_late"].notna()].copy()
    late_group["首单配送"] = np.where(late_group["is_late"] == 1, "首单超时", "首单准时")
    by_late = late_group.groupby("首单配送").agg(
        人数=("customer_unique_id", "count"),
        复购率=("90天复购", lambda s: s.mean() * 100),
    )
    say("")
    say(f"  {'首单配送':<12}{'人数':>10}{'90天复购率':>12}")
    for name, row in by_late.iterrows():
        say(f"  {name:<12}{int(row['人数']):>10,}{row['复购率']:>11.2f}%")

    # 按首单评分分组
    score_group = eligible[eligible["review_score"].notna()].copy()
    score_group["首单评分"] = pd.cut(
        score_group["review_score"], bins=[0, 2, 3, 5],
        labels=["差评(1-2分)", "中评(3分)", "好评(4-5分)"],
    )
    by_score = score_group.groupby("首单评分", observed=True).agg(
        人数=("customer_unique_id", "count"),
        复购率=("90天复购", lambda s: s.mean() * 100),
    )
    say("")
    say(f"  {'首单评分':<14}{'人数':>10}{'90天复购率':>12}")
    for name, row in by_score.iterrows():
        say(f"  {str(name):<14}{int(row['人数']):>10,}{row['复购率']:>11.2f}%")

    # ============================================================
    # 结论：用卡方检验判断差异"是不是真的"，再看相对幅度
    # ------------------------------------------------------------
    # 为什么不用"差几个百分点"当标准：样本有 7 万多人，
    # 哪怕只差 0.2 个百分点也可能是统计上显著的。
    # 所以先做显著性检验（看 p 值），再看相对差有多大（看业务意义）。
    # ============================================================
    def compare(frame, group_col, name_a, name_b):
        """比较两组复购率，返回 (a 的复购率, b 的复购率, p 值, 相对差%)"""
        stat = frame.groupby(group_col, observed=True)["90天复购"].agg(
            人数="count", 复购率=lambda s: s.mean() * 100
        )
        table = pd.crosstab(frame[group_col], frame["90天复购"])
        p_value = float(chi2_contingency(table)[1])
        rate_a = float(stat.loc[name_a, "复购率"])
        rate_b = float(stat.loc[name_b, "复购率"])
        relative = (rate_a - rate_b) / rate_b * 100
        return rate_a, rate_b, p_value, relative

    def verdict(p_value, relative, subject):
        """把 p 值和相对差翻译成人话。"""
        if p_value >= 0.05:
            return f"【{subject}：差异不显著】可能是随机波动，不能下结论"
        if abs(relative) < 15:
            return (f"【{subject}：统计上显著，但幅度不大"
                    f"（相对差 {abs(relative):.0f}%）】")
        if relative > 0:
            return f"【{subject}：差异明显，相对差 {abs(relative):.0f}%】"
        return f"【{subject}：方向相反，需要排查原因】"

    say("")
    rate_a, rate_b, p_value, relative = compare(
        late_group, "首单配送", "首单准时", "首单超时"
    )
    say(f"  → 首单准时 {rate_a:.2f}% vs 首单超时 {rate_b:.2f}%"
        f"（差 {rate_a - rate_b:.2f} 个百分点，相对差 {relative:.0f}%），"
        f"卡方检验 p = {p_value:.2e}")
    say("     " + verdict(p_value, relative, "首单是否超时"))
    say("     业务含义：如果差异明显，说明履约不只是体验问题，它直接影响留存。")

    say("")
    rate_a, rate_b, p_value, relative = compare(
        score_group, "首单评分", "好评(4-5分)", "差评(1-2分)"
    )
    say(f"  → 首单好评 {rate_a:.2f}% vs 首单差评 {rate_b:.2f}%"
        f"（差 {rate_a - rate_b:.2f} 个百分点，相对差 {relative:.0f}%），"
        f"卡方检验 p = {p_value:.2e}")
    say("     " + verdict(p_value, relative, "首单评分高低"))
    say("     业务含义：如果差异明显，说明差评不只是「少了一个好评」，"
        "而是「永久失去一个客户」。")

    # ============================================================
    # 画图
    # ============================================================
    # 图 1：留存热力图
    display = rate.iloc[:, :13]
    fig, ax = plt.subplots(figsize=(13, 8))
    data = display.values.astype(float)
    masked = np.ma.masked_invalid(data)
    im = ax.imshow(masked, cmap="YlGnBu", aspect="auto", vmin=0,
                   vmax=max(2.0, np.nanmax(data)))
    ax.set_xticks(range(display.shape[1]))
    ax.set_xticklabels([f"第{c}月" for c in display.columns], fontsize=9)
    ax.set_yticks(range(display.shape[0]))
    ax.set_yticklabels([f"{c}（{cohort_size[c]:,}人）" for c in display.index], fontsize=8)
    ax.set_title("模块 4 · 同期群留存热力图（每行是首购月份，数值是当月还有多少人回来买）\n"
                 "颜色越深留存越高；空白＝那个月还没到或数据不够",
                 fontsize=12)
    for i in range(display.shape[0]):
        for j in range(display.shape[1]):
            value = data[i, j]
            if not np.isnan(value):
                ax.text(j, i, f"{value:.1f}", ha="center", va="center", fontsize=7,
                        color="white" if value > np.nanmax(data) * 0.6 else "#333333")
    fig.colorbar(im, ax=ax, label="留存率 %")
    fig.tight_layout()
    fig.savefig(FIG1, dpi=140)

    # 图 2：留存曲线
    fig, ax = plt.subplots(figsize=(12, 6))
    periods = [c for c in rate.columns if c <= 6]
    for cohort in rate.index:
        row = rate.loc[cohort]
        values = [row.get(p) for p in periods]
        if all(pd.isna(v) for v in values):
            continue
        ax.plot(periods, values, marker="o", markersize=3, linewidth=1, alpha=0.75,
                label=str(cohort))
    ax.set_xlabel("首购后第几个月")
    ax.set_ylabel("留存率 %")
    ax.set_title("模块 4 · 各同期群的留存曲线（0-6 月）", fontsize=13)
    ax.grid(linestyle="--", alpha=0.4)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG2, dpi=140)

    # 图 3：首单体验 vs 90 天复购率
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    ax = axes[0]
    ax.bar(by_late.index, by_late["复购率"], color=["#54A24B", "#E45756"][: len(by_late)])
    ax.set_title("首单配送 vs 90 天复购率", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(by_late["复购率"]):
        ax.annotate(f"{value:.2f}%", (index, value), ha="center", va="bottom", fontsize=11)
    ax = axes[1]
    ax.bar([str(i) for i in by_score.index], by_score["复购率"],
           color=["#E45756", "#F58518", "#54A24B"][: len(by_score)])
    ax.set_title("首单评分 vs 90 天复购率", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(by_score["复购率"]):
        ax.annotate(f"{value:.2f}%", (index, value), ha="center", va="bottom", fontsize=11)
    fig.suptitle("模块 4 · 首单体验和「会不会再来」有关系吗", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG3, dpi=140)

    say("")
    say("【产出文件】")
    for path in [OUT_CSV, FIG1, FIG2, FIG3]:
        say(f"  {path}")

    with open(OUT_TXT, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print(f"\n结论已保存：{OUT_TXT}")


if __name__ == "__main__":
    main()
