"""De-censored, season-adjusted velocity. Owned by S1.

compute_velocity(data) -> one row per store x non-packaging SKU (VEL_COLS), where
vel_daily = forecast units/day for the next ~30 days:

    base      = in-stock-day rate, shrunk toward a peer / style prior when sparse,
                or a peer / history / new-store estimate when never in stock in the window
    vel_daily = base x season lift (per state, LY festive season vs TY window, YoY-trended)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import config as C
from engine.data import Data


def _units_per_day(sales: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Units/day per state over the inclusive date range [start, end]."""
    s = sales[(sales["date"] >= start) & (sales["date"] <= end)]
    days = (end - start).days + 1
    return s.groupby("state")["qty"].sum() / days


def season_lift(data: Data) -> dict[str, float]:
    """lift[state] = (LY festive rate x YoY trend) / TY 84-day window rate, clipped to [LIFT_MIN, LIFT_MAX]."""
    as_of = data.as_of
    sales = data.sales.merge(data.stores[["store_id", "state"]], on="store_id")
    states = sorted(data.stores["state"].unique())

    cal = data.calendar
    ly_year = as_of.year - 1
    diwali = cal[(cal["festival"] == "Diwali") & (cal["date"].dt.year == ly_year)]
    diwali_by_state = diwali.groupby("state")["date"].min()
    any_diwali = diwali["date"].min()

    win_end = as_of
    win_start = as_of - pd.Timedelta(days=C.VELOCITY_WINDOW_DAYS - 1)
    ty_rate = _units_per_day(sales, win_start, win_end)

    ty_off = _units_per_day(sales, pd.Timestamp(as_of.year, 8, 1), pd.Timestamp(as_of.year, 9, 30))
    ly_off = _units_per_day(sales, pd.Timestamp(ly_year, 8, 1), pd.Timestamp(ly_year, 9, 30))

    out: dict[str, float] = {}
    for st in states:
        d = diwali_by_state.get(st, any_diwali)
        ly_fest = _units_per_day(sales, d - pd.Timedelta(days=10), d + pd.Timedelta(days=41)).get(st, 0.0)
        trend = ty_off.get(st, 0.0) / ly_off[st] if ly_off.get(st, 0.0) > 0 else 1.0
        ty = ty_rate.get(st, 0.0)
        raw = ly_fest * trend / ty if ty > 0 else C.LIFT_MIN
        out[st] = float(min(C.LIFT_MAX, max(C.LIFT_MIN, raw)))
    return out


BASIS = ("instock", "shrunk", "peer", "history", "new_store_peer", "not_ranged")
SHRINK_K = 28            # pseudo-days of prior: w = in_stock_days / (in_stock_days + SHRINK_K)
MIN_TRUST_DAYS = 7       # in-stock days needed before rate_instock is trusted on its own
NEW_STORE_DAYS = 90      # store opened within this many days of as_of -> peer-based (BLR-05)
NEW_STYLE_DAYS = 60      # style launched within this many days -> peer demand even where never stocked


