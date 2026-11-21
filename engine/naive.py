"""Naive placeholder features (plain 90-day rate, no de-censoring, no lift). Owned by S0.

Exists only so S2/S3/S4/S5 can work before S1 lands. S1's velocity.py / position.py
replace these automatically (see interfaces.build_features). Same output columns.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engine import config as C
from engine.data import Data, protected_styles
from engine.interfaces import (Features, SKU_POS_COLS, STORE_POS_COLS, VEL_COLS, WH_COLS,
                               WH_TIMELINE_COLS)


def naive_velocity(data: Data) -> pd.DataFrame:
    start = data.as_of - pd.Timedelta(days=C.VELOCITY_WINDOW_DAYS)
    s = data.sales[data.sales["date"] > start]
    sold = s.groupby(["store_id", "sku_id"])["qty"].sum().rename("sold_84")
    grid = pd.MultiIndex.from_product([data.stores["store_id"], data.items["sku_id"]],
                                      names=["store_id", "sku_id"]).to_frame(index=False)
    v = grid.merge(sold.reset_index(), on=["store_id", "sku_id"], how="left").fillna({"sold_84": 0})
    v["sold_84"] = v["sold_84"].astype(int)
    v["in_stock_days"] = C.VELOCITY_WINDOW_DAYS
    v["rate_instock"] = v["sold_84"] / C.VELOCITY_WINDOW_DAYS
    v["lift"] = 1.0
    v["vel_daily"] = v["rate_instock"]
    v["basis"] = "naive_84d"
    return v[VEL_COLS]


def _cover(avail: pd.Series, vel: pd.Series) -> pd.Series:
    return np.where(vel > 0, avail / vel.where(vel > 0, 1), np.inf)


def naive_positions(data: Data, vel: pd.DataFrame) -> Features:
    st = data.stores.set_index("store_id")
    snap = data.snapshot
    store_snap = snap[snap["location_id"] != C.WH_ID]

    p = vel.rename(columns={"store_id": "location_id"}).merge(
        store_snap[["location_id", "sku_id", "on_hand", "in_transit", "oldest_received"]],
        on=["location_id", "sku_id"], how="left")
    p[["on_hand", "in_transit"]] = p[["on_hand", "in_transit"]].fillna(0).astype(int)
    p = p.merge(data.items[["sku_id", "style_id", "style_name", "category", "cat_group", "size", "mrp", "is_core"]],
                on="sku_id")
    p["tier"] = p["location_id"].map(st["tier"])
    p["city"] = p["location_id"].map(st["city"])
    p["zone"] = p["location_id"].map(st["zone"])
    p["available"] = p["on_hand"] + p["in_transit"]
    p["cover_days"] = _cover(p["available"], p["vel_daily"])
    p["age_days"] = (data.as_of - p["oldest_received"]).dt.days
    target = p["zone"].map(C.LEAD_WH) + C.REVIEW_DAYS + C.SAFETY_DAYS
    p["need_units"] = np.maximum(0, np.ceil(p["vel_daily"] * target) - p["available"]).astype(int)
    keep = np.ceil(p["vel_daily"] * C.DONOR_MIN_COVER_DAYS)
    p["excess_units"] = np.maximum(0, p["available"] - keep).astype(int)
    prot = protected_styles(data)
    p["is_protected"] = [(a, b) in prot for a, b in zip(p["location_id"], p["style_id"])]
    p.loc[p["is_protected"], "excess_units"] = 0
    sku_pos = p[SKU_POS_COLS].reset_index(drop=True)

    g = sku_pos.groupby("location_id").agg(units=("available", "sum"), vel_daily=("vel_daily", "sum"))
    sp = data.stores[["store_id", "tier", "city", "zone", "capacity"]].merge(
        g, left_on="store_id", right_index=True, how="left").fillna({"units": 0, "vel_daily": 0})
    sp["utilisation"] = sp["units"] / sp["capacity"]
    sp["cover_days"] = _cover(sp["units"], sp["vel_daily"])
    cat = sku_pos.groupby(["location_id", "tier", "cat_group"])["available"].sum().reset_index()
    cat = cat.merge(data.min_display, on=["tier", "cat_group"], how="left")
    below = cat[cat["available"] < cat["min_units"]].groupby("location_id")["cat_group"].apply(list)
    sp["below_min"] = sp["store_id"].map(below).apply(lambda x: x if isinstance(x, list) else [])
    store_pos = sp[STORE_POS_COLS]

    whs = snap[snap["location_id"] == C.WH_ID].copy()
    whs["age_days"] = (data.as_of - whs["oldest_received"]).dt.days
    wh = whs[WH_COLS].reset_index(drop=True)

    t0 = wh[["sku_id", "on_hand"]].rename(columns={"on_hand": "qty"}).assign(date=data.as_of)
    t1 = data.inbound.rename(columns={"expected_date": "date"})[["sku_id", "date", "qty"]]
    tl = pd.concat([t0, t1]).groupby(["sku_id", "date"], as_index=False)["qty"].sum().sort_values(["sku_id", "date"])
    tl["cum_qty"] = tl.groupby("sku_id")["qty"].cumsum()
    wh_timeline = tl[WH_TIMELINE_COLS].reset_index(drop=True)

    return Features(sku_pos=sku_pos, store_pos=store_pos, wh=wh, wh_timeline=wh_timeline)
