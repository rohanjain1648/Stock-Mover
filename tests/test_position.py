import pytest

from engine.data import load_data
from engine.interfaces import build_features, SKU_POS_COLS, STORE_POS_COLS


@pytest.fixture(scope="module")
def f():
    return build_features(load_data())


def test_columns(f):
    assert list(f.sku_pos.columns) == SKU_POS_COLS
    assert list(f.store_pos.columns) == STORE_POS_COLS
    assert set(f.sku_pos.basis) - {"instock", "shrunk", "peer", "history", "new_store_peer", "not_ranged"} == set()


def test_negative_stock_clipped(f):
    r = f.sku_pos[(f.sku_pos.location_id == "MYS-02") & (f.sku_pos.sku_id == "KUR-02-M")].iloc[0]
    assert r.on_hand == 0


def test_knp03_over_capacity(f):
    r = f.store_pos.set_index("store_id").loc["KNP-03"]
    assert r.utilisation == pytest.approx(520 / 250, rel=0.01)


def test_min_display_deficit_in_need(f):
    p = f.sku_pos
    assert p[(p.location_id == "MZF-01") & (p.cat_group == "Mojari")].need_units.sum() >= 3
    assert p[(p.location_id == "BLR-05") & (p.cat_group == "Sherwani")].need_units.sum() >= 3


def test_protected_never_excess(f):
    p = f.sku_pos
    assert (p[p.is_protected].excess_units == 0).all()
    assert p[(p.location_id == "LKO-01") & (p.style_id == "KUR-02")].is_protected.all()


def test_wh_timeline_kur04(f):
    t = f.wh_timeline[f.wh_timeline.sku_id.str.startswith("KUR-04-")]
    assert t.groupby("sku_id").cum_qty.max().sum() == 308 + 4378


def test_min_display_fully_covered_by_need(f):
    """Every store x cat_group: available + need_units reaches min display."""
    from engine.data import load_data
    md = load_data().min_display
    p = f.sku_pos.groupby(["location_id", "tier", "cat_group"])[["available", "need_units"]].sum().reset_index()
    p = p.merge(md, on=["tier", "cat_group"])
    short = p[p.available + p.need_units < p.min_units]
    assert short.empty, short.head().to_string()


def test_not_ranged_stock_is_all_excess(f):
    """vel-0 stock is all excess, except where releasing it would take the category below min display."""
    from engine.data import load_data
    md = load_data().min_display
    p = f.sku_pos
    g = p.groupby(["location_id", "tier", "cat_group"])[["available", "excess_units"]].sum().reset_index()
    g = g.merge(md, on=["tier", "cat_group"])
    free = g[g.available - g.excess_units > g.min_units][["location_id", "cat_group"]]
    nr = p[(p.vel_daily == 0) & ~p.is_protected].merge(free, on=["location_id", "cat_group"])
    assert len(nr) > 0
    assert (nr.excess_units == nr.available).all()


def test_age_days_nan_when_no_stock(f):
    p = f.sku_pos
    assert p.loc[p.on_hand == 0, "age_days"].isna().all() or p.loc[p.on_hand == 0, "age_days"].isna().mean() > 0.9


def test_excess_keeps_min_display(f):
    """Spec 5.3: donor excess = units above max(30 d cover, min-display share) -> taking all excess keeps min display."""
    from engine.data import load_data
    md = load_data().min_display
    p = f.sku_pos.groupby(["location_id", "tier", "cat_group"])[["available", "excess_units"]].sum().reset_index()
    p = p.merge(md, on=["tier", "cat_group"])
    bad = p[p.available - p.excess_units < p[["min_units", "available"]].min(axis=1)]
    assert bad.empty, bad.head().to_string()


def test_min_display_topup_round_robin():
    """Category below min with zero store velocity: deficit goes to chain best-sellers, one unit at a time."""
    import pandas as pd
    from engine.position import _min_display_topup
    p = pd.DataFrame({
        "location_id": ["S1"] * 3, "tier": ["B"] * 3, "cat_group": ["Mojari"] * 3,
        "sku_id": ["A", "B", "C"], "available": [1, 0, 0], "vel_daily": [0.0, 0.0, 0.0],
        "need_units": [0, 0, 0]})
    md = pd.DataFrame({"tier": ["B"], "cat_group": ["Mojari"], "min_units": [6]})
    chain = pd.Series({"A": 1.0, "B": 3.0, "C": 2.0})
    out = _min_display_topup(p, md, chain)
    assert out.need_units.sum() == 5
    assert dict(zip(out.sku_id, out.need_units)) == {"B": 2, "C": 2, "A": 1}
