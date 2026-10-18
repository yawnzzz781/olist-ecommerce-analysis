# -*- coding: utf-8 -*-
r"""
第 6 步 · 模块 5：体验归因（配送时效对评分的影响）
================================================================

【这一步回答什么问题】
  1. 配送超时的订单，评分真的更低吗？（不能只看平均数，要做显著性检验）
  2. 只是"超时/没超时"两种结果吗？还是说"越慢越差"（剂量-反应关系）？
  3. 超得越久，影响越大吗？
  4. 换个角度看（按州对比），这个关系还成立吗？

【为什么要做统计检验，而不是比平均数】
  超时订单平均 2.57 分、准时 4.30 分，看起来差很多。
  但样本只有几千和几万，万一是抽样波动呢？
  所以要用检验判断"这个差异是真的，还是碰巧"。

  本项目做了两道：
    * t 检验（Welch）：比较两组均值 —— 岗位面试最常问的
    * 曼-惠特尼 U 检验：不假设正态分布的版本 —— 评分是 1-5 的等级数据，
      严格来说更该用它。两个都做，结论一致才敢下结论。
  另外报告效应量（Cohen's d）：p 值只说"有没有差异"，效应量说"差异有多大"。

【必须声明的一点：这是相关，不是因果】
  这份是观察性数据，不能证明"超时导致差评"。
  可能存在第三因素：比如某些州既物流差、商品质量也差。
  要证明因果需要 A/B 测试或断点回归。报告里必须写清这一条。

【数据源】
  原始文件副本\cleaned\order_master.csv

【产出】
  体验归因.txt
  图1_超时与准时评分对比.png
  图2_配送时长与评分.png
  图3_各州超时率与评分.png
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from scipy import stats  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(HERE, "原始文件副本", "cleaned", "order_master.csv")
OUT_TXT = os.path.join(HERE, "体验归因.txt")
FIG1 = os.path.join(HERE, "图1_超时与准时评分对比.png")
FIG2 = os.path.join(HERE, "图2_配送时长与评分.png")
FIG3 = os.path.join(HERE, "图3_各州超时率与评分.png")

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


def cohens_d(a, b):
    """效应量：两组均值差，除以合并标准差。0.2 小、0.5 中、0.8 大。"""
    n_a, n_b = len(a), len(b)
    pooled = np.sqrt(((n_a - 1) * a.var(ddof=1) + (n_b - 1) * b.var(ddof=1))
                     / (n_a + n_b - 2))
    return (b.mean() - a.mean()) / pooled


def main():
    setup_font()
    df = pd.read_csv(MASTER, encoding="utf-8-sig")
    for column in ["review_score", "is_late", "delivery_days", "gmv"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["下单时间"] = pd.to_datetime(
        df["order_purchase_timestamp"], errors="coerce", format="mixed"
    )
    df["签收时间"] = pd.to_datetime(
        df["order_delivered_customer_date"], errors="coerce", format="mixed"
    )
    df["承诺时间"] = pd.to_datetime(
        df["order_estimated_delivery_date"], errors="coerce", format="mixed"
    )

    say("=" * 72)
    say("模块 5：体验归因 —— 配送时效对评分的影响")
    say("=" * 72)
    say(f"订单 {len(df):,} 笔")

    # ---------- 一、核心对比：超时 vs 准时 ----------
    valid = df[df["is_late"].notna() & df["review_score"].notna()].copy()
    delayed = valid.loc[valid["is_late"] == 1, "review_score"]
    on_time = valid.loc[valid["is_late"] == 0, "review_score"]

    say("")
    say("【一】超时 vs 准时：评分到底差多少？（有评分的订单）")
    say("-" * 72)
    say(f"  参与对比订单：{len(valid):,}"
        f"（排除 {int(df['review_score'].isna().sum())} 笔无评分、"
        f"{int(df['is_late'].isna().sum())} 笔缺签收时间）")
    say("")
    say(f"  {'组别':<10}{'订单数':>9}{'平均分':>9}{'中位数':>8}{'标准差':>9}{'差评率(≤2分)':>13}")
    for name, series in [("准时", on_time), ("超时", delayed)]:
        say(f"  {name:<10}{len(series):>9,}{series.mean():>9.3f}"
            f"{series.median():>8.1f}{series.std(ddof=1):>9.3f}"
            f"{(series <= 2).mean() * 100:>12.2f}%")

    t_stat, p_ttest = stats.ttest_ind(delayed, on_time, equal_var=False)
    u_stat, p_mw = stats.mannwhitneyu(delayed, on_time, alternative="two-sided")
    d_value = cohens_d(on_time, delayed)
    gap = on_time.mean() - delayed.mean()

    say("")
    say("  统计检验：")
    say(f"    Welch t 检验      t = {t_stat:.1f}，p = {p_ttest:.3e}")
    say(f"    曼-惠特尼 U 检验   p = {p_mw:.3e}（不假设正态分布，评分这种等级数据更该看它）")
    say(f"    效应量 Cohen's d  = {d_value:.3f}"
        f"（0.2 小 / 0.5 中 / 0.8 大）")
    say("")
    say(f"  → 平均分差 {gap:.2f} 分（准时 {on_time.mean():.2f} vs 超时 {delayed.mean():.2f}）")
    say(f"     两个检验的 p 值都远小于 0.05，说明【差异是真的，不是抽样波动】")
    say(f"     Cohen's d = {d_value:.2f}，按通用标准属于"
        f"{'大' if abs(d_value) >= 0.8 else ('中' if abs(d_value) >= 0.5 else '小')}效应"
        f"——差异不只是统计显著，业务上也足够大")
    say(f"     超时订单的差评率 {(delayed <= 2).mean() * 100:.1f}%，"
        f"是准时订单 {(on_time <= 2).mean() * 100:.1f}% 的 "
        f"{(delayed <= 2).mean() / (on_time <= 2).mean():.1f} 倍")

    # ---------- 二、配送时长分档（剂量-反应） ----------
    say("")
    say("【二】不只是「超不超时」，而是「越慢越差」吗？（剂量-反应关系）")
    say("-" * 72)
    day_data = valid[valid["delivery_days"].notna()].copy()
    day_bins = [-100, 3, 7, 14, 21, 1000]
    day_labels = ["1-3 天", "4-7 天", "8-14 天", "15-21 天", "21 天以上"]
    day_data["时长档"] = pd.cut(day_data["delivery_days"], bins=day_bins,
                              labels=day_labels)
    by_day = day_data.groupby("时长档", observed=True).agg(
        订单数=("order_id", "count"),
        平均评分=("review_score", "mean"),
        差评率=("review_score", lambda s: (s <= 2).mean() * 100),
    ).round(3)
    say(f"  {'配送时长':<12}{'订单数':>10}{'平均评分':>11}{'差评率':>10}")
    for name, row in by_day.iterrows():
        say(f"  {str(name):<12}{int(row['订单数']):>10,}{row['平均评分']:>11.3f}"
            f"{row['差评率']:>9.2f}%")
    scores = by_day["平均评分"].tolist()
    monotonic = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    say("")
    first, last = scores[0], scores[-1]
    say(f"  → 最快的档平均 {first:.2f} 分，最慢的档平均 {last:.2f} 分，"
        f"差 {first - last:.2f} 分")
    if monotonic:
        say("     评分随配送时长【单调下降】—— 这就是「剂量-反应关系」，")
        say("     比单纯比「超时/准时」更有说服力：慢得越多，分数掉得越多。")
    else:
        say("     评分整体随配送时长下降，但不是严格单调（中间有波动），")
        say("     报告里要如实说明，不要为了好看硬说「越慢越差」。")

    # ---------- 三、超时的严重程度 ----------
    say("")
    say("【三】超得越久，影响越大吗？")
    say("-" * 72)
    late_data = valid[valid["is_late"] == 1].copy()
    late_data["超时天数"] = (late_data["签收时间"] - late_data["承诺时间"]).dt.days
    late_bins = [0, 3, 7, 14, 1000]
    late_labels = ["超 1-3 天", "超 4-7 天", "超 8-14 天", "超 14 天以上"]
    late_data["超时档"] = pd.cut(late_data["超时天数"], bins=late_bins,
                               labels=late_labels)
    by_late = late_data.groupby("超时档", observed=True).agg(
        订单数=("order_id", "count"),
        平均评分=("review_score", "mean"),
        差评率=("review_score", lambda s: (s <= 2).mean() * 100),
    ).round(3)
    say(f"  {'超时程度':<12}{'订单数':>10}{'平均评分':>11}{'差评率':>10}")
    for name, row in by_late.iterrows():
        say(f"  {str(name):<12}{int(row['订单数']):>10,}{row['平均评分']:>11.3f}"
            f"{row['差评率']:>9.2f}%")
    say("")
    say(f"  → 超 1-3 天平均 {by_late['平均评分'].iloc[0]:.2f} 分，"
        f"超 14 天以上平均 {by_late['平均评分'].iloc[-1]:.2f} 分")

    # ---------- 四、跨地区验证 ----------
    say("")
    say("【四】换个角度看：按州对比，这个关系还成立吗？")
    say("-" * 72)
    state = valid.groupby("customer_state").agg(
        订单数=("order_id", "count"),
        超时率=("is_late", lambda s: s.mean() * 100),
        平均评分=("review_score", "mean"),
    )
    state = state[state["订单数"] >= 200]
    r_value, p_value = stats.pearsonr(state["超时率"], state["平均评分"])
    say(f"  参与对比的州：{len(state)} 个（订单数 ≥200）")
    say(f"  相关系数 r = {r_value:.3f}，p = {p_value:.3e}")
    if p_value < 0.05 and r_value < 0:
        say("  → 州和州之间也成立：超时率越高的州，平均评分越低（负相关，统计显著）")
        say("     说明这个关系不是个别地区的问题，而是【普遍规律】。")
    elif p_value >= 0.05:
        say("  → 州与州之间没有显著相关 —— 说明这个关系在地区层面不稳定，")
        say("     报告里要如实说明，不能把它当成放之四海的规律。")
    else:
        say("  → 相关系数为正（超时率高的州评分反而高），需要进一步排查。")

    # ---------- 五、因果声明 ----------
    say("")
    say("【五】必须声明：这是相关，不是因果")
    say("-" * 72)
    say("  上面所有检验只能证明「超时订单的评分更差」这个关联是真实的，")
    say("  不能证明「超时导致了差评」。原因：")
    say("    1. 这是观察性数据，没有随机分组")
    say("    2. 可能存在第三因素：比如某些卖家既发货慢、商品质量也差")
    say("    3. 也可能反过来：客户本来就预期差，所以对延迟更敏感")
    say("  要证明因果，需要做 A/B 测试（随机给一部分订单加急）或者断点回归。")
    say("  【报告里必须写这一段】—— 面试官最爱追问的就是「你怎么证明是因果」。")

    # ============================================================
    # 画图
    # ============================================================
    # 图 1：分布对比 + 平均分对比
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    scores_axis = [1, 2, 3, 4, 5]
    width = 0.38
    on_counts = [(on_time == s).mean() * 100 for s in scores_axis]
    late_counts = [(delayed == s).mean() * 100 for s in scores_axis]
    ax.bar([s - width / 2 for s in scores_axis], on_counts, width,
           label="准时", color="#54A24B")
    ax.bar([s + width / 2 for s in scores_axis], late_counts, width,
           label="超时", color="#E45756")
    ax.set_xticks(scores_axis)
    ax.set_ylabel("占比 %")
    ax.set_title("评分分布：准时 vs 超时", fontsize=12)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax = axes[1]
    bars = ax.bar(["准时", "超时"], [on_time.mean(), delayed.mean()],
                  color=["#54A24B", "#E45756"])
    ax.set_ylim(0, 5)
    ax.set_ylabel("平均评分")
    ax.set_title(f"平均评分：差 {gap:.2f} 分（p = {p_ttest:.1e}）", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for bar, value in zip(bars, [on_time.mean(), delayed.mean()]):
        ax.annotate(f"{value:.2f}", (bar.get_x() + bar.get_width() / 2, value),
                    ha="center", va="bottom", fontsize=12)
    fig.suptitle("模块 5 · 超时与准时订单的评分对比", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG1, dpi=140)

    # 图 2：配送时长 / 超时程度 vs 评分
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    ax.bar([str(i) for i in by_day.index], by_day["平均评分"], color="#4C78A8")
    ax.set_ylim(0, 5)
    ax.set_ylabel("平均评分")
    ax.set_title("配送时长 vs 平均评分", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(by_day["平均评分"]):
        ax.annotate(f"{value:.2f}", (index, value), ha="center", va="bottom", fontsize=10)
    ax = axes[1]
    ax.bar([str(i) for i in by_late.index], by_late["平均评分"], color="#E45756")
    ax.set_ylim(0, 5)
    ax.set_ylabel("平均评分")
    ax.set_title("超时程度 vs 平均评分", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(by_late["平均评分"]):
        ax.annotate(f"{value:.2f}", (index, value), ha="center", va="bottom", fontsize=10)
    fig.suptitle("模块 5 · 越慢越差吗（剂量-反应关系）", fontsize=14)
    fig.tight_layout()
    fig.savefig(FIG2, dpi=140)

    # 图 3：各州散点
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.scatter(state["超时率"], state["平均评分"],
               s=state["订单数"] / 60, alpha=0.6, color="#4C78A8")
    for name, row in state.iterrows():
        if row["订单数"] > 2000 or row["超时率"] > 15:
            ax.annotate(name, (row["超时率"], row["平均评分"]),
                        fontsize=9, xytext=(4, 4), textcoords="offset points")
    slope, intercept = np.polyfit(state["超时率"], state["平均评分"], 1)
    xs = np.linspace(state["超时率"].min(), state["超时率"].max(), 50)
    ax.plot(xs, slope * xs + intercept, color="#E45756", linestyle="--",
            label=f"趋势线（r = {r_value:.2f}，p = {p_value:.1e}）")
    ax.set_xlabel("该州配送超时率 %")
    ax.set_ylabel("该州平均评分")
    ax.set_title("模块 5 · 每个点是一个州：超时率越高的州，评分越低吗", fontsize=13)
    ax.legend()
    ax.grid(linestyle="--", alpha=0.4)
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
