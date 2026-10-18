# -*- coding: utf-8 -*-
r"""
按月统计订单量，画出趋势图，用来确认「分析时间窗」。
================================================================

【为什么要做这一步】
这份数据的时间范围是 2016-09 到 2018-10，但两头都有问题：
  开头：2016 年 9-12 月一共只有 329 单（占 0.33%），其中 11 月一笔订单都没有，
        说明平台那时候还没真正开始运营
  结尾：2018 年 9 月只有 16 单、10 月只有 4 单，而且这些订单 100% 还没送达，
        说明数据是被截断的，那不是一个真实的下跌

如果直接拿全量数据算月度趋势或环比同比，开头会出现一个假低谷，
结尾会出现一个假暴跌。所以要先定一个干净的时间窗。

【怎么运行】
  最简单：双击项目里的「运行月度订单量图.bat」
  手动运行：
      "C:\Users\15414\Anaconda3\python.exe" 02_monthly_orders.py

【产出】
  月度订单量.png —— 趋势图
  月度订单量.txt —— 数字表格（证据文件）
  月度订单量.csv —— 同一份数字，方便用 Excel 打开
"""

import os
import sys

import matplotlib

matplotlib.use("Agg")  # 不弹窗，直接存成图片文件

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "原始文件", "olist_orders_dataset.csv")
OUT_PNG = os.path.join(HERE, "月度订单量.png")
OUT_TXT = os.path.join(HERE, "月度订单量.txt")
OUT_CSV = os.path.join(HERE, "月度订单量.csv")

# 定下来的分析时间窗（含头含尾）
WINDOW_START = "2017-01"
WINDOW_END = "2018-08"


def pick_chinese_font():
    """找一个能显示中文的字体；找不到就返回 None（图上改用英文）。"""
    for name in [
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
    ]:
        try:
            font_manager.findfont(name, fallback_to_default=False)
            return name
        except Exception:  # noqa: BLE001
            continue
    return None


def main() -> None:
    lines = []

    def say(text=""):
        print(text)
        lines.append(text)

    df = pd.read_csv(SRC, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df["ts"] = pd.to_datetime(
        df["order_purchase_timestamp"], errors="coerce", format="mixed"
    )
    df["month"] = df["ts"].dt.to_period("M").astype(str)
    df["is_delivered"] = df["order_status"] == "delivered"

    g = df.groupby("month").agg(
        订单数=("order_id", "count"),
        已送达=("is_delivered", "sum"),
        有数据天数=("ts", lambda s: s.dt.day.nunique()),
    )
    g["未送达占比"] = (1 - g["已送达"] / g["订单数"]) * 100

    say("=" * 70)
    say("按月订单量统计")
    say("=" * 70)
    say("下单时间范围：" + str(df["ts"].min()) + " ~ " + str(df["ts"].max()))
    say("订单总数：" + str(len(df)))
    say("")
    say("月份        订单数    已送达   未送达占比   有数据天数")
    for month, row in g.iterrows():
        say(
            "%-9s%8d%8d%10.1f%%%11d"
            % (
                month,
                int(row["订单数"]),
                int(row["已送达"]),
                row["未送达占比"],
                int(row["有数据天数"]),
            )
        )

    inside = g.loc[(g.index >= WINDOW_START) & (g.index <= WINDOW_END)]
    total_inside = int(inside["订单数"].sum())
    say("")
    say("-" * 70)
    say("分析时间窗：" + WINDOW_START + " ~ " + WINDOW_END)
    say(
        "  覆盖 %d 个完整月份，%d 单，占全部订单的 %.2f%%"
        % (len(inside), total_inside, total_inside / len(df) * 100)
    )
    say(
        "  月订单量区间：%d ~ %d 单"
        % (int(inside["订单数"].min()), int(inside["订单数"].max()))
    )
    excluded = int(g["订单数"].sum()) - total_inside
    say(
        "  被排除的时段（2016-09~2016-12、2018-09~2018-10）合计只有 %d 单，占 %.2f%%"
        % (excluded, excluded / len(df) * 100)
    )
    g.to_csv(OUT_CSV, encoding="utf-8-sig")

    # ---------------- 画图 ----------------
    font = pick_chinese_font()
    lang_cn = font is not None
    if lang_cn:
        plt.rcParams["font.sans-serif"] = [font]
        plt.rcParams["axes.unicode_minus"] = False

    months = list(g.index)
    counts = [int(v) for v in g["订单数"]]
    colors = [
        "#4C78A8" if WINDOW_START <= m <= WINDOW_END else "#C9CDD4" for m in months
    ]

    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(range(len(months)), counts, color=colors)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, rotation=90, fontsize=8)
    ax.set_ylabel("订单数" if lang_cn else "Orders")
    if lang_cn:
        ax.set_title("Olist 月度订单量（深色 = 分析时间窗 2017-01 ~ 2018-08）")
    else:
        ax.set_title("Olist monthly orders (dark = window 2017-01 .. 2018-08)")
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    peak = max(counts)
    note_style = {"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 3}
    ax.annotate(
        ("开头：平台还没开始运营，2016-11 一笔订单都没有"
         if lang_cn
         else "start: platform not live yet"),
        xy=(months.index("2016-10"), 324),
        xytext=(months.index("2016-10") + 0.5, peak * 0.62),
        fontsize=9,
        color="#D9534F",
        bbox=note_style,
        arrowprops={"arrowstyle": "->", "color": "#D9534F"},
    )
    ax.annotate(
        ("结尾：数据被截断，订单都还没送达" if lang_cn else "end: truncated data"),
        xy=(len(months) - 1, 16),
        xytext=(len(months) - 10, peak * 0.45),
        fontsize=9,
        color="#D9534F",
        bbox=note_style,
        arrowprops={"arrowstyle": "->", "color": "#D9534F"},
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print("\n图已保存：" + OUT_PNG)
    lines.append("")
    lines.append("图已保存：" + OUT_PNG)

    with open(OUT_TXT, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print("数字已保存：" + OUT_TXT)
    if not lang_cn:
        print("提示：没找到中文字体，图上的标签是英文的。")


if __name__ == "__main__":
    main()
