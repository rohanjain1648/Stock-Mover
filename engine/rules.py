"""Independent rule validator. Owned by S3.

Re-derives start stock from raw `Data` (never from the move generator's ledger), replays every
move line in `ship_on` order (same day: every give before every receipt, then group/line order)
and checks every rule in
spec §2 / §5.6. Written without reading engine/moves.py — independence is the point.

    validate(data, feats, groups) -> {"passed", "checked_moves", "violations": [{rule, group_id, detail}]}

Stock model: start = on_hand (clipped >= 0) + in_transit per store x SKU. A line debits the giver
and credits the receiver at `ship_on` (our own sends count as arriving, like in-transit stock).
WH-KOL supply on a date = WH on hand + inbound with expected_date <= date + pull-backs that have
arrived (arrives_on <= date).
"""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

from engine import config as C
from engine.data import Data, lead_days, protected_styles

WH = C.WH_ID


def _day(x) -> pd.Timestamp | None:
    try:
        t = pd.Timestamp(x)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(t) else t.normalize()


def _fmt(t: pd.Timestamp | None) -> str:
    return t.strftime("%Y-%m-%d") if t is not None else "?"


def _num(x: float) -> str:
    return "inf" if math.isinf(x) else f"{x:.1f}"


def _lines(g: dict) -> list[dict]:
    lines = g.get("lines")
    if lines:
        return lines
    style = g.get("style_id", "")
    return [{"sku_id": f"{style}-{size}", "size": size, "qty": q} for size, q in (g.get("sizes") or {}).items()]


