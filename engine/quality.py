"""Non-move findings (flags) for the merchandiser. Owned by S3.

    find_flags(data, feats) -> [{flag_id, kind, location_id, sku_id, style_id, message}]

Kinds (spec §5.9): DATA_QUALITY, CAPACITY, NEW_STORE, REORDER, DEAD_STOCK.
Messages are one line, plain English, with the numbers behind them.
"""
from __future__ import annotations

import pandas as pd

from engine import config as C
from engine.data import Data

REORDER_MIN_SOLD_365 = 50       # style must have sold at least this many in 12 months
REORDER_MAX_LEFT_SHARE = 0.05   # ...and have at most 5% of that left chain-wide
DEAD_MIN_STORES = 5             # on shelf all 12 weeks at >= this many stores
DEAD_MAX_SOLD_84 = 10           # ...and sold at most this many chain-wide in those 12 weeks
DEAD_MIN_YEARS_COVER = 2        # ...and holds >= 2 years of stock at the last-12-month pace
NEW_STORE_DAYS = 90


def _d(t: pd.Timestamp) -> str:
    return f"{t.day} {t.strftime('%b %Y')}"


def find_flags(data: Data, feats) -> list[dict]:
    a = data.as_of
    store_ids = set(data.stores["store_id"])
    styles = data.items.drop_duplicates("style_id").set_index("style_id")["style_name"].to_dict()
    sku_style = data.items.set_index("sku_id")["style_id"]
    out: list[dict] = []

    def add(kind, message, location_id=None, sku_id=None, style_id=None):
        out.append({"flag_id": None, "kind": kind, "location_id": location_id, "sku_id": sku_id,
                    "style_id": style_id, "message": message.replace("\n", " ")})

    # ---- DATA_QUALITY: negative on-hand ----
    snap = data.snapshot
    for r in snap[snap["on_hand_raw"] < 0].itertuples(index=False):
        add("DATA_QUALITY", f"{r.location_id} {r.sku_id}: on hand is {r.on_hand_raw} in the {_d(a)} stock snapshot; "
                            f"treated as 0. Stock count needed.",
            location_id=r.location_id, sku_id=r.sku_id, style_id=sku_style.get(r.sku_id))

    # ---- DATA_QUALITY: sales in weeks recorded as 0 days in stock ----
    wk = data.weekly
    s = data.sales[["date", "store_id", "sku_id", "qty"]].copy()
    s["week_ending"] = s["date"] + pd.to_timedelta((5 - s["date"].dt.weekday) % 7, unit="D")   # weeks end Saturday
    m = s.merge(wk[["week_ending", "store_id", "sku_id", "days_in_stock"]], on=["week_ending", "store_id", "sku_id"])
    z = m[m["days_in_stock"] == 0].groupby("store_id").agg(units=("qty", "sum"), weeks=("week_ending", "nunique"),
                                                           skus=("sku_id", "nunique"))
    for store, r in z.sort_index().iterrows():
        add("DATA_QUALITY", f"{store}: {int(r.units)} units sold across {int(r.skus)} SKUs in {int(r.weeks)} weeks "
                            f"recorded as 0 days in stock; stock records there are unreliable.",
            location_id=store)

    # ---- CAPACITY ----
    sp = feats.store_pos
    for r in sp[sp["utilisation"] > 1.0].sort_values("store_id").itertuples(index=False):
        add("CAPACITY", f"{r.store_id}: {int(r.units)} units in a {int(r.capacity)}-unit store "
                        f"({r.utilisation:.0%}); send nothing there until the excess is moved out.",
            location_id=r.store_id)

    # ---- NEW_STORE ----
    st = data.stores
    new = st[(a - st["opened_on"]).dt.days.between(0, NEW_STORE_DAYS)]
    for r in new.sort_values("store_id").itertuples(index=False):
        days = (a - r.opened_on).days
        add("NEW_STORE", f"{r.store_id} opened {_d(r.opened_on)} ({days} days ago): its demand is estimated from "
                         f"peer {r.tier}-tier stores in {r.zone} zone, not its own {days} days of sales.",
            location_id=r.store_id)

    # ---- REORDER: sold out chain-wide, nothing inbound ----
    sales = data.sales
    sold_365 = sales[sales["date"] > a - pd.Timedelta(days=365)].groupby("style_id")["qty"].sum()
    sold_84 = sales[sales["date"] > a - pd.Timedelta(days=C.VELOCITY_WINDOW_DAYS)].groupby("style_id")["qty"].sum()
    left = (snap.assign(u=snap["on_hand"] + snap["in_transit"]).assign(style_id=snap["sku_id"].map(sku_style))
            .groupby("style_id")["u"].sum())
    inbound = data.inbound.assign(style_id=data.inbound["sku_id"].map(sku_style)).groupby("style_id")["qty"].sum()
    reorder = set()
    for style in sorted(sold_365.index):
        n, mleft = int(sold_365[style]), int(left.get(style, 0))
        if n >= REORDER_MIN_SOLD_365 and mleft <= REORDER_MAX_LEFT_SHARE * n and int(inbound.get(style, 0)) == 0:
            reorder.add(style)
            add("REORDER", f"{style} {styles.get(style, '')}: sold out chain-wide ({n} sold in 12 months, {mleft} left, "
                           f"nothing inbound). {int(sold_84.get(style, 0))} sold in the last 12 weeks as stock ran out; "
                           f"low recent sales here mean sold out, not slow. Buyer: reorder or replace.",
                style_id=style)

    # ---- DEAD_STOCK: on shelf everywhere, nobody buys ----
    w = wk[wk["store_id"].isin(store_ids)].assign(style_id=wk["sku_id"].map(sku_style))
    n_weeks = w["week_ending"].nunique()
    full = w[w["days_in_stock"] == 7].groupby(["style_id", "store_id"])["week_ending"].nunique()
    stores_all_weeks = (full == n_weeks).groupby("style_id").sum()
    for style in sorted(stores_all_weeks.index):
        n_st = int(stores_all_weeks[style])
        s84, s365, mleft = int(sold_84.get(style, 0)), int(sold_365.get(style, 0)), int(left.get(style, 0))
        if (style not in reorder and n_st >= DEAD_MIN_STORES and s84 <= DEAD_MAX_SOLD_84
                and mleft >= DEAD_MIN_YEARS_COVER * s365 and mleft > 0):
            add("DEAD_STOCK", f"{style} {styles.get(style, '')}: on shelf all {n_weeks} weeks at {n_st} stores but only "
                              f"{s84} sold chain-wide in that time ({s365} in 12 months); {mleft} units left. "
                              f"Consolidate or mark down; do not reorder.",
                style_id=style)

    for i, f in enumerate(out, 1):
        f["flag_id"] = f"F{i:03d}"
    return out
