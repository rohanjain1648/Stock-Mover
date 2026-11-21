"""Planted-problem acceptance tests (spec §5.10). Run the whole engine; must all pass before freeze."""
import pytest

from engine import config as C
from engine.run import run_engine

SOLD_OUT = {"KUR-12", "KUR-15", "KUR-18", "KUR-24", "MOJ-03", "MOJ-06", "JKT-06", "STL-03"}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return run_engine(trigger="test", strict=False, out_dir=tmp_path_factory.mktemp("out"))


def q(run, **kw):
    return sum(g["qty"] for g in run["groups"] if all(g[k] == v for k, v in kw.items()))


def flagged(run, kind, key):
    return {f[key] for f in run["flags"] if f["kind"] == kind}


def test_validation_passes(run):                       # P0: no rule broken
    assert run["validation"]["passed"], run["validation"]["violations"][:5]


def test_p1_knp03(run):
    assert q(run, **{"from": "KNP-03", "style_id": "SHW-02"}) >= 200
    assert q(run, to="KNP-03") == 0
    assert "KNP-03" in flagged(run, "CAPACITY", "location_id")


def test_p2_mzf01_topped_up(run):
    assert q(run, to="MZF-01") >= 20
    assert q(run, to="MZF-01", category="Mojari") >= 3     # Mojari 5 -> >= min display 8


def test_p3_kur04_new_launch(run):
    assert q(run, to="LKO-01", style_id="KUR-04") > 0 and q(run, to="MZF-01", style_id="KUR-04") > 0


def test_p4_kur01_shared(run):
    assert len({g["to"] for g in run["groups"] if g["style_id"] == "KUR-01" and g["type"] == "WH_TO_STORE"}) >= 8


def test_p5_sold_out_not_pulled_back(run):
    assert not [g for g in run["groups"] if g["style_id"] in SOLD_OUT and g["type"] == "PULL_BACK"]
    assert SOLD_OUT <= flagged(run, "REORDER", "style_id")
    assert not SOLD_OUT & flagged(run, "DEAD_STOCK", "style_id")


def test_p6_jkt08(run):
    assert any(g["style_id"] == "JKT-08" for g in run["groups"])
    assert "JKT-08" in flagged(run, "DEAD_STOCK", "style_id")


def test_p7_blr05_sherwani(run):
    assert q(run, to="BLR-05", category="Sherwani") >= 3   # Sherwani 2 -> >= min display 5
    assert "BLR-05" in flagged(run, "NEW_STORE", "location_id")


def test_p8_ageing_moves_exist(run):
    assert sum(1 for g in run["groups"] if g["problem_kind"] == "AGEING") >= 5


def test_p9_negative_stock_flag(run):
    assert any(f["kind"] == "DATA_QUALITY" and f["sku_id"] == "KUR-02-M" for f in run["flags"])


def test_p10_festive_lift_band(run):
    chain = sum(s["vel_daily"] or 0 for s in run["stores"])
    lo, hi = C.CHAIN_DAILY_SANITY
    assert lo <= chain <= hi, f"chain forecast {chain:.0f}/day outside {lo}-{hi}"


def test_p11_explanations_and_approval(run):
    for g in run["groups"]:
        assert g["explanation"] and "\n" not in g["explanation"]
        assert g["needs_approval"] == (g["mrp_value"] > C.APPROVAL_MRP_THRESHOLD)
