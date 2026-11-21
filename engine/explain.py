"""One-line merchandiser explanations + evidence numbers for move groups. Owned by S1.

Everything is read from the START state (feats + data), never from S2's ledger, so each line says why the
move was needed, not what the plan looks like after it. Lookups are built once per Features object.
"""
from __future__ import annotations

import math

import pandas as pd

from engine import config as C
from engine.data import Data
from engine.interfaces import Features

MAX_LEN = 220
_CACHE: dict = {}


# ---------------------------------------------------------------- lookups (once per feats)
def _lookups(data: Data, feats: Features) -> dict:
    c = _CACHE.get("lk")
    if c is not None and c["feats"] is feats and c["data"] is data:
        return c
    p = feats.sku_pos
    st = p.groupby(["location_id", "style_id"]).agg(
        avail=("available", "sum"), vel=("vel_daily", "sum"), sold=("sold_84", "sum"), age=("age_days", "max"))
    sp = feats.store_pos.set_index("store_id")
    stores = data.stores.set_index("store_id")
    items = data.items
    cutoff = data.as_of + pd.Timedelta(days=max(C.LEAD_WH.values()) + C.REVIEW_DAYS + C.SAFETY_DAYS)
    tl = feats.wh_timeline[feats.wh_timeline["date"] <= cutoff]
    style_vel = p.groupby("style_id")["vel_daily"].sum()
    c = {
        "feats": feats, "data": data,
        "style_loc": {k: tuple(v) for k, v in zip(st.index, st[["avail", "vel", "sold", "age"]].to_numpy())},
        "sku_on_hand": dict(zip(zip(p["location_id"], p["sku_id"]), p["on_hand"])),
        "sku_loc": dict(zip(zip(p["location_id"], p["sku_id"]), zip(p["available"], p["vel_daily"]))),
        "units": sp["units"].to_dict(), "capacity": sp["capacity"].to_dict(), "util": sp["utilisation"].to_dict(),
        "lift": p.groupby("location_id")["lift"].first().to_dict(),
        "tier": stores["tier"].to_dict(),
        "cat_units": p.groupby(["location_id", "cat_group"])["available"].sum().to_dict(),
        "min_units": dict(zip(zip(data.min_display["tier"], data.min_display["cat_group"]),
                              data.min_display["min_units"])),
        "style_cat_group": items.groupby("style_id")["cat_group"].first().to_dict(),
        "launch": items.groupby("style_id")["launch_date"].min().to_dict(),
        "chain_vel": style_vel.to_dict(),
        "supply_by": cutoff,
        "supply": tl.groupby("sku_id")["cum_qty"].last().to_dict(),
        "need_stores": p[p["need_units"] > 0].groupby("sku_id")["location_id"].apply(set).to_dict(),
        "store_ids": list(sp.index),
    }
    _CACHE.clear()
    _CACHE["lk"] = c
    return c


def _sl(lk: dict, loc: str, style: str) -> tuple[float, float, float, float]:
    """(available, vel_daily, sold_84, max age_days) for a style at a location; zeros when unknown."""
    return lk["style_loc"].get((loc, style), (0, 0.0, 0, math.nan))


def _moved(lk: dict, g: dict, loc: str) -> tuple[int, float, str]:
    """(available, vel_daily, size label) at loc summed over the SKUs this group moves."""
    a = v = 0.0
    for ln in g["lines"]:
        sa, sv = lk["sku_loc"].get((loc, ln["sku_id"]), (0, 0.0))
        a, v = a + sa, v + sv
    return int(a), float(v), "/".join(str(s) for s in g["sizes"])


def _cover(avail: float, vel: float) -> float | None:
    return float(round(float(avail) / float(vel), 1)) if vel > 0 else None


def _r1(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 1)


