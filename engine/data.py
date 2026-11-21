"""Load and clean the Manyavar CSVs. Owned by S0.

Everything downstream reads from `Data`; never re-read CSVs elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from engine import config as C


@dataclass
class Data:
    as_of: pd.Timestamp
    stores: pd.DataFrame         # store_id, city, state, zone, tier, capacity(int), opened_on(ts), area_manager_id
    area_managers: pd.DataFrame  # area_manager_id, name, city, stores(list[str]), max_alerts_per_week(int)
    items: pd.DataFrame          # sku_id, style_id, style_name, category, cat_group, size, mrp, cost_price, launch_date, is_core(bool)  -- packaging removed
    sales: pd.DataFrame          # date(ts), bill_id, store_id, customer_id, sku_id, style_id, category, size, qty(int), mrp, selling_price  -- packaging removed
    snapshot: pd.DataFrame       # location_id, sku_id, on_hand(int, clipped >=0), on_hand_raw(int), in_transit(int), in_transit_arrives_on(ts|NaT), oldest_received(ts|NaT)
    weekly: pd.DataFrame         # week_ending(ts), store_id, sku_id, closing_on_hand(int), days_in_stock(int)
    inbound: pd.DataFrame        # expected_date(ts), sku_id, qty(int)
    calendar: pd.DataFrame       # date(ts), state, festival(str, '' if none), is_wedding(bool)
    min_display: pd.DataFrame    # tier, cat_group, min_units(int)
    protected: pd.DataFrame      # store_id, rank(int), style_id
    footfall: pd.DataFrame       # date(ts), store_id, footfall(int)


def _read(d: Path, name: str) -> pd.DataFrame:
    return pd.read_csv(d / f"{name}.csv", dtype=str, keep_default_na=False)


def _ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.replace("", None), errors="coerce")


def _int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int)


def cat_group(category: str) -> str:
    return C.ACCESSORY_GROUP if category in C.ACCESSORY_CATS else category


def load_data(data_dir: Path = C.DATA_DIR) -> Data:
    d = Path(data_dir)
    stores = _read(d, "stores")
    stores["capacity"] = _int(stores.pop("stock_capacity_units"))
    stores["size_sqft"] = _int(stores["size_sqft"])
    stores["opened_on"] = _ts(stores["opened_on"])

    am = _read(d, "area_managers")
    am["stores"] = am["stores"].str.split(",").apply(lambda xs: [x.strip() for x in xs])
    am["max_alerts_per_week"] = _int(am["max_alerts_per_week"])

    items = _read(d, "items")
    items = items[items["is_packaging"] != "1"].copy()
    items["mrp"] = _int(items["mrp"])
    items["cost_price"] = _int(items["cost_price"])
    items["launch_date"] = _ts(items["launch_date"])
    items["is_core"] = items["is_core_style"] == "1"
    items["cat_group"] = items["category"].map(cat_group)
    items = items.drop(columns=["is_core_style", "is_packaging"]).reset_index(drop=True)

    bills = _read(d, "bills")
    lines = _read(d, "bill_lines")
    sales = lines.merge(bills, on="bill_id").merge(
        items[["sku_id", "style_id", "category", "size"]], on="sku_id")  # inner join drops packaging
    sales["date"] = _ts(sales.pop("bill_date"))
    for c in ("qty", "mrp", "selling_price"):
        sales[c] = _int(sales[c])

    snap = _read(d, "stock_snapshot")
    as_of = pd.Timestamp(snap["as_of_date"].iloc[0])
    snap["on_hand_raw"] = _int(snap["on_hand"])
    snap["on_hand"] = snap["on_hand_raw"].clip(lower=0)   # MYS-02 KUR-02-M = -4 -> 0 (flagged by quality.py)
    snap["in_transit"] = _int(snap["in_transit"])
    snap["in_transit_arrives_on"] = _ts(snap["in_transit_arrives_on"])
    snap["oldest_received"] = _ts(snap.pop("oldest_stock_received_on"))
    snap = snap[snap["sku_id"].isin(items["sku_id"])].drop(columns=["as_of_date"]).reset_index(drop=True)

    wk = _read(d, "stock_weekly")
    wk["week_ending"] = _ts(wk["week_ending"])
    wk["closing_on_hand"] = _int(wk["closing_on_hand"])
    wk["days_in_stock"] = _int(wk["days_in_stock"])

    inb = _read(d, "warehouse_inbound")
    inb["expected_date"] = _ts(inb["expected_date"])
    inb["qty"] = _int(inb["qty"])
    inb = inb[["expected_date", "sku_id", "qty"]]

    cal = _read(d, "calendar")
    cal["date"] = _ts(cal["date"])
    cal["is_wedding"] = cal.pop("is_wedding_date") == "1"

    md = _read(d, "min_display").rename(columns={"category": "cat_group", "min_display_units": "min_units"})
    md["min_units"] = _int(md["min_units"])

    prot = _read(d, "flagship_protected")
    prot["rank"] = _int(prot["rank"])

    ff = _read(d, "footfall_daily")
    ff["date"] = _ts(ff["date"])
    ff["footfall"] = _int(ff["footfall"])

    return Data(as_of=as_of, stores=stores, area_managers=am, items=items, sales=sales,
                snapshot=snap, weekly=wk, inbound=inb, calendar=cal, min_display=md,
                protected=prot, footfall=ff)


def lead_days(src: str, dst: str, stores: pd.DataFrame) -> int:
    """Lead time in days between two locations (store ids or WH-KOL)."""
    s = stores.set_index("store_id")
    if src == C.WH_ID and dst == C.WH_ID:
        return 0
    if src == C.WH_ID:
        return C.LEAD_WH[s.at[dst, "zone"]]
    if dst == C.WH_ID:
        return C.LEAD_WH[s.at[src, "zone"]]
    if s.at[src, "city"] == s.at[dst, "city"]:
        return C.LEAD_S2S_SAME_CITY
    if s.at[src, "zone"] == s.at[dst, "zone"]:
        return C.LEAD_S2S_SAME_ZONE
    return C.LEAD_S2S_OTHER_ZONE


def protected_styles(data: Data) -> set[tuple[str, str]]:
    """{(store_id, style_id)} that may never leave an S++ store."""
    return set(zip(data.protected["store_id"], data.protected["style_id"]))
