"""Stable seams between sessions. Owned by S0.

    data = load_data()
    feats = build_features(data)            # S1 (velocity.py + position.py), naive fallback until S1 lands
    result = generate_moves(data, feats)    # S2 (moves.py)
    flags = find_flags(data, feats)         # S3 (quality.py)
    validation = validate(data, feats, result["groups"])   # S3 (rules.py)

Each stage falls back to a placeholder when its module is not written yet, so every
session can run `python -m engine.run` end-to-end from minute one.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.data import Data

# Contract C1 column lists (see contracts/CONTRACTS.md). Do not rename.
VEL_COLS = ["store_id", "sku_id", "sold_84", "in_stock_days", "rate_instock", "lift", "vel_daily", "basis"]
SKU_POS_COLS = ["location_id", "sku_id", "style_id", "style_name", "category", "cat_group", "size", "mrp",
                "is_core", "tier", "city", "zone", "on_hand", "in_transit", "available", "sold_84",
                "in_stock_days", "rate_instock", "lift", "vel_daily", "basis", "cover_days", "age_days",
                "need_units", "excess_units", "is_protected"]
STORE_POS_COLS = ["store_id", "tier", "city", "zone", "capacity", "units", "utilisation", "vel_daily",
                  "cover_days", "below_min"]
WH_COLS = ["sku_id", "on_hand", "age_days"]
WH_TIMELINE_COLS = ["sku_id", "date", "qty", "cum_qty"]


@dataclass
class Features:
    sku_pos: pd.DataFrame      # one row per store x non-packaging SKU (full grid, 20 x 382), SKU_POS_COLS
    store_pos: pd.DataFrame    # one row per store, STORE_POS_COLS; below_min = list[str] of cat_groups
    wh: pd.DataFrame           # WH_COLS, one row per SKU held at WH-KOL
    wh_timeline: pd.DataFrame  # WH_TIMELINE_COLS: as_of on_hand row + one row per inbound date; cum_qty = running supply


def build_features(data: Data) -> Features:
    try:
        from engine.velocity import compute_velocity        # S1
    except ImportError:
        from engine.naive import naive_velocity as compute_velocity
    try:
        from engine.position import build_positions         # S1
    except ImportError:
        from engine.naive import naive_positions as build_positions
    vel = compute_velocity(data)
    return build_positions(data, vel)


def generate_moves(data: Data, feats: Features) -> dict:
    """Returns {"groups": [...C2 group dicts...], "problems": [...C2 problem dicts...]}"""
    try:
        from engine.moves import generate_moves as impl     # S2
    except ImportError:
        return {"groups": [], "problems": []}
    return impl(data, feats)


def find_flags(data: Data, feats: Features) -> list[dict]:
    try:
        from engine.quality import find_flags as impl       # S3
    except ImportError:
        return []
    return impl(data, feats)


def validate(data: Data, feats: Features, groups: list[dict]) -> dict:
    """Returns {"passed": bool, "checked_moves": int, "violations": [ {rule, group_id, detail} ]}"""
    try:
        from engine.rules import validate as impl           # S3
    except ImportError:
        return {"passed": False, "checked_moves": 0, "violations": [
            {"rule": "VALIDATOR_MISSING", "group_id": None, "detail": "engine/rules.py not written yet"}]}
    return impl(data, feats, groups)
