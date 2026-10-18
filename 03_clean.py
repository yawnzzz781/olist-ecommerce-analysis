# -*- coding: utf-8 -*-
r"""
第 4 步：数据清洗与分层建模
================================================================

【这一步做什么】
把 原始文件\ 里的 9 张原始表，加工成能直接拿来做分析的一套干净表，
输出到 原始文件副本\cleaned\。

【为什么顺序不能乱】
  先筛订单 -> 再关联明细 -> 最后聚合。
  如果先把订单表和明细表连起来再筛，一个订单买了 3 件商品就会变成 3 行，
  "订单数"会从 96,211 变成 109,880，客单价直接算错。

【五条口径（全篇通用，写在《数据问题清单》第七节）】
  1. 只算 order_status = 'delivered' 的订单
  2. 时间窗：下单时间 >= 2017-01-01 且 < 2018-09-01（左闭右开）
  3. 涉及"人"的计算一律用 customer_unique_id
  4. 销售额 GMV = 订单明细的 price 求和，不含运费
  5. 同一订单有多条评价时，取 review_creation_date 最新的一条

【怎么运行】
  最简单：双击项目里的「运行数据清洗.bat」
  手动运行：
      "C:\Users\15414\Anaconda3\python.exe" 03_clean.py

【产出】（都在 原始文件副本\cleaned\ 里）
  orders_clean.csv        清洗后的订单表（96,211 行）
  order_items_clean.csv   清洗后的订单明细（109,880 行，含品类）
  reviews_clean.csv       去重后的评价表（95,568 行）
  products_clean.csv      商品表（品类空白已归为 unknown，已补英文名）
  geo_by_zip.csv          地理表按邮编聚合（约 19,015 行）
  order_master.csv        【分析用宽表】一行一订单，含 GMV / 时效 / 评分
  清洗日志.txt            每一步的处理说明和校验数字
"""

import os
import sys

import pandas as pd

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "原始文件")
OUT = os.path.join(HERE, "原始文件副本", "cleaned")
LOG_PATH = os.path.join(OUT, "清洗日志.txt")

WINDOW_START = "2017-01-01"
WINDOW_END = "2018-09-01"  # 左闭右开：不含 2018-09-01 当天

# 品类翻译表里缺的 2 个，手工补上
MANUAL_CATEGORY_EN = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "small_kitchen_appliances",
}

lines = []
checks = []


def say(text="") -> None:
    print(text)
    lines.append(text)


def check(label, actual, expected) -> None:
    """打印校验结果：实际值应该等于预期值。"""
    ok = actual == expected
    mark = "[OK]" if ok else "[!!]"
    tail = "" if ok else f"   <<< 预期是 {expected}，请检查！"
    say(f"    {mark} {label}：{actual}{tail}")
    checks.append((label, actual, expected, ok))


def read_csv(name):
    return pd.read_csv(
        os.path.join(SRC, name), dtype=str, keep_default_na=False, encoding="utf-8-sig"
    )


def to_dt(series):
    return pd.to_datetime(series, errors="coerce", format="mixed")