def validate(data: Data, feats, groups: list[dict]) -> dict:
    stores = data.stores.set_index("store_id")
    store_ids = set(stores.index)
    items = data.items.set_index("sku_id")
    sku_style = items["style_id"].to_dict()
    sku_cat = items["cat_group"].to_dict()
    min_units = {(t, c): int(m) for t, c, m in data.min_display[["tier", "cat_group", "min_units"]].itertuples(index=False)}
    protected = protected_styles(data)

    snap = data.snapshot
    st_snap = snap[snap["location_id"].isin(store_ids)]
    stock: dict[tuple[str, str], int] = defaultdict(int)       # store x SKU, replayed
    in_transit: dict[tuple[str, str], int] = {}
    for loc, sku, oh, it in st_snap[["location_id", "sku_id", "on_hand", "in_transit"]].itertuples(index=False):
        stock[(loc, sku)] += int(oh) + int(it)
        in_transit[(loc, sku)] = int(it)
    store_total: dict[str, int] = defaultdict(int)
    cat_total: dict[tuple[str, str], int] = defaultdict(int)
    style_total: dict[tuple[str, str], int] = defaultdict(int)
    for (loc, sku), q in stock.items():
        store_total[loc] += q
        cat_total[(loc, sku_cat.get(sku))] += q
        style_total[(loc, sku_style.get(sku))] += q

    sp = feats.sku_pos
    vel = {(a, b): float(v) for a, b, v in sp[["location_id", "sku_id", "vel_daily"]].itertuples(index=False)}
    style_vel: dict[tuple[str, str], float] = defaultdict(float)
    for (loc, sku), v in vel.items():
        style_vel[(loc, sku_style.get(sku))] += v

    wh_on_hand = {sku: int(q) for sku, q in snap.loc[snap["location_id"] == WH, ["sku_id", "on_hand"]].itertuples(index=False)}
    inbound = [(_day(d), sku, int(q)) for d, sku, q in data.inbound[["expected_date", "sku_id", "qty"]].itertuples(index=False)]

    violations: list[dict] = []

    def flag(rule: str, gid, detail: str) -> None:
        violations.append({"rule": rule, "group_id": gid, "detail": detail.replace("\n", " ")})

    # ---- flatten to lines; group-level checks (lead time) ----
    events = []   # (ship_day, group_idx, line_idx, group, line)
    pullback_arrivals = []   # (arrive_day, sku, qty) into WH
    for gi, g in enumerate(groups):
        gid, frm, to = g.get("group_id"), g.get("from"), g.get("to")
        ship, arr = _day(g.get("ship_on")), _day(g.get("arrives_on"))
        try:
            lead = lead_days(frm, to, data.stores)
        except KeyError:
            lead = None
        if lead is None or ship is None or arr is None:
            flag("LEAD_TIME", gid, f"{frm} -> {to}: unknown route or bad dates (ship {g.get('ship_on')}, arrive {g.get('arrives_on')})")
        else:
            gap = (arr - ship).days
            if gap != lead or g.get("lead_days") != lead:
                flag("LEAD_TIME", gid, f"{frm} -> {to}: lead time is {lead} days but group says lead_days "
                                       f"{g.get('lead_days')}, ship {_fmt(ship)} -> arrive {_fmt(arr)} ({gap} days)")
        for li, ln in enumerate(_lines(g)):
            events.append((ship if ship is not None else pd.Timestamp.max, gi, li, g, ln))
            if to == WH and frm != WH and arr is not None and int(ln.get("qty", 0)) > 0:
                pullback_arrivals.append((arr, ln["sku_id"], int(ln["qty"])))
    events.sort(key=lambda e: (e[0], e[1], e[2]))

    def wh_supply(sku: str, day: pd.Timestamp) -> int:
        return (wh_on_hand.get(sku, 0)
                + sum(q for d, s, q in inbound if s == sku and d is not None and d <= day)
                + sum(q for d, s, q in pullback_arrivals if s == sku and d <= day))

    # ---- ROUND_TRIP: same store x SKU both gives and receives in this run ----
    gives: dict[tuple[str, str], list] = defaultdict(list)
    gets: dict[tuple[str, str], list] = defaultdict(list)
    for _, _, _, g, ln in events:
        if g.get("from") in store_ids:
            gives[(g["from"], ln["sku_id"])].append(g.get("group_id"))
        if g.get("to") in store_ids:
            gets[(g["to"], ln["sku_id"])].append(g.get("group_id"))
    for key in sorted(set(gives) & set(gets)):
        loc, sku = key
        flag("ROUND_TRIP", gets[key][0], f"{loc} {sku} is sent stock (groups {', '.join(map(str, gets[key]))}) "
                                         f"and gives stock (groups {', '.join(map(str, gives[key]))}) in the same run")

    # ---- replay: per ship day, every give (debit) before every receipt (credit) ----
    # A receipt shipped on day D lands at D + lead (>= 2 days), so it can never fund a give on D;
    # this also makes the verdict independent of the order groups are listed in.
    replay = sorted(((e[0], phase, e[1], e[2], e[3], e[4]) for e in events for phase in (0, 1)),
                    key=lambda r: r[:4])
    wh_sent: dict[str, int] = defaultdict(int)
    for ship, phase, _, _, g, ln in replay:
        gid, frm, to, kind = g.get("group_id"), g.get("from"), g.get("to"), g.get("problem_kind")
        sku, qty = ln.get("sku_id"), int(ln.get("qty", 0))
        style, cat = sku_style.get(sku, g.get("style_id")), sku_cat.get(sku)
        if qty <= 0:
            if phase == 0:
                flag("NON_POSITIVE_QTY", gid, f"{frm} -> {to} {sku}: qty {qty}")
            continue

        if phase == 0:   # giver side
            if frm in store_ids:
                tier = stores.at[frm, "tier"]
                if tier == C.S_PLUS_PLUS and (frm, style) in protected:
                    flag("FLAGSHIP_PROTECTED", gid, f"{frm} (S++) gives {qty} x {sku}; {style} is in its top-20 protected styles")
                stock[(frm, sku)] -= qty
                store_total[frm] -= qty
                cat_total[(frm, cat)] -= qty
                style_total[(frm, style)] -= qty
                if stock[(frm, sku)] < 0:
                    flag("NEGATIVE_STOCK", gid, f"{frm} {sku}: gives {qty}, leaves {stock[(frm, sku)]} on {_fmt(ship)}")
                need = min_units.get((tier, cat))
                if need is not None and cat_total[(frm, cat)] < need:
                    flag("MIN_DISPLAY", gid, f"{frm} ({tier}) {cat}: gives {qty} x {sku}, leaves {cat_total[(frm, cat)]} "
                                             f"units vs min display {need}")
                if to in store_ids:
                    v = style_vel.get((frm, style), 0.0)
                    cover = style_total[(frm, style)] / v if v > 0 else math.inf
                    if cover < C.DONOR_MIN_COVER_DAYS:
                        flag("DONOR_COVER", gid, f"{frm} -> {to} {sku}: {frm} keeps {style_total[(frm, style)]} of {style} "
                                                 f"at {v:.3g}/day = {_num(cover)} days cover (< {C.DONOR_MIN_COVER_DAYS})")
            elif frm == WH:
                wh_sent[sku] += qty
                supply = wh_supply(sku, ship)
                if wh_sent[sku] > supply:
                    flag("WH_NEGATIVE", gid, f"WH -> {to} {sku}: {wh_sent[sku]} sent by {_fmt(ship)} but only {supply} "
                                             f"available at WH-KOL by then")
            continue

        # phase 1: receiver side
        if to not in store_ids:
            continue
        if frm == WH and in_transit.get((to, sku), 0) > 0 and kind != "MIN_DISPLAY":
            have = stock[(to, sku)]
            target = math.ceil(vel.get((to, sku), 0.0) * (C.LEAD_WH[stores.at[to, "zone"]] + C.REVIEW_DAYS + C.SAFETY_DAYS))
            if have >= target:
                flag("IN_TRANSIT", gid, f"WH -> {to} {sku}: store already has {have} incl. {in_transit[(to, sku)]} "
                                        f"in transit vs target {target}; sending {qty} more")
        stock[(to, sku)] += qty
        store_total[to] += qty
        cat_total[(to, cat)] += qty
        style_total[(to, style)] += qty
        cap = int(stores.at[to, "capacity"])
        if store_total[to] > cap:
            flag("CAPACITY", gid, f"{frm} -> {to} {qty} x {sku}: {to} would hold {store_total[to]} units vs "
                                  f"capacity {cap} ({store_total[to] / cap:.0%})")

    return {"passed": len(violations) == 0, "checked_moves": len(events), "violations": violations}
