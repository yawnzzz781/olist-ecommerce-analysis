# -*- coding: utf-8 -*-
r"""
第 7 步（准备工作）：把数据整理成 Power BI 直接能连的格式
================================================================

【为什么要单独准备一份】
给 Power BI 用的数据要满足几个条件，原始的分析输出不完全符合：
  1. 列名用中文 —— 拖到图表里一眼就懂，不用对照英文猜
  2. 分类字段要预先分好档（"超时/准时"而不是 1/0），
     这样直接拖到图例里就能用，不用写公式
  3. 州级表要带经纬度，否则地图视觉对象认不出来
  4. 日期要单独一列（只到天），否则建不了日期表关系
  5. 留存矩阵要转成"长格式"（首购月 / 第几个月 / 留存率），
     宽格式在 Power BI 里做热力图很别扭

【产出】都放在 看板数据\ 文件夹里，共 7 个 CSV

【怎么运行】
  双击项目里的「运行准备看板数据.bat」
"""

import os
import sys

import pandas as pd

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CLEAN = os.path.join(HERE, "原始文件副本", "cleaned")
OUT = os.path.join(HERE, "看板数据")


def say(text=""):
    print(text)


def price_band(value):
    if pd.isna(value):
        return None
    if value < 50:
        return "50 元以下"
    if value < 100:
        return "50-100 元"
    if value < 200:
        return "100-200 元"
    if value < 500:
        return "200-500 元"
    return "500 元以上"