def main() -> None:
    say("=" * 68)
    say("第 4 步：数据清洗与分层建模")
    say("=" * 68)
    say(f"原始数据：{SRC}")
    say(f"输出目录：{OUT}")
    say(f"分析时间窗：{WINDOW_START} ~ {WINDOW_END}（左闭右开）")

    os.makedirs(OUT, exist_ok=True)

    # ---------------------------------------------------------------
    say("")
    say("【第 1 步】读取 9 张原始表")
    say("-" * 68)
    orders = read_csv("olist_orders_dataset.csv")
    items = read_csv("olist_order_items_dataset.csv")
    payments = read_csv("olist_order_payments_dataset.csv")
    reviews = read_csv("olist_order_reviews_dataset.csv")
    customers = read_csv("olist_customers_dataset.csv")
    products = read_csv("olist_products_dataset.csv")
    sellers = read_csv("olist_sellers_dataset.csv")
    geo = read_csv("olist_geolocation_dataset.csv")
    trans = read_csv("product_category_name_translation.csv")
    say(f"    订单表 {len(orders)} 行 | 明细 {len(items)} | 付款 {len(payments)} "
        f"| 评价 {len(reviews)} | 买家 {len(customers)} | 商品 {len(products)} "
        f"| 卖家 {len(sellers)} | 地理 {len(geo)} | 品类翻译 {len(trans)}")
    check("原始订单总数", len(orders), 99441)

    # ---------------------------------------------------------------
    say("")
    say("【第 2 步】处理订单表：筛已送达 + 限定时间窗")
    say("-" * 68)
    orders["purchase_ts"] = to_dt(orders["order_purchase_timestamp"])

    delivered = orders[orders["order_status"] == "delivered"].copy()
    say(f"    只保留已送达（delivered），剔掉未送达的 {len(orders) - len(delivered)} 单")
    check("已送达订单数", len(delivered), 96478)

    win = delivered[
        (delivered["purchase_ts"] >= WINDOW_START) & (delivered["purchase_ts"] < WINDOW_END)
    ].copy()
    say(f"    再限定时间窗，又剔掉窗口外的 {len(delivered) - len(win)} 单")
    check("窗口内已送达订单数", len(win), 96211)

    # 派生字段
    win["order_month"] = win["purchase_ts"].dt.to_period("M").astype(str)
    for col in [
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        win[col] = win[col].str.strip().replace("", pd.NA)

    delivered_ts = to_dt(win["order_delivered_customer_date"])
    estimate_ts = to_dt(win["order_estimated_delivery_date"])
    win["delivery_days"] = (delivered_ts - win["purchase_ts"]).dt.days
    win["is_late"] = (delivered_ts > estimate_ts).where(
        delivered_ts.notna() & estimate_ts.notna()
    )

    missing_delivered = int(delivered_ts.isna().sum())
    say(f"    已送达但缺签收时间的：{missing_delivered} 单（这{missing_delivered}单算不出配送天数）")
    late_rate = win["is_late"].mean() * 100
    say(f"    配送超时率：{late_rate:.2f}%"
        f"（超时 {int(win['is_late'].sum())} 单 / 准时 {int((win['is_late'] == False).sum())} 单）")
    say(f"    平均配送天数：{win['delivery_days'].mean():.1f} 天"
        f"（中位数 {win['delivery_days'].median():.0f} 天）")

    # ---------------------------------------------------------------
    say("")
    say("【第 3 步】把订单级编号换成人级编号")
    say("-" * 68)
    uid = customers[["customer_id", "customer_unique_id", "customer_city",
                     "customer_state", "customer_zip_code_prefix"]]
    win = win.merge(uid, on="customer_id", how="left")
    say(f"    customer_id 是每笔订单一个编号；customer_unique_id 才是同一个人")
    check("这些订单来自多少个人", win["customer_unique_id"].nunique(), 93104)
    say(f"    平均每人 {len(win) / win['customer_unique_id'].nunique():.2f} 单"
        f"（<1.1 说明复购天然很低，后面做 RFM 时要有心理准备）")

    # ---------------------------------------------------------------
    say("")
    say("【第 4 步】关联订单明细，算第一批指标")
    say("-" * 68)
    order_ids = set(win["order_id"])
    it = items[items["order_id"].isin(order_ids)].copy()
    it["price"] = pd.to_numeric(it["price"])
    it["freight_value"] = pd.to_numeric(it["freight_value"])
    check("订单明细行数", len(it), 109880)
    check("有明细的订单数", it["order_id"].nunique(), 96211)

    gmv = it["price"].sum()
    freight = it["freight_value"].sum()
    say(f"    GMV（只加 price，不含运费）：{gmv:,.2f}")
    say(f"    运费合计：{freight:,.2f}")
    say(f"    客单价 = GMV / 订单数 = {gmv / len(win):,.2f}")
    say(f"    【口径】运费不算进 GMV，因为它是物流成本，不是商品销售额")
    check("GMV 取整", round(gmv), 13181027)

    # ---------------------------------------------------------------
    say("")
    say("【第 5 步】评价表去重（一单多评只留最新一条）")
    say("-" * 68)
    rw = reviews[reviews["order_id"].isin(order_ids)].copy()
    rw["score"] = pd.to_numeric(rw["review_score"])
    rw["created"] = to_dt(rw["review_creation_date"])
    say(f"    原始评价行数：{len(rw)}，只涉及 {rw['order_id'].nunique()} 个订单"
        f"（说明有 {len(rw) - rw['order_id'].nunique()} 行是同一订单的重复评价）")
    rw = rw.sort_values(["order_id", "created"]).drop_duplicates("order_id", keep="last")
    check("去重后的评价行数", len(rw), 95568)
    say(f"    平均评分：{rw['score'].mean():.3f}")
    say(f"    差评（<=2 分）占比：{(rw['score'] <= 2).mean() * 100:.2f}%")
    say(f"    没有评价的订单：{len(win) - len(rw)} 单")
    say(f"    另有 {reviews['order_id'].nunique() - rw['order_id'].nunique()} 个订单的评价"
        f"不在我们的分析窗口内，已排除")

    # ---------------------------------------------------------------
    say("")
    say("【第 6 步】商品表：补品类翻译，空白归为 unknown")
    say("-" * 68)
    prod = products.copy()
    prod["category_pt"] = prod["product_category_name"].replace("", "unknown")
    name_map = dict(zip(trans["product_category_name"],
                        trans["product_category_name_english"]))
    name_map.update(MANUAL_CATEGORY_EN)
    prod["category_en"] = prod["category_pt"].map(name_map).fillna(prod["category_pt"])
    filled = int((products["product_category_name"] == "").sum())
    say(f"    品类空白填成 unknown：{filled} 个商品")
    say(f"    补上翻译表缺的 2 个品类：pc_gamer、portateis_cozinha_e_preparadores_de_alimentos")
    check("商品品类数（不含 unknown）",
          prod[prod["category_pt"] != "unknown"]["category_pt"].nunique(), 73)

    it = it.merge(
        prod[["product_id", "category_pt", "category_en"]], on="product_id", how="left"
    )

    # ---------------------------------------------------------------
    say("")
    say("【第 7 步】地理表：先按邮编聚合（否则连表会爆炸）")
    say("-" * 68)
    say(f"    原始 {len(geo)} 行，其中完全重复的行 {int(geo.duplicated().sum())} 行，先去重")
    geo2 = geo.drop_duplicates().copy()
    geo2["lat"] = pd.to_numeric(geo2["geolocation_lat"], errors="coerce")
    geo2["lng"] = pd.to_numeric(geo2["geolocation_lng"], errors="coerce")
    in_brazil = geo2["lat"].between(-34.2, 5.5) & geo2["lng"].between(-74.5, -33.5)
    say(f"    剔除 {int((~in_brazil).sum())} 行坐标不在巴西范围内的（约 -34~5 / -74~-33）")
    geo2 = geo2[in_brazil]
    geo_by_zip = (
        geo2.groupby("geolocation_zip_code_prefix")
        .agg(lat=("lat", "mean"), lng=("lng", "mean"),
             state=("geolocation_state", "first"), city=("geolocation_city", "first"),
             原始行数=("lat", "size"))
        .reset_index()
    )
    say(f"    聚合后：{len(geo_by_zip)} 行（一个邮编一行，{len(geo)} 行压成 {len(geo_by_zip)} 行）")
    say(f"    如果不聚合就直接连表，96,211 行的订单表会膨胀成几百万行")

    # 买家邮编匹配情况
    zip_in_geo = set(geo_by_zip["geolocation_zip_code_prefix"])
    cust_zips = set(win["customer_zip_code_prefix"])
    unmatched = len(cust_zips - zip_in_geo)
    say(f"    买家邮编 {len(cust_zips)} 个，其中 {unmatched} 个在地理表里找不到"
        f"（占 {unmatched / len(cust_zips) * 100:.2f}%，做地图时这部分没有坐标）")

    # ---------------------------------------------------------------
    say("")
    say("【第 8 步】拼一张分析用的宽表 order_master（一行一订单）")
    say("-" * 68)
    agg = it.groupby("order_id").agg(
        gmv=("price", "sum"),
        freight=("freight_value", "sum"),
        items=("order_item_id", "count"),
        categories=("category_pt", "nunique"),
    ).reset_index()

    master = win[[
        "order_id", "customer_unique_id", "customer_state", "customer_city",
        "customer_zip_code_prefix", "order_purchase_timestamp", "order_month",
        "order_delivered_customer_date", "order_estimated_delivery_date",
        "delivery_days", "is_late",
    ]].merge(agg, on="order_id", how="left")
    master = master.merge(
        rw[["order_id", "score"]].rename(columns={"score": "review_score"}),
        on="order_id", how="left",
    )
    check("宽表行数（一行一订单）", len(master), 96211)
    say(f"    含 gmv、freight（运费）、items（件数）、categories（品类数）、"
        f"配送天数、是否超时、评分")
    say(f"    没评分的订单 {int(master['review_score'].isna().sum())} 行"
        f"（分析评分时记得排除空值）")

    # ---------------------------------------------------------------
    say("")
    say("【第 9 步】写出文件")
    say("-" * 68)
    outputs = {
        "orders_clean.csv": win,
        "order_items_clean.csv": it,
        "reviews_clean.csv": rw,
        "products_clean.csv": prod,
        "geo_by_zip.csv": geo_by_zip,
        "order_master.csv": master,
    }
    for name, frame in outputs.items():
        path = os.path.join(OUT, name)
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        say(f"    写出 {name:<26} {len(frame):>7} 行   {os.path.getsize(path):>10,} 字节")
    say(f"    付款表和卖家表没有进行加工：它们没有空白或异常，直接按 order_id / seller_id"
        f" 关联即可（不需要处理的表就别动它）")

    # ---------------------------------------------------------------
    say("")
    say("=" * 68)
    say("校验汇总")
    say("=" * 68)
    bad = 0
    for label, actual, expected, ok in checks:
        say(f"    {'[OK]' if ok else '[!!]'} {label:<22} 实际 {actual:<10} 预期 {expected}")
        bad += 0 if ok else 1
    say("")
    if bad == 0:
        say(f"    全部 {len(checks)} 项校验通过，清洗完成。")
    else:
        say(f"    有 {bad} 项对不上，请先检查再往下做。")

    with open(LOG_PATH, "w", encoding="utf-8-sig", newline="") as handle:
        handle.write("\r\n".join(lines))
    print(f"\n清洗日志已保存：{LOG_PATH}")
    print(f"所有结果在：{OUT}")


if __name__ == "__main__":
    main()
