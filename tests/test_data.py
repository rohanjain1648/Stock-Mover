"""Smoke tests for the shared loader and orchestration. Owned by S0."""
import pytest

from engine import config as C
from engine.data import lead_days, load_data, protected_styles


@pytest.fixture(scope="module")
def data():
    return load_data()


def test_as_of_and_shapes(data):
    assert str(data.as_of.date()) == "2026-10-31"
    assert len(data.stores) == 20
    assert len(data.items) == 382                      # 385 minus 3 packaging rows
    assert not data.sales["sku_id"].str.startswith("PKG").any()


def test_negative_stock_clipped_but_kept(data):
    r = data.snapshot[(data.snapshot.location_id == "MYS-02") & (data.snapshot.sku_id == "KUR-02-M")].iloc[0]
    assert r.on_hand == 0 and r.on_hand_raw == -4


def test_lead_days(data):
    assert lead_days(C.WH_ID, "PAT-01", data.stores) == 3
    assert lead_days(C.WH_ID, "LKO-01", data.stores) == 4
    assert lead_days("BLR-05", C.WH_ID, data.stores) == 6
    assert lead_days("LKO-01", "LKO-03", data.stores) == 2
    assert lead_days("LKO-01", "KNP-03", data.stores) == 4
    assert lead_days("PAT-01", "BLR-01", data.stores) == 7


def test_protected(data):
    p = protected_styles(data)
    assert ("LKO-01", "KUR-02") in p and len(p) == 80


def test_engine_runs_end_to_end(tmp_path):
    from engine.run import run_engine
    run = run_engine(trigger="test", strict=False, out_dir=tmp_path)
    assert run["as_of"] == "2026-10-31" and len(run["stores"]) == 20
    assert (tmp_path / "latest.json").exists()
