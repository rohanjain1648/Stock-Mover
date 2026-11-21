import re
import time

import pytest

from engine import config as C
from engine import explain as X
from engine.data import load_data
from engine.explain import evidence_for, explain_group
from engine.interfaces import build_features

EV_KEYS = {"from_cover_before", "from_cover_after", "to_cover_before", "to_cover_after",
           "to_vel_daily", "from_vel_daily", "lift", "age_days", "to_capacity_after"}


@pytest.fixture(scope="module")
def data():
    return load_data()


@pytest.fixture(scope="module")
def feats(data):
    return build_features(data)


def g(**kw):
    base = {"type": "WH_TO_STORE", "problem_kind": "UNDERSTOCK", "style_id": "KUR-09", "style_name": "x",
            "category": "Kurta Set", "from": "WH-KOL", "to": "PAT-02", "sizes": {"XL": 2}, "qty": 2,
            "mrp_value": 0, "lines": [{"sku_id": "KUR-09-XL", "size": "XL", "qty": 2}],
            "ship_on": "2026-11-01", "arrives_on": "2026-11-04", "lead_days": 3}
    base.update(kw)
    return base


def one(style, size, qty, **kw):
    return g(style_id=style, sizes={size: qty}, qty=qty,
             lines=[{"sku_id": f"{style}-{size}", "size": size, "qty": qty}], **kw)


S2S = {"type": "STORE_TO_STORE", "ship_on": "2026-11-01", "arrives_on": "2026-11-05", "lead_days": 4}
ALL_KINDS = [
    one("SHW-02", "L", 40, problem_kind="CAPACITY", category="Sherwani", **S2S, **{"from": "KNP-03", "to": "LKO-01"}),
    one("SHW-02", "L", 195, problem_kind="CAPACITY", category="Sherwani", type="PULL_BACK",
        **{"from": "KNP-03", "to": "WH-KOL"}, arrives_on="2026-11-05", lead_days=4),
    one("KUR-07", "M", 6, problem_kind="OVERSTOCK", **S2S, **{"from": "BLR-03", "to": "BLR-01"}),
    one("KUR-09", "XL", 2, problem_kind="UNDERSTOCK"),
    one("KUR-09", "XL", 2, problem_kind="UNDERSTOCK", **S2S, **{"from": "PAT-01", "to": "PAT-02"}),
    one("KUR-01", "L", 4, problem_kind="SCARCITY", to="LKO-01"),
    one("KUR-04", "L", 5, problem_kind="NEW_LAUNCH", to="LKO-01", arrives_on="2026-11-05", lead_days=4),
    one("MOJ-01", "8", 3, problem_kind="MIN_DISPLAY", category="Mojari", to="MZF-01"),
    one("IW-08", "M", 3, problem_kind="AGEING", category="Indo-Western", **S2S, **{"from": "PAT-01", "to": "PAT-02"}),
    one("JKT-08", "M", 2, problem_kind="SOLD_OUT_CONSOLIDATION", category="Jacket", **S2S,
        **{"from": "BLR-03", "to": "BLR-01"}),
]


def test_capacity_pullback(data, feats):
    e = explain_group(g(type="PULL_BACK", problem_kind="CAPACITY", style_id="SHW-02", category="Sherwani",
                        **{"from": "KNP-03", "to": "WH-KOL"}, sizes={"L": 195}, qty=195,
                        lines=[{"sku_id": "SHW-02-L", "size": "L", "qty": 195}], arrives_on="2026-11-05",
                        lead_days=4), data, feats)
    assert e.startswith("KNP-03 → WH · 195 × SHW-02 (L195): ") and "208%" in e and "300" in e
    assert "130%" in e and "12 Dec" in e


def test_new_launch(data, feats):
    e = explain_group(g(problem_kind="NEW_LAUNCH", style_id="KUR-04", to="LKO-01", sizes={"L": 5}, qty=5,
                        lines=[{"sku_id": "KUR-04-L", "size": "L", "qty": 5}], arrives_on="2026-11-05",
                        lead_days=4), data, feats)
    assert "KUR-04" in e and "LKO-01" in e and "new launch" in e and "20 Sep" in e


def test_understock_wh_numbers(data, feats):
    e = explain_group(ALL_KINDS[3], data, feats)
    assert e.startswith("WH → PAT-02 · 2 × KUR-09 (XL2): ") and "festive lift" in e and "4 Nov" in e


def test_min_display(data, feats):
    e = explain_group(ALL_KINDS[7], data, feats)
    assert "Mojari" in e and "minimum display" in e


@pytest.mark.parametrize("grp", ALL_KINDS, ids=[f"{x['problem_kind']}-{x['type']}" for x in ALL_KINDS])
def test_shape_all_kinds(grp, data, feats):
    e = explain_group(grp, data, feats)
    assert "\n" not in e and len(e) <= 220
    assert f"· {grp['qty']} × {grp['style_id']} (" in e
    reason = e.split("): ", 1)[1]
    assert len(re.findall(r"\d+(?:\.\d+)?", reason)) >= 2, e
    assert not re.search(r"\bvel|basis|nan|inf|None\b", reason, re.I), e
    ev = evidence_for(grp, data, feats)
    assert set(ev) == EV_KEYS
    assert all(v is None or isinstance(v, float) for v in ev.values()), ev


def test_evidence_capacity_pullback(data, feats):
    ev = evidence_for(ALL_KINDS[1], data, feats)
    assert ev["to_cover_before"] is None and ev["to_cover_after"] is None and ev["to_vel_daily"] is None
    assert ev["to_capacity_after"] is None and ev["age_days"] == 809.0
    assert ev["from_cover_before"] > ev["from_cover_after"] > 0
    assert ev["lift"] is not None and C.LIFT_MIN <= ev["lift"] <= C.LIFT_MAX


def test_evidence_wh_to_store(data, feats):
    ev = evidence_for(ALL_KINDS[6], data, feats)
    assert ev["from_cover_before"] is None and ev["from_vel_daily"] is None and ev["age_days"] is None
    assert ev["to_cover_after"] > ev["to_cover_before"]
    assert ev["to_capacity_after"] == pytest.approx((934 + 5) / 1200, abs=0.01)


@pytest.mark.parametrize("kind", ["OVERSTOCK", "AGEING", "SOLD_OUT_CONSOLIDATION"])
def test_pullback_never_says_wh_sells(kind, data, feats):
    grp = one("KUR-07", "M", 16, problem_kind=kind, type="PULL_BACK", **{"from": "BLR-03", "to": "WH-KOL"})
    e = explain_group(grp, data, feats)
    assert e.startswith("BLR-03 → WH · 16 × KUR-07 (M16): ")
    assert "WH sells" not in e and "WH-KOL" not in e and "0.0/day" not in e, e


def test_700_groups_under_1s(data, feats):
    X._CACHE.clear()
    t = time.perf_counter()
    for i in range(700):
        grp = ALL_KINDS[i % len(ALL_KINDS)]
        explain_group(grp, data, feats)
        evidence_for(grp, data, feats)
    assert time.perf_counter() - t < 1.0
