# -*- coding: utf-8 -*-
r"""
第 6 步 · 模块 3：用户价值分层（RFM 适配版）
================================================================

【先说清一个必须处理的问题】
经典 RFM 用三个维度给用户打分：
   R = 最近一次购买距今多久      F = 买了多少次      M = 一共花了多少钱

但这份数据的 F 几乎没有区分度：93,104 个用户里 97% 只买过 1 次，
平均每人 1.03 单。硬套标准 RFM，所有人的 F 都是 1，分群就是假的。

所以这里用适配版本：
   * 主维度用 R（新近度）× M（金额）——这两个维度真实有区分度
   * F 作为独立的「是否复购」标记，单独看这 3% 的人
   报告里要如实写"为什么改了算法"，这比硬套公式专业得多。

【这一步回答什么问题】
  1. 9.3 万用户能分出几类？每类多少人、贡献多少钱？
  2. 少数高价值用户是不是贡献了大部分 GMV？
  3. 复购用户（3%）到底贡献了多少？
  4. 首单花得多的人，是不是更容易再买一次？（能指导拉新策略）

【数据源】
  原始文件副本\cleaned\order_master.csv（96,211 行，一行一订单）

【产出】
  用户分群诊断.txt
  用户分群表.csv        每个用户一行：R/F/M + 分群标签（可导入 Power BI）
  图1_用户分层结果.png
  图2_复购用户贡献.png
  图3_首单金额与复购率.png
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
MASTER = os.path.join(HERE, "原始文件副本", "cleaned", "order_master.csv")
OUT_TXT = os.path.join(HERE, "用户分群诊断.txt")
OUT_CSV = os.path.join(HERE, "用户分群表.csv")
FIG1 = os.path.join(HERE, "图1_用户分层结果.png")
FIG2 = os.path.join(HERE, "图2_复购用户贡献.png")
FIG3 = os.path.join(HERE, "图3_首单金额与复购率.png")

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
    orders["ts"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce", format="mixed"
    )

    # 参照日：数据里最后一笔订单的第二天（算"距今多久"用）
    ref_date = orders["ts"].max() + pd.Timedelta(days=1)

    say("=" * 72)
    say("模块 3：用户价值分层（RFM 适配版）")
    say("=" * 72)
    say(f"订单 {len(orders):,} 笔 | 参照日 {ref_date.date()}（数据里最后一笔订单的次日）")

    # ---------- 用户级汇总 ----------
    user = orders.groupby("customer_unique_id").agg(
        R=("ts", lambda s: int((ref_date - s.max()).days)),
        F=("order_id", "count"),
        M=("gmv", "sum"),
        首单月份=("order_month", "min"),
    ).reset_index()

    say("")
    say("【零】先看 F 维度到底有没有用")
    say("-" * 72)
    f_dist = user["F"].value_counts().sort_index()
    say(f"  {'购买次数':<10}{'人数':>12}{'占比':>10}")
    for times, people in f_dist.head(6).items():
        say(f"  {times:<10}{people:>12,}{people / len(user) * 100:>9.2f}%")
    repeat = user[user["F"] >= 2]
    say("")
    say(f"  → {len(repeat):,} 人买过 2 次以上，只占 {len(repeat) / len(user) * 100:.2f}%")
    say("     所以 F 没有区分度，下面用 R（新近度）× M（金额）做主分层。")

    # ---------- R × M 分层 ----------
    r_median = user["R"].median()
    m_median = user["M"].median()

    def label(row):
        recent = row["R"] <= r_median
        high = row["M"] >= m_median
        if recent and high:
            return "核心价值客户"
        if not recent and high:
            return "流失预警客户"
        if recent and not high:
            return "潜力培养客户"
        return "低价值流失客户"

    user["人群"] = user.apply(label, axis=1)
    user["是否复购"] = np.where(user["F"] >= 2, "复购用户", "一次性用户")

    say("")
    say("【一】用户分群结果（R 按中位数 {:.0f} 天、M 按中位数 {:.1f} 元切分）".format(
        r_median, m_median))
    say("-" * 72)

    group = (user.groupby("人群")
             .agg(人数=("customer_unique_id", "count"),
                  总消费=("M", "sum"),
                  客单价=("M", "mean"),
                  平均订单数=("F", "mean"),
                  平均R=("R", "mean"))
             .sort_values("总消费", ascending=False))
    group["人数占比%"] = (group["人数"] / len(user) * 100).round(2)
    group["GMV占比%"] = (group["总消费"] / user["M"].sum() * 100).round(2)
    group["复购率%"] = [
        (user[user["人群"] == name]["F"] >= 2).mean() * 100 for name in group.index
    ]

    say(f"  {'人群':<18}{'人数':>9}{'人数占比':>9}{'GMV占比':>9}"
        f"{'平均消费':>10}{'复购率':>8}")
    for name, row in group.iterrows():
        say(f"  {name:<18}{int(row['人数']):>9,}{row['人数占比%']:>8.2f}%"
            f"{row['GMV占比%']:>8.2f}%{row['客单价']:>10,.1f}"
            f"{row['复购率%']:>7.2f}%")
    say("")
    top2 = group.head(2)
    say(f"  → 前两类人群（{top2['人数占比%'].sum():.1f}% 的用户）"
        f"贡献了 {top2['GMV占比%'].sum():.1f}% 的 GMV")
    say(f"     「{group.index[0]}」平均每人消费 {group['客单价'].iloc[0]:,.0f} 元，"
        f"是「{group.index[-1]}」的 {group['客单价'].iloc[0] / group['客单价'].iloc[-1]:.1f} 倍")

    # ---------- 复购用户的贡献 ----------
    say("")
    say("【二】复购用户（3%）到底贡献了多少？")
    say("-" * 72)
    split = (user.groupby("是否复购")
             .agg(人数=("customer_unique_id", "count"), GMV=("M", "sum")))
    split["人数占比%"] = (split["人数"] / len(user) * 100).round(2)
    split["GMV占比%"] = (split["GMV"] / user["M"].sum() * 100).round(2)
    split["人均消费"] = (split["GMV"] / split["人数"]).round(0)
    for name in ["一次性用户", "复购用户"]:
        if name in split.index:
            row = split.loc[name]
            say(f"  {name:<10}{int(row['人数']):>9,} 人（{row['人数占比%']:>5.2f}%）"
                f"   GMV {row['GMV']:>13,.0f}（{row['GMV占比%']:>5.2f}%）"
                f"   人均 {row['人均消费']:>8,.0f}")
    ratio_repeat = (split.loc["复购用户", "人均消费"]
                    / split.loc["一次性用户", "人均消费"])
    say("")
    say(f"  → 复购用户只占 {split.loc['复购用户', '人数占比%']:.2f}% 的人数，"
        f"GMV 贡献 {split.loc['复购用户', 'GMV占比%']:.2f}%，"
        f"人均消费是一次性用户的 {ratio_repeat:.2f} 倍。")
    say("     虽然比例不高，但复购用户的人均价值明显更高 —— "
        "把一次性买家转成二次买家，是这门生意最直接的杠杆。")

    # ---------- 首单金额与复购率 ----------
    say("")
    say("【三】首单花得多的人，更容易再买一次吗？")
    say("-" * 72)
    first_order = orders.loc[orders.groupby("customer_unique_id")["ts"].idxmin()]
    first_amount = first_order.set_index("customer_unique_id")["gmv"]
    user["首单金额"] = user["customer_unique_id"].map(first_amount)
    user["首单档"] = pd.qcut(user["首单金额"], 5,
                             labels=["最低 20%", "偏低 20%", "中等 20%",
                                     "偏高 20%", "最高 20%"])
    first_stat = (user.groupby("首单档", observed=True)
                  .agg(人数=("customer_unique_id", "count"),
                       复购率=("F", lambda s: (s >= 2).mean() * 100),
                       人均消费=("M", "mean")))
    say(f"  {'首单金额档':<12}{'人数':>10}{'复购率':>10}{'人均总消费':>12}")
    for name, row in first_stat.iterrows():
        say(f"  {str(name):<12}{int(row['人数']):>10,}{row['复购率']:>9.2f}%"
            f"{row['人均消费']:>12,.1f}")
    rates = first_stat["复购率"]
    spread = rates.max() - rates.min()
    say("")
    # 结论由数据决定，不预先写死
    if spread < 1.0:
        say(f"  → 各档复购率都在 {rates.min():.2f}% ~ {rates.max():.2f}% 之间，"
            f"最大差距只有 {spread:.2f} 个百分点。")
        say("     【首单金额和复购率没有明显关系】—— 首单花得多的人并不会更容易回来。")
        say("     这是一个「否定结论」，但同样有价值：")
        say("     它说明不能用首单金额去筛选『高潜力用户』，也就省掉了这笔冤枉钱。")
        say("     报告里要如实写否定结论，不要硬编一个故事。")
    elif rates.iloc[-1] > rates.iloc[0]:
        say(f"  → 首单最高 20% 的人复购率 {rates.iloc[-1]:.2f}%，"
            f"是最低 20%（{rates.iloc[0]:.2f}%）的 {rates.iloc[-1] / rates.iloc[0]:.1f} 倍。")
        say("     【首单金额越高，越可能回来】。")
        say("     业务含义：与其用大额优惠券拉一堆低质新客，"
            "不如用『首单满额礼』筛选出有消费能力的用户。")
    else:
        say(f"  → 首单最高 20% 的人复购率反而更低（{rates.iloc[-1]:.2f}% vs "
            f"{rates.iloc[0]:.2f}%）。")
        say("     【高客单价首单的人是『买完就走』型】—— 值得单独研究原因。")

    user.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    say("")
    say(f"用户分群表已写出：{OUT_CSV}（{len(user):,} 行 × {user.shape[1]} 列）")

    # ---------- 画图 ----------
    # 图 1：人群的人数占比 vs GMV 占比
    fig, ax = plt.subplots(figsize=(12, 5.5))
    positions = np.arange(len(group))
    width = 0.38
    ax.bar(positions - width / 2, group["人数占比%"], width,
           label="人数占比", color="#4C78A8")
    ax.bar(positions + width / 2, group["GMV占比%"], width,
           label="GMV 占比", color="#F58518")
    ax.set_xticks(positions)
    ax.set_xticklabels(group.index, fontsize=10)
    ax.set_ylabel("%")
    ax.set_title("模块 3 · 用户分层：人数占比 vs GMV 占比", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(group["人数占比%"]):
        ax.annotate(f"{value:.1f}", (index - width / 2, value),
                    ha="center", va="bottom", fontsize=9)
    for index, value in enumerate(group["GMV占比%"]):
        ax.annotate(f"{value:.1f}", (index + width / 2, value),
                    ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG1, dpi=140)

    # 图 2：复购 vs 一次性
    fig, ax = plt.subplots(figsize=(9, 5))
    names = ["一次性用户", "复购用户"]
    people_pct = [split.loc[n, "人数占比%"] for n in names if n in split.index]
    gmv_pct = [split.loc[n, "GMV占比%"] for n in names if n in split.index]
    positions = np.arange(len(names))
    ax.bar(positions - 0.19, people_pct, 0.38, label="人数占比", color="#4C78A8")
    ax.bar(positions + 0.19, gmv_pct, 0.38, label="GMV 占比", color="#54A24B")
    ax.set_xticks(positions)
    ax.set_xticklabels(names)
    ax.set_ylabel("%")
    ax.set_title("模块 3 · 复购用户 vs 一次性用户", fontsize=13)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(people_pct):
        ax.annotate(f"{value:.2f}%", (index - 0.19, value), ha="center",
                    va="bottom", fontsize=9)
    for index, value in enumerate(gmv_pct):
        ax.annotate(f"{value:.2f}%", (index + 0.19, value), ha="center",
                    va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG2, dpi=140)

    # 图 3：首单金额 vs 复购率
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar([str(i) for i in first_stat.index], first_stat["复购率"], color="#E45756")
    ax.set_ylabel("复购率 %")
    ax.set_title("模块 3 · 首单金额越高，越可能再买一次", fontsize=13)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for index, value in enumerate(first_stat["复购率"]):
        ax.annotate(f"{value:.2f}%", (index, value), ha="center", va="bottom", fontsize=10)
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