# ---------------------------------------------------------------- evidence
def evidence_for(group: dict, data: Data, feats: Features) -> dict:
    lk = _lookups(data, feats)
    frm, to, style, qty = group["from"], group["to"], group["style_id"], int(group["qty"])
    ev = dict.fromkeys(["from_cover_before", "from_cover_after", "to_cover_before", "to_cover_after",
                        "to_vel_daily", "from_vel_daily", "lift", "age_days", "to_capacity_after"])
    if frm != C.WH_ID:
        a, v, _, age = _sl(lk, frm, style)
        ev["from_cover_before"], ev["from_cover_after"] = _cover(a, v), _cover(max(a - qty, 0), v)
        ev["from_vel_daily"], ev["age_days"] = _r1(v), _r1(age)
    if to != C.WH_ID:
        a, v, _, _ = _sl(lk, to, style)
        ev["to_cover_before"], ev["to_cover_after"] = _cover(a, v), _cover(a + qty, v)
        ev["to_vel_daily"] = _r1(v)
        cap = lk["capacity"].get(to)
        if cap:
            ev["to_capacity_after"] = float(round((lk["units"].get(to, 0) + qty) / cap, 2))
    lift_at = frm if group["type"] == "PULL_BACK" or to == C.WH_ID else to
    ev["lift"] = _r1(lk["lift"].get(lift_at))
    return ev


# ---------------------------------------------------------------- formatting helpers
def _loc(x: str) -> str:
    return "WH" if x == C.WH_ID else x


def _rate(v: float) -> str:
    if v <= 0:
        return "0"
    return "under 0.1" if v < 0.05 else f"{v:.1f}"


def _back_to_wh() -> str:
    return f"no store needs them before {_day(C.SEASON_END)}, so they go back to WH"


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _day(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.day} {d:%b}"


def _days(avail: float, vel: float) -> str | None:
    """'N days' of cover ('1 day', 'under a day'); None when nothing sells."""
    if vel <= 0:
        return None
    d = avail / vel
    if d < 1:
        return "under a day"
    n = round(d)
    return "1 day" if n == 1 else f"{n} days"


def _size_qty(s, q) -> str:
    """'L4'; numeric sizes get a separator so Mojari 8 x 3 reads '8×3', not '83'."""
    s = str(s)
    return f"{s}×{int(q)}" if s[-1:].isdigit() else f"{s}{int(q)}"


def _main_sku(group: dict) -> str:
    return max(group["lines"], key=lambda ln: ln["qty"])["sku_id"]


# ---------------------------------------------------------------- reasons, one per problem_kind
def _capacity(g, lk):
    frm, to, qty = g["from"], g["to"], int(g["qty"])
    sku = _main_sku(g)
    n = int(lk["sku_on_hand"].get((frm, sku), 0))
    util = lk["util"].get(frm, 0.0)
    head = f"{frm} holds {n} of {sku} (store at {_pct(util)} of capacity); "
    if g["type"] == "PULL_BACK" or to == C.WH_ID:
        units, cap = lk["units"].get(frm, 0), lk["capacity"][frm]
        after = (units - qty) / cap
        tail = (f"takes {frm} from {_pct(util)} to {_pct(after)} of capacity." if _pct(after) != _pct(util)
                else f"frees {qty} of the {int(units - cap)} units over capacity.")
        return head + f"no store needs them before {_day(C.SEASON_END)}; " + tail
    a, v, sz = _moved(lk, g, to)
    return head + f"{to} has {a} in {sz}, sells {_rate(v)}/day in festive season."


def _overstock(g, lk):
    frm, to, style = g["from"], g["to"], g["style_id"]
    fa, fv, fs, _ = _sl(lk, frm, style)
    ta, tv, sz = _moved(lk, g, to)
    fc = _days(fa, fv)
    left = f"{frm} has {fc} of cover" if fc else f"{frm} has {int(fa)} with {int(fs)} sold in 12 weeks"
    tc = _days(ta, tv)
    if to == C.WH_ID:
        right = f"{int(fa)} on hand; " + _back_to_wh() if fc else _back_to_wh()
    elif ta <= 0:
        right = f"{to} is out of {sz}, sells {_rate(tv)}/day"
    elif tc:
        right = f"{to} runs out of {sz} in {tc} ({ta} left)"
    else:
        right = f"{to} has {ta} in {sz}"
    return f"{left}; {right}."


def _understock(g, lk):
    frm, to, qty = g["from"], g["to"], int(g["qty"])
    a, v, sz = _moved(lk, g, to)
    lift = lk["lift"].get(to, 1.0)
    covers = _days(qty, v)
    s = f"{to} has {a} left in {sz}, sells {_rate(v)}/day (×{lift:.1f} festive lift); "
    s += (f"this covers {covers}" if covers else f"this adds {qty} units") + f", arriving {_day(g['arrives_on'])}."
    if frm != C.WH_ID:
        fa, fv, _ = _moved(lk, g, frm)
        keep = _days(max(fa - qty, 0), fv)
        s += f" {frm} keeps {keep} of cover." if keep else f" {frm} keeps {max(fa - qty, 0)}."
    return s


