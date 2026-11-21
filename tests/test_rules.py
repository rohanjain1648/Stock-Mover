import copy
from functools import lru_cache

import pandas as pd
import pytest

from engine.data import lead_days, load_data
from engine.interfaces import build_features


@lru_cache(maxsize=1)
def _data():
    return load_data()


@pytest.fixture(scope="module")
def df():
    d = _data()
    return d, build_features(d)


def grp(gid, typ, frm, to, sku, qty, ship="2026-11-01", arr=None, lead=None, kind="UNDERSTOCK"):
    d = _data()
    lead = lead if lead is not None else lead_days(frm, to, d.stores)
    arr = arr or (pd.Timestamp(ship) + pd.Timedelta(days=lead)).strftime("%Y-%m-%d")
    style, size = sku.rsplit("-", 1)
    return {"group_id": gid, "type": typ, "problem_kind": kind, "style_id": style, "from": frm, "to": to,
            "ship_on": ship, "arrives_on": arr, "lead_days": lead, "qty": qty, "sizes": {size: qty},
            "lines": [{"sku_id": sku, "size": size, "qty": qty}]}


def rules_hit(df, groups):
    from engine.rules import validate
    return {v["rule"] for v in validate(*df, groups)["violations"]}


def with_vel(df, loc, prefix, vel):
    """Copy of (data, feats) with vel_daily forced for every SKU at `loc` whose id starts with `prefix`."""
    d, f = df
    f2 = copy.copy(f)
    sp = f.sku_pos.copy()
    sp.loc[(sp["location_id"] == loc) & sp["sku_id"].str.startswith(prefix), "vel_daily"] = vel
    f2.sku_pos = sp
    return d, f2


def test_empty_passes(df):
    from engine.rules import validate
    assert validate(*df, []) == {"passed": True, "checked_moves": 0, "violations": []}


def test_flagship_protected(df):
    assert "FLAGSHIP_PROTECTED" in rules_hit(df, [grp("G1", "STORE_TO_STORE", "LKO-01", "LKO-02", "KUR-02-L", 1)])


def test_capacity_into_knp03(df):
    assert "CAPACITY" in rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "KNP-03", "KUR-09-XL", 1)])


def test_min_display_giver(df):
    # MZF-01 holds 3 of MOJ-01-9; Mojari total 5 < min 8
    assert "MIN_DISPLAY" in rules_hit(df, [grp("G1", "PULL_BACK", "MZF-01", "WH-KOL", "MOJ-01-9", 1)])


def test_wh_negative_by_date(df):
    assert "WH_NEGATIVE" in rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-01", "KUR-01-XL", 100)])


def test_lead_time(df):
    assert "LEAD_TIME" in rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-01", "KUR-09-XL", 1,
                                             arr="2026-11-02", lead=1)])


def test_non_positive(df):
    assert "NON_POSITIVE_QTY" in rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-01", "KUR-09-XL", 0)])


def test_round_trip(df):
    g = [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-02", "KUR-09-XL", 1),
         grp("G2", "PULL_BACK", "PAT-02", "WH-KOL", "KUR-09-XL", 1)]
    assert "ROUND_TRIP" in rules_hit(df, g)


def test_clean_move_passes(df):
    assert rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-02", "KUR-09-XL", 2)]) <= {"IN_TRANSIT"}


# ---- Review Focus cases ----

def test_store_below_min_may_receive(df):
    # MZF-01 Mojari 5 < 8 before any move; receiving Mojari is fine
    assert "MIN_DISPLAY" not in rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "MZF-01", "MOJ-01-9", 3,
                                                   kind="MIN_DISPLAY")])


def test_knp03_pull_out_is_fine(df):
    assert rules_hit(df, [grp("G1", "PULL_BACK", "KNP-03", "WH-KOL", "SHW-02-L", 200, kind="CAPACITY")]) == set()


def test_knp03_inbound_after_pullout_still_over(df):
    g = [grp("G1", "PULL_BACK", "KNP-03", "WH-KOL", "SHW-02-L", 100, kind="CAPACITY"),
         grp("G2", "WH_TO_STORE", "WH-KOL", "KNP-03", "KUR-09-XL", 1, ship="2026-11-02")]
    from engine.rules import validate
    v = validate(*df, g)["violations"]
    assert [x["group_id"] for x in v if x["rule"] == "CAPACITY"] == ["G2"]


def test_wh_send_fits_after_inbound_date(df):
    # WH holds 15 KUR-01-XL; 190 arrive 2026-11-03. 100 shipped on 11-03 fits.
    assert "WH_NEGATIVE" not in rules_hit(df, [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-01", "KUR-01-XL", 100,
                                                   ship="2026-11-03")])


def test_wh_cumulative_sends(df):
    g = [grp("G1", "WH_TO_STORE", "WH-KOL", "PAT-01", "KUR-01-XL", 10),
         grp("G2", "WH_TO_STORE", "WH-KOL", "PAT-02", "KUR-01-XL", 10)]
    from engine.rules import validate
    v = validate(*df, g)["violations"]
    assert [x["group_id"] for x in v if x["rule"] == "WH_NEGATIVE"] == ["G2"]


def test_negative_stock_giver(df):
    # PAT-02 holds 14 KUR-09-XL
    assert "NEGATIVE_STOCK" in rules_hit(df, [grp("G1", "PULL_BACK", "PAT-02", "WH-KOL", "KUR-09-XL", 15)])
    assert "NEGATIVE_STOCK" not in rules_hit(df, [grp("G1", "PULL_BACK", "PAT-02", "WH-KOL", "KUR-09-XL", 14)])


def test_donor_cover_zero_velocity_passes(df):
    d = with_vel(df, "PAT-02", "KUR-09-", 0.0)
    assert "DONOR_COVER" not in rules_hit(d, [grp("G1", "STORE_TO_STORE", "PAT-02", "PAT-03", "KUR-09-XL", 2)])


def test_donor_cover_low_cover_blocks(df):
    d = with_vel(df, "PAT-02", "KUR-09-", 5.0)   # PAT-02 KUR-09 cover << 30 days
    assert "DONOR_COVER" in rules_hit(d, [grp("G1", "STORE_TO_STORE", "PAT-02", "PAT-03", "KUR-09-XL", 2)])
    # pull-backs are not store-to-store transfers
    assert "DONOR_COVER" not in rules_hit(d, [grp("G1", "PULL_BACK", "PAT-02", "WH-KOL", "KUR-09-XL", 2)])


def test_in_transit_double_send(df):
    # BLR-01 KUR-14-M: on hand 1 + in transit 1; with zero demand that already covers the target
    d = with_vel(df, "BLR-01", "KUR-14-", 0.0)
    assert "IN_TRANSIT" in rules_hit(d, [grp("G1", "WH_TO_STORE", "WH-KOL", "BLR-01", "KUR-14-M", 1)])
    assert "IN_TRANSIT" not in rules_hit(d, [grp("G1", "WH_TO_STORE", "WH-KOL", "BLR-01", "KUR-14-M", 1,
                                                 kind="MIN_DISPLAY")])


def test_violation_shape_and_checked_moves(df):
    from engine.rules import validate
    g = [grp("G1", "WH_TO_STORE", "WH-KOL", "KNP-03", "KUR-09-XL", 1),
         grp("G2", "WH_TO_STORE", "WH-KOL", "PAT-02", "KUR-09-XL", 2)]
    out = validate(*df, g)
    assert out["checked_moves"] == 2 and out["passed"] is False
    for v in out["violations"]:
        assert set(v) == {"rule", "group_id", "detail"} and "\n" not in v["detail"]