def _in_stock_days(data: Data, win: pd.DataFrame) -> pd.DataFrame:
    """Per store x SKU over the window:
    in_stock_days = sum over weeks of max(weekly days_in_stock, distinct sale days that week), capped 7/week;
    eff_days      = the same days weighted by the state's weekly season index (week units/day / window units/day),
                    so a SKU stocked only in the pre-Diwali weeks is not credited with the festive bump twice."""
    as_of = data.as_of
    s = win[["store_id", "sku_id", "date", "qty"]].copy()
    s["week_ending"] = as_of - pd.to_timedelta(((as_of - s["date"]).dt.days // 7) * 7, unit="D")
    sale_days = s.groupby(["store_id", "sku_id", "week_ending"])["date"].nunique().rename("sale_days")
    wk = data.weekly[data.weekly["week_ending"] > as_of - pd.Timedelta(days=C.VELOCITY_WINDOW_DAYS)]
    dis = wk.groupby(["store_id", "sku_id", "week_ending"])["days_in_stock"].sum()
    both = pd.concat([dis, sale_days], axis=1).fillna(0)
    both["d"] = both[["days_in_stock", "sale_days"]].max(axis=1).clip(upper=7)

    state = data.stores.set_index("store_id")["state"]
    s["state"] = s["store_id"].map(state)
    wk_units = s.groupby(["state", "week_ending"])["qty"].sum()
    idx = (wk_units / wk_units.groupby(level="state").transform("mean")).rename("idx")
    both = both.reset_index()
    both["state"] = both["store_id"].map(state)
    both = both.merge(idx.reset_index(), on=["state", "week_ending"], how="left").fillna({"idx": 1.0})
    both["e"] = both["d"] * both["idx"]
    return both.groupby(["store_id", "sku_id"]).agg(in_stock_days=("d", "sum"), eff_days=("e", "sum")).reset_index()


def _peer_mean(v: pd.DataFrame, col: str, mask: pd.Series, keys: list[str], exclude_self: bool) -> pd.Series:
    """Mean of v[col] over rows where mask, grouped by keys, aligned to every row of v (optionally leaving the row out)."""
    x = v[col].where(mask, 0.0)
    n = mask.astype(float)
    g_sum = x.groupby([v[k] for k in keys]).transform("sum")
    g_n = n.groupby([v[k] for k in keys]).transform("sum")
    if exclude_self:
        g_sum, g_n = g_sum - x, g_n - n
    return (g_sum / g_n).where(g_n > 0)


def compute_velocity(data: Data) -> pd.DataFrame:
    from engine.interfaces import VEL_COLS

    as_of = data.as_of
    start = as_of - pd.Timedelta(days=C.VELOCITY_WINDOW_DAYS)          # window = (start, as_of]
    sales = data.sales
    win = sales[(sales["date"] > start) & (sales["date"] <= as_of)]

    st = data.stores.set_index("store_id")
    new_stores = set(st.index[st["opened_on"] > as_of - pd.Timedelta(days=NEW_STORE_DAYS)])
    items = data.items[["sku_id", "style_id", "launch_date"]]

    v = pd.MultiIndex.from_product([data.stores["store_id"], data.items["sku_id"]],
                                   names=["store_id", "sku_id"]).to_frame(index=False)
    v = v.merge(items, on="sku_id")
    v["tier"] = v["store_id"].map(st["tier"])
    v["zone"] = v["store_id"].map(st["zone"])
    v["state"] = v["store_id"].map(st["state"])
    v["is_new_store"] = v["store_id"].isin(new_stores)

    sold = win.groupby(["store_id", "sku_id"])["qty"].sum().rename("sold_84").reset_index()
    v = v.merge(sold, on=["store_id", "sku_id"], how="left").merge(
        _in_stock_days(data, win), on=["store_id", "sku_id"], how="left")
    v[["sold_84", "in_stock_days"]] = v[["sold_84", "in_stock_days"]].fillna(0).astype(int)
    v["eff_days"] = v["eff_days"].fillna(0.0)
    isd = v["in_stock_days"]

    # 1-2. in-stock-day rate (trusted from 7 days). rate_instock (shown) = sold / in-stock days;
    #      rate_adj (used for base) = sold / season-weighted in-stock days, i.e. in window-average units.
    v["rate_instock"] = (v["sold_84"] / isd.where(isd >= MIN_TRUST_DAYS)).fillna(0.0)
    v["rate_raw"] = (v["sold_84"] / v["eff_days"].where(v["eff_days"] > 0)).fillna(0.0)
    v["rate_adj"] = v["rate_raw"].where(isd >= MIN_TRUST_DAYS, 0.0)

    # 3. prior: same tier+zone peers (trusted rows, leave-one-out) -> same tier -> style rate x size share
    trusted = (isd >= MIN_TRUST_DAYS) & ~v["is_new_store"]
    prior = _peer_mean(v, "rate_adj", trusted, ["sku_id", "tier", "zone"], True)
    prior = prior.fillna(_peer_mean(v, "rate_adj", trusted, ["sku_id", "tier"], True))

    y = sales[(sales["date"] > as_of - pd.Timedelta(days=365)) & (sales["date"] <= as_of)]
    sku_365 = y.groupby("sku_id")["qty"].sum()
    style_365 = y.groupby("style_id")["qty"].sum()
    n_sizes = items.groupby("style_id")["sku_id"].transform("count")
    share = (v["sku_id"].map(sku_365) / v["style_id"].map(style_365)).fillna(1.0 / v["sku_id"].map(
        dict(zip(items["sku_id"], n_sizes))))
    sty = v.groupby(["store_id", "style_id"]).agg(s_sold=("sold_84", "sum"), s_isd=("eff_days", "max"))
    sty_rate = (sty["s_sold"] / sty["s_isd"].where(sty["s_isd"] > 0)).fillna(0.0)
    style_prior = pd.Series(sty_rate.reindex(pd.MultiIndex.from_frame(v[["store_id", "style_id"]])).values,
                            index=v.index) * share
    prior = prior.fillna(style_prior).fillna(0.0)

    w = isd / (isd + SHRINK_K)
    v["base"] = (w * v["rate_raw"] + (1 - w) * prior).where(isd > 0, 0.0)
    v["basis"] = np.where(w >= 0.5, "instock", "shrunk")

    # 4. never in stock in the window
    zero = (isd == 0) & ~v["is_new_store"]
    evidence = (isd > 0) & ~v["is_new_store"]
    peer = _peer_mean(v, "base", evidence, ["sku_id", "tier", "zone"], False)
    peer = peer.where(peer > 0).fillna(_peer_mean(v, "base", evidence, ["sku_id", "tier"], False)).fillna(0.0)

    launch = items.groupby("style_id")["launch_date"].min()
    new_style = v["style_id"].map(launch) > as_of - pd.Timedelta(days=NEW_STYLE_DAYS)
    sold_style = set(zip(y["store_id"], y["style_id"]))
    ranged = pd.Series([(a, b) in sold_style for a, b in zip(v["store_id"], v["style_id"])], index=v.index)
    eligible = zero & (new_style | ranged)

    # history: own 365-d rate before the window, put in window-average units (that year holds a festive
    # season, so divide by the state's 365-d-rate / window-rate ratio) -- the lift then adds the season once.
    pre = sales[(sales["date"] > start - pd.Timedelta(days=365)) & (sales["date"] <= start)]
    st_state = st["state"]
    pre_rate = pre.groupby(pre["store_id"].map(st_state))["qty"].sum() / 365.0
    win_rate = win.groupby(win["store_id"].map(st_state))["qty"].sum() / C.VELOCITY_WINDOW_DAYS
    norm = (pre_rate / win_rate).where(lambda r: r > 0).fillna(1.0)
    own = pre.groupby(["store_id", "sku_id"])["qty"].sum()
    hist = pd.Series(own.reindex(pd.MultiIndex.from_frame(v[["store_id", "sku_id"]])).fillna(0).values,
                     index=v.index) / 365.0 / v["state"].map(norm).fillna(1.0)

    use_peer = eligible & (peer > 0)
    use_hist = eligible & ~use_peer
    v.loc[use_peer, "base"] = peer[use_peer]
    v.loc[use_peer, "basis"] = "peer"
    v.loc[use_hist, "base"] = hist[use_hist]
    v.loc[use_hist, "basis"] = "history"
    v.loc[zero & ~eligible, ["base", "basis"]] = [0.0, "not_ranged"]

    # 4a. new store: peers' final base (same tier+zone, else same tier) x capacity ratio
    if new_stores:
        old = ~v["is_new_store"]
        nsp = _peer_mean(v, "base", old, ["sku_id", "tier", "zone"], False)
        nsp = nsp.where(nsp > 0).fillna(_peer_mean(v, "base", old, ["sku_id", "tier"], False)).fillna(0.0)
        peer_cap = {(t, z): st.loc[(st["tier"] == t) & ~st.index.isin(new_stores), "capacity"].mean()
                    for t, z in zip(st["tier"], st["zone"])}
        ratio = v["store_id"].map(st["capacity"]) / pd.Series(
            [peer_cap[(t, z)] for t, z in zip(v["tier"], v["zone"])], index=v.index)
        ns = v["is_new_store"]
        v.loc[ns, "base"] = (nsp * ratio.fillna(1.0))[ns]
        v.loc[ns, "basis"] = "new_store_peer"

    # 5. season lift
    lift = season_lift(data)
    v["lift"] = v["state"].map(lift).fillna(C.LIFT_MIN)
    v["vel_daily"] = (v["base"] * v["lift"]).fillna(0.0).clip(lower=0.0)
    return v[VEL_COLS].reset_index(drop=True)
