"""Store x SKU positions (stock, cover, need, excess). Owned by S1.

Starts from engine/naive.py::naive_positions; differences:
  need_units   = ceil(vel_daily x (lead_WH + review 7 + safety 7)) - available, then raised so every
                 store x cat_group reaches min display (deficit spread one unit at a time over the store's
                 fastest SKUs in that category, chain best-sellers when the store has no velocity there)
  excess_units = available - ceil(vel_daily x 30) (all available when vel 0), 0 for protected S++ styles,
                 then trimmed so taking every excess unit still leaves the category at min display (spec 5.3)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import config as C
from engine.data import Data, protected_styles
from engine.interfaces import (Features, SKU_POS_COLS, STORE_POS_COLS, WH_COLS, WH_TIMELINE_COLS)


def _cover(avail: pd.Series, vel: pd.Series) -> np.ndarray:
    return np.where(vel > 0, avail / vel.where(vel > 0, 1), np.inf)


def _min_display_topup(p: pd.DataFrame, min_display: pd.DataFrame, chain_vel: pd.Series) -> pd.DataFrame:
    """Raise need_units so available + need reaches min_units per location x cat_group.

    p needs location_id, tier, cat_group, sku_id, available, vel_daily, need_units.
    chain_vel: sku_id -> chain total vel_daily (fallback ranking when the store sells nothing in the category).
    """
    p = p.copy()
    g = p.groupby(["location_id", "tier", "cat_group"])[["available", "need_units"]].sum().reset_index()
    g = g.merge(min_display, on=["tier", "cat_group"])
    g["deficit"] = (g["min_units"] - g["available"] - g["need_units"]).clip(lower=0).astype(int)
    g = g[g["deficit"] > 0]
    if g.empty:
        return p
    p["_chain"] = p["sku_id"].map(chain_vel).fillna(0.0)
    add = pd.Series(0, index=p.index)
    for loc, cg, deficit in zip(g["location_id"], g["cat_group"], g["deficit"]):
        cand = p[(p["location_id"] == loc) & (p["cat_group"] == cg)]
        live = cand[(cand["vel_daily"] > 0) | (cand["_chain"] > 0)]
        cand = (live if not live.empty else cand).sort_values(["vel_daily", "_chain", "sku_id"],
                                                              ascending=[False, False, True])
        idx = cand.index.to_numpy()
        for i in range(deficit):                      # one unit at a time, round-robin over the ranked SKUs
            add[idx[i % len(idx)]] += 1
    p["need_units"] = (p["need_units"] + add).astype(int)
    return p.drop(columns="_chain")


def _trim_excess_to_min_display(p: pd.DataFrame, min_display: pd.DataFrame) -> pd.Series:
    """Cap each location x cat_group's total excess at available - min_units; slowest SKUs released first."""
    q = p[["location_id", "tier", "cat_group", "available", "excess_units", "vel_daily"]].merge(
        min_display, on=["tier", "cat_group"], how="left")
    q.index = p.index
    q["min_units"] = q["min_units"].fillna(0)
    grp = ["location_id", "cat_group"]
    cap = (q.groupby(grp)["available"].transform("sum") - q["min_units"]).clip(lower=0)
    q = q.assign(_cap=cap).sort_values(grp + ["vel_daily"], kind="stable")
    before = q.groupby(grp)["excess_units"].cumsum() - q["excess_units"]
    allowed = np.minimum(q["excess_units"], (q["_cap"] - before).clip(lower=0))
    return allowed.reindex(p.index).astype(int)


def build_positions(data: Data, vel: pd.DataFrame) -> Features:
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
    p["age_days"] = (data.as_of - p["oldest_received"]).dt.days      # NaN when oldest_received blank

    target = p["zone"].map(C.LEAD_WH) + C.REVIEW_DAYS + C.SAFETY_DAYS
    p["need_units"] = np.maximum(0, np.ceil(p["vel_daily"] * target) - p["available"]).astype(int)
    chain_vel = p.groupby("sku_id")["vel_daily"].sum()
    p = _min_display_topup(p, data.min_display, chain_vel)

    keep = np.ceil(p["vel_daily"] * C.DONOR_MIN_COVER_DAYS)
    p["excess_units"] = np.maximum(0, p["available"] - keep).astype(int)
    prot = protected_styles(data)
    p["is_protected"] = [(a, b) in prot for a, b in zip(p["location_id"], p["style_id"])]
    p.loc[p["is_protected"], "excess_units"] = 0
    p["excess_units"] = _trim_excess_to_min_display(p, data.min_display)
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
    store_pos = sp[STORE_POS_COLS].reset_index(drop=True)

    whs = snap[snap["location_id"] == C.WH_ID].copy()
    whs["age_days"] = (data.as_of - whs["oldest_received"]).dt.days
    wh = whs[WH_COLS].reset_index(drop=True)

    t0 = wh[["sku_id", "on_hand"]].rename(columns={"on_hand": "qty"}).assign(date=data.as_of)
    t1 = data.inbound.rename(columns={"expected_date": "date"})[["sku_id", "date", "qty"]]
    tl = pd.concat([t0, t1]).groupby(["sku_id", "date"], as_index=False)["qty"].sum().sort_values(["sku_id", "date"])
    tl["cum_qty"] = tl.groupby("sku_id")["qty"].cumsum()
    wh_timeline = tl[WH_TIMELINE_COLS].reset_index(drop=True)

    return Features(sku_pos=sku_pos, store_pos=store_pos, wh=wh, wh_timeline=wh_timeline)