def main():
    os.makedirs(OUT, exist_ok=True)
    say("=" * 72)
    say("准备 Power BI 看板数据")
    say("=" * 72)
    say(f"输出目录：{OUT}")

    # ---------------- 1. 订单主表（核心事实表） ----------------
    orders = pd.read_csv(
        os.path.join(CLEAN, "order_master.csv"), encoding="utf-8-sig",
        dtype={"customer_zip_code_prefix": str},
    )
    for column in ["gmv", "freight", "items", "categories",
                   "review_score", "is_late", "delivery_days"]:
        if column in orders.columns:
            orders[column] = pd.to_numeric(orders[column], errors="coerce")

    orders["下单时间"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce", format="mixed"
    )
    orders["下单日期"] = orders["下单时间"].dt.date
    orders["配送天数"] = orders["delivery_days"]
    orders["是否超时"] = orders["is_late"].map({1: "超时", 0: "准时"})
    orders["评分"] = orders["review_score"]
    orders["评价档"] = pd.cut(
        orders["评分"], bins=[0, 2, 3, 5],
        labels=["差评(1-2分)", "中评(3分)", "好评(4-5分)"],
    ).astype(object)
    orders["是否差评"] = (orders["评分"] <= 2).map({True: "差评", False: "非差评"})
    orders.loc[orders["评分"].isna(), ["评价档", "是否差评"]] = None
    orders["客单价档"] = orders["gmv"].apply(price_band)

    # 新客 / 老客：这一单是不是该客户的第一次购买
    首购月份 = orders.groupby("customer_unique_id")["order_month"].transform("min")
    orders["客群"] = (orders["order_month"] == 首购月份).map(
        {True: "新客", False: "老客"}
    )

    # 主品类：这一单里价格最高的那件商品的品类。
    # 为什么要它：品类条形图如果直接用「品类汇总」这张独立汇总表，
    # 它和日期表没有关系，年份切片器就筛不动它（而其他图都会变）。
    # 把品类挂到订单主表上，所有图就能统一受切片器控制。
    items_all = pd.read_csv(
        os.path.join(CLEAN, "order_items_clean.csv"), encoding="utf-8-sig"
    )
    items_all["price"] = pd.to_numeric(items_all["price"])
    top_idx = items_all.groupby("order_id")["price"].idxmax()
    primary = (items_all.loc[top_idx, ["order_id", "category_en"]]
               .rename(columns={"order_id": "_order_id", "category_en": "主品类"}))
    orders["主品类"] = orders["order_id"].map(
        primary.set_index("_order_id")["主品类"]
    )

    # 经纬度也挂到订单主表上（原因同上：地图如果只用「州级汇总」这张独立表，
    # 年份切片器就筛不动它）。注意读 CSV 时邮编必须指定成字符串，
    # 否则 pandas 会把它当数字（01037 变成 1037），和订单表的邮编对不上。
    geo = pd.read_csv(
        os.path.join(CLEAN, "geo_by_zip.csv"), encoding="utf-8-sig",
        dtype={"geolocation_zip_code_prefix": str},
    )
    zip_geo = geo.set_index("geolocation_zip_code_prefix")[["lat", "lng"]]
    orders["纬度"] = orders["customer_zip_code_prefix"].astype(str).str.strip().map(zip_geo["lat"])
    orders["经度"] = orders["customer_zip_code_prefix"].astype(str).str.strip().map(zip_geo["lng"])

    fact = pd.DataFrame({
        "订单编号": orders["order_id"],
        "客户编号": orders["customer_unique_id"],
        "下单时间": orders["下单时间"],
        "下单日期": orders["下单日期"],
        "月份": orders["order_month"],
        "州": orders["customer_state"],
        "城市": orders["customer_city"],
        "邮编前缀": orders["customer_zip_code_prefix"],
        "GMV": orders["gmv"],
        "运费": orders["freight"],
        "商品件数": orders["items"],
        "品类数": orders["categories"],
        "客单价档": orders["客单价档"],
        "客群": orders["客群"],
        "主品类": orders["主品类"],
        "纬度": orders["纬度"],
        "经度": orders["经度"],
        "配送天数": orders["配送天数"],
        "是否超时": orders["是否超时"],
        "评分": orders["评分"],
        "评价档": orders["评价档"],
        "是否差评": orders["是否差评"],
    })
    fact.to_csv(os.path.join(OUT, "订单主表.csv"), index=False, encoding="utf-8-sig")
    say(f"  订单主表.csv        {len(fact):>7,} 行 × {fact.shape[1]} 列")

    # ---------------- 2. 月度指标 ----------------
    monthly = pd.read_csv(os.path.join(HERE, "指标总表.csv"), encoding="utf-8-sig")
    monthly.to_csv(os.path.join(OUT, "月度指标.csv"), index=False, encoding="utf-8-sig")
    say(f"  月度指标.csv        {len(monthly):>7,} 行 × {monthly.shape[1]} 列")

    # ---------------- 3. 用户分群 ----------------
    users = pd.read_csv(os.path.join(HERE, "用户分群表.csv"), encoding="utf-8-sig")
    user_out = pd.DataFrame({
        "客户编号": users["customer_unique_id"],
        "最近购买距今天数": users["R"],
        "购买次数": users["F"],
        "累计消费": users["M"].round(2),
        "人群": users["人群"],
        "是否复购": users["是否复购"],
        "首购月份": users["首单月份"],
    })
    user_out.to_csv(os.path.join(OUT, "用户分群.csv"), index=False, encoding="utf-8-sig")
    say(f"  用户分群.csv        {len(user_out):>7,} 行 × {user_out.shape[1]} 列")

    # ---------------- 4. 州级汇总（带经纬度，给地图用） ----------------
    state = fact.groupby("州").agg(
        订单数=("订单编号", "count"),
        下单人数=("客户编号", "nunique"),
        GMV=("GMV", "sum"),
        平均评分=("评分", "mean"),
        纬度=("纬度", "mean"),
        经度=("经度", "mean"),
    ).reset_index()
    state["客单价"] = (state["GMV"] / state["订单数"]).round(2)
    state["GMV"] = state["GMV"].round(2)
    state["平均评分"] = state["平均评分"].round(3)
    late_rate = fact[fact["是否超时"].notna()].groupby("州")["是否超时"].apply(
        lambda s: (s == "超时").mean() * 100
    ).round(2).rename("超时率%")
    state = state.merge(late_rate, on="州", how="left")
    state = state.sort_values("GMV", ascending=False)
    state.to_csv(os.path.join(OUT, "州级汇总.csv"), index=False, encoding="utf-8-sig")
    say(f"  州级汇总.csv        {len(state):>7,} 行 × {state.shape[1]} 列（含经纬度）")

    # ---------------- 5. 品类汇总 ----------------
    items = pd.read_csv(os.path.join(CLEAN, "order_items_clean.csv"), encoding="utf-8-sig")
    items["price"] = pd.to_numeric(items["price"])
    category = (items.groupby("category_en")
                .agg(GMV=("price", "sum"), 件数=("order_item_id", "count"))
                .sort_values("GMV", ascending=False)
                .reset_index()
                .rename(columns={"category_en": "品类"}))
    category["GMV"] = category["GMV"].round(2)
    category["GMV占比%"] = (category["GMV"] / category["GMV"].sum() * 100).round(2)
    category["累计占比%"] = category["GMV占比%"].cumsum().round(2)
    category.to_csv(os.path.join(OUT, "品类汇总.csv"), index=False, encoding="utf-8-sig")
    say(f"  品类汇总.csv        {len(category):>7,} 行 × {category.shape[1]} 列")

    # ---------------- 6. 留存矩阵（转成长格式） ----------------
    matrix = pd.read_csv(os.path.join(HERE, "同期群留存矩阵.csv"), encoding="utf-8-sig")
    matrix = matrix.rename(columns={matrix.columns[0]: "首购月份"})
    long = matrix.melt(id_vars="首购月份", var_name="第几个月", value_name="留存率%")
    long = long[long["留存率%"].notna()]
    long["第几个月"] = pd.to_numeric(long["第几个月"]).astype(int)
    long["首购月份"] = long["首购月份"].astype(str)
    long.to_csv(os.path.join(OUT, "留存矩阵.csv"), index=False, encoding="utf-8-sig")
    say(f"  留存矩阵.csv        {len(long):>7,} 行（长格式：首购月 × 第几个月）")

    # ---------------- 7. 日期表 ----------------
    dates = pd.date_range(fact["下单时间"].min().normalize(),
                          fact["下单时间"].max().normalize(), freq="D")
    calendar = pd.DataFrame({"日期": dates})
    calendar["年"] = calendar["日期"].dt.year
    calendar["季度"] = calendar["日期"].dt.quarter.map(lambda q: f"Q{q}")
    calendar["月份"] = calendar["日期"].dt.month
    calendar["年月"] = calendar["日期"].dt.strftime("%Y-%m")
    calendar["年月序号"] = (calendar["日期"].dt.year * 12 + calendar["日期"].dt.month)
    calendar["星期"] = calendar["日期"].dt.dayofweek.map(
        lambda d: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][d]
    )
    calendar["日期"] = calendar["日期"].dt.date
    calendar.to_csv(os.path.join(OUT, "日期表.csv"), index=False, encoding="utf-8-sig")
    say(f"  日期表.csv          {len(calendar):>7,} 行（{calendar['日期'].min()} ~ "
        f"{calendar['日期'].max()}）")

    say("")
    say("全部准备完毕。下一步：打开 Power BI，按《PowerBI看板搭建指南.md》操作。")
    say("")
    say("文件清单：")
    for name in sorted(os.listdir(OUT)):
        path = os.path.join(OUT, name)
        say(f"  {name:<20} {os.path.getsize(path):>12,} 字节")


if __name__ == "__main__":
    main()
