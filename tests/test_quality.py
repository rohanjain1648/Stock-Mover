import re

import pytest

from engine.data import load_data
from engine.interfaces import build_features

SOLD_OUT = {"KUR-12", "KUR-15", "KUR-18", "KUR-24", "MOJ-03", "MOJ-06", "JKT-06", "STL-03"}


@pytest.fixture(scope="module")
def flags():
    d = load_data()
    from engine.quality import find_flags
    return find_flags(d, build_features(d))


def kinds(flags, kind, key):
    return {f[key] for f in flags if f["kind"] == kind}


def test_negative_stock_flag(flags):
    assert ("MYS-02", "KUR-02-M") in {(f["location_id"], f["sku_id"]) for f in flags if f["kind"] == "DATA_QUALITY"}


def test_sold_out_styles_are_reorder_not_dead(flags):
    assert SOLD_OUT <= kinds(flags, "REORDER", "style_id")
    assert not SOLD_OUT & kinds(flags, "DEAD_STOCK", "style_id")


def test_jkt08_dead(flags):
    assert "JKT-08" in kinds(flags, "DEAD_STOCK", "style_id")
    assert "KUR-01" not in kinds(flags, "DEAD_STOCK", "style_id")


def test_new_store_and_capacity(flags):
    assert "BLR-05" in kinds(flags, "NEW_STORE", "location_id")
    assert kinds(flags, "CAPACITY", "location_id") == {"KNP-03"}


def test_flag_shape(flags):
    for f in flags:
        assert set(f) == {"flag_id", "kind", "location_id", "sku_id", "style_id", "message"}
        assert "\n" not in f["message"]


# ---- extra checks ----

def test_flag_ids_sequential_and_kinds_valid(flags):
    from engine import config as C
    assert [f["flag_id"] for f in flags] == [f"F{i:03d}" for i in range(1, len(flags) + 1)]
    assert {f["kind"] for f in flags} <= set(C.FLAG_KINDS)


def test_inbound_styles_not_reorder(flags):
    # KUR-01 and SHW-01 are scarce but have warehouse inbound -> allocation problem, not a buyer reorder
    assert not {"KUR-01", "SHW-01"} & kinds(flags, "REORDER", "style_id")


def test_zero_day_sales_flags_total_191(flags):
    msgs = [f["message"] for f in flags if f["kind"] == "DATA_QUALITY" and f["sku_id"] is None]
    assert len(msgs) == 18
    assert sum(int(re.search(r"(\d+) units? sold", m).group(1)) for m in msgs) == 191


def test_messages_carry_numbers(flags):
    for f in flags:
        assert re.search(r"\d", f["message"]), f
