import pytest

from engine import config as C
from engine.data import load_data


@pytest.fixture(scope="module")
def data():
    return load_data()


def test_season_lift_per_state(data):
    from engine.velocity import season_lift
    lift = season_lift(data)
    assert set(lift) == {"Uttar Pradesh", "Bihar", "Karnataka"}
    for v in lift.values():
        assert 1.5 <= v <= C.LIFT_MAX   # Nov is festive + wedding season everywhere


from engine.interfaces import VEL_COLS


@pytest.fixture(scope="module")
def vel(data):
    from engine.velocity import compute_velocity
    return compute_velocity(data)


def _row(vel, store, sku):
    return vel[(vel.store_id == store) & (vel.sku_id == sku)].iloc[0]


def test_grid_and_columns(vel):
    assert list(vel.columns) == VEL_COLS
    assert len(vel) == 20 * 382
    assert vel.vel_daily.notna().all() and (vel.vel_daily >= 0).all()


def test_instock_rate_is_decensored(vel):
    r = _row(vel, "LKO-02", "KUR-09-XXL")       # in stock only ~12 of 84 days, sold 3
    assert r.in_stock_days < 20
    assert r.rate_instock > r.sold_84 / 84 * 3


def test_new_launch_has_demand_where_missing(vel):
    lko = vel[(vel.store_id == "LKO-01") & vel.sku_id.str.startswith("KUR-04-")].vel_daily.sum()
    mzf = vel[(vel.store_id == "MZF-01") & vel.sku_id.str.startswith("KUR-04-")].vel_daily.sum()
    assert lko >= 1.0 and mzf > 0


def test_new_store_uses_peers(vel):
    assert (vel[vel.store_id == "BLR-05"].basis == "new_store_peer").all()


def test_sold_out_style_not_zero(vel):
    r = _row(vel, "LKO-01", "KUR-18-L")         # sold out chain-wide, sold well last year
    assert r.vel_daily > 0 and r.basis in {"history", "peer"}


def test_lift_bounds(vel):
    assert vel.lift.between(1.0, 3.5).all()


def test_chain_forecast_sanity(vel):
    lo, hi = C.CHAIN_DAILY_SANITY
    assert lo <= vel.vel_daily.sum() <= hi      # Nov 2025 ran 434/day; Aug-Oct 2026 ran 163/day