def _scarcity(g, lk):
    to = g["to"]
    skus = {ln["sku_id"] for ln in g["lines"]}
    supply = int(sum(lk["supply"].get(k, 0) for k in skus))
    n_stores = len(set().union(*(lk["need_stores"].get(k, set()) for k in skus)))
    a, v, sz = _moved(lk, g, to)
    return (f"only {supply} of {sz} arrive for {max(n_stores, 1)} stores by {_day(lk['supply_by'])}; "
            f"{to} gets its share — sells {_rate(v)}/day, has {a}.")


def _new_launch(g, lk):
    to, style = g["to"], g["style_id"]
    a, v, _, _ = _sl(lk, to, style)
    tier = lk["tier"].get(to)
    peers = [_sl(lk, s, style)[1] for s in lk["store_ids"] if s != to and lk["tier"].get(s) == tier]
    peers = [x for x in peers if x > 0] or [_sl(lk, s, style)[1] for s in lk["store_ids"] if s != to]
    peer = sum(peers) / len(peers) if peers else 0.0
    launch = lk["launch"].get(style)
    when = f" ({_day(launch)})" if pd.notna(launch) else ""
    return (f"new launch{when} selling {_rate(lk['chain_vel'].get(style, 0.0))}/day chain-wide; "
            f"{to} holds {int(a)}; similar stores sell {_rate(peer)}/day.")


def _min_display(g, lk):
    to, qty = g["to"], int(g["qty"])
    cg = lk["style_cat_group"].get(g["style_id"], g["category"])
    have = int(lk["cat_units"].get((to, cg), 0))
    mn = lk["min_units"].get((lk["tier"].get(to), cg))
    if mn is None:
        return f"{to} has {have} {cg}; this brings it to {have + qty}."
    return f"{to} has {have} {cg} vs minimum display {int(mn)}; this brings it to {have + qty}."


def _ageing(g, lk):
    frm, to, style = g["from"], g["to"], g["style_id"]
    _, _, fs, age = _sl(lk, frm, style)
    _, tv, _, _ = _sl(lk, to, style)
    old = f"{int(age)} days old at {frm}" if not math.isnan(age) else f"old stock at {frm}"
    right = _back_to_wh() if to == C.WH_ID else f"{to} sells {_rate(tv)}/day"
    return f"{old}, sold {int(fs)} there in 12 weeks; {right}."


def _sold_out(g, lk):
    frm, to, style = g["from"], g["to"], g["style_id"]
    _, _, fs, _ = _sl(lk, frm, style)
    _, tv, _, _ = _sl(lk, to, style)
    right = "back to WH to consolidate" if to == C.WH_ID else f"{to} sells {_rate(tv)}/day"
    return f"style sold out chain-wide, nothing inbound; {frm} sold {int(fs)} in 12 weeks, {right}."


def _generic(g, lk):
    a, v, _, _ = _sl(lk, g["to"], g["style_id"])
    return f"{_loc(g['to'])} has {int(a)}, sells {_rate(v)}/day."


_REASONS = {"CAPACITY": _capacity, "OVERSTOCK": _overstock, "UNDERSTOCK": _understock, "SCARCITY": _scarcity,
            "NEW_LAUNCH": _new_launch, "MIN_DISPLAY": _min_display, "AGEING": _ageing,
            "SOLD_OUT_CONSOLIDATION": _sold_out}


def explain_group(group: dict, data: Data, feats: Features) -> str:
    lk = _lookups(data, feats)
    sizes = " ".join(_size_qty(s, q) for s, q in group["sizes"].items())
    head = f"{_loc(group['from'])} → {_loc(group['to'])} · {int(group['qty'])} × {group['style_id']} ({sizes}): "
    reason = _REASONS.get(group["problem_kind"], _generic)(group, lk)
    line = head + reason
    return line if len(line) <= MAX_LEN else line[:MAX_LEN - 1] + "…"
