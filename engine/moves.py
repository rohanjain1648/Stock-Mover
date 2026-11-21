"""Move generation (S2): one shared ledger, five allocation passes, style-level groups, problem cards.

    generate_moves(data, feats) -> {"groups": [...C2 groups...], "problems": [...C2 problems...]}

Every pass reads and writes the same `Ledger`, so a unit is never counted twice and every hard
rule is checked at the moment of allocation (S3's engine/rules.py re-checks independently):
  1 min display (giver cat_group), 2 S++ protected styles, 3 receiver capacity,
  4 never send past target, 5 S2S donor style cover >= 30 days, 6 approval flag > Rs 1 lakh.
"""
from __future__ import annotations

import math
from collections import defaultdict

import pandas as pd

from engine import config as C
from engine.data import Data, protected_styles
from engine.interfaces import Features

INF = float("inf")
TARGET_EXTRA = C.REVIEW_DAYS + C.SAFETY_DAYS


def _cover(stock: float, vel: float) -> float:
    return stock / vel if vel > 0 else INF


class Ledger:
    """Projected stock per location x SKU, per store total, per store x cat_group / style, plus WH allocations."""

    def __init__(self, data: Data, feats: Features):
        self.data, self.feats = data, feats
        self.as_of = data.as_of
        self.ship0 = data.as_of + pd.Timedelta(days=1)
        self.season_end = pd.Timestamp(C.SEASON_END)
        st = data.stores.set_index("store_id")
        self.store_ids = list(st.index)
        self.tier, self.city, self.zone = st["tier"].to_dict(), st["city"].to_dict(), st["zone"].to_dict()
        self.capacity = st["capacity"].astype(int).to_dict()
        self.target_days = {s: C.LEAD_WH[z] + TARGET_EXTRA for s, z in self.zone.items()}
        self.prot = protected_styles(data)
        self.min_units = {(r.tier, r.cat_group): int(r.min_units) for r in data.min_display.itertuples()}

        it = data.items.reset_index(drop=True)
        self.items = it.set_index("sku_id")
        self.size_rank = {sku: i for i, sku in enumerate(it["sku_id"])}
        self.style_skus = it.groupby("style_id")["sku_id"].apply(list).to_dict()

        p = feats.sku_pos
        self.pos = p.set_index(["location_id", "sku_id"])
        key = list(zip(p["location_id"], p["sku_id"]))
        self.on_hand = dict(zip(key, p["on_hand"].astype(int)))
        self.in_transit = dict(zip(key, p["in_transit"].astype(int)))
        self.avail = dict(zip(key, p["available"].astype(int)))
        self.vel = dict(zip(key, p["vel_daily"].astype(float)))
        self.age = dict(zip(key, p["age_days"]))
        self.store_start = p.groupby("location_id")["available"].sum().astype(int).to_dict()
        self.cat_start = p.groupby(["location_id", "cat_group"])["available"].sum().astype(int).to_dict()
        self.style_start = p.groupby(["location_id", "style_id"])["available"].sum().astype(int).to_dict()
        self.style_vel = p.groupby(["location_id", "style_id"])["vel_daily"].sum().astype(float).to_dict()
        self.chain_vel_sku = p.groupby("sku_id")["vel_daily"].sum().astype(float).to_dict()
        self.chain_vel_style = p.groupby("style_id")["vel_daily"].sum().astype(float).to_dict()

        self.given = defaultdict(int)       # (loc, sku) -> units out
        self.recv = defaultdict(int)        # (loc, sku) -> units in
        self.store_in = defaultdict(int)
        self.store_out = defaultdict(int)
        self.cat_in = defaultdict(int)
        self.cat_out = defaultdict(int)
        self.style_in = defaultdict(int)
        self.style_out = defaultdict(int)

        # WH supply points: (ship date, cumulative supply). On-hand ships as_of + 1.
        self.wh_points: dict[str, list[tuple[pd.Timestamp, int]]] = {}
        for sku, g in feats.wh_timeline.sort_values("date").groupby("sku_id"):
            pts: dict[pd.Timestamp, int] = {}
            for d, cq in zip(g["date"], g["cum_qty"]):
                d = max(pd.Timestamp(d), self.ship0)
                pts[d] = max(pts.get(d, 0), int(cq))
            self.wh_points[sku] = sorted(pts.items())
        self.wh_alloc = defaultdict(lambda: defaultdict(int))   # sku -> ship date -> qty
        self.wh_start = dict(zip(feats.wh["sku_id"], feats.wh["on_hand"].astype(int)))
        self.lines: list[dict] = []
        self._lead: dict[tuple[str, str], int] = {}

    # ---------- lookups ----------
    def lead(self, src: str, dst: str) -> int:
        k = (src, dst)
        if k not in self._lead:
            if src == C.WH_ID:
                v = C.LEAD_WH[self.zone[dst]]
            elif dst == C.WH_ID:
                v = C.LEAD_WH[self.zone[src]]
            elif self.city[src] == self.city[dst]:
                v = C.LEAD_S2S_SAME_CITY
            elif self.zone[src] == self.zone[dst]:
                v = C.LEAD_S2S_SAME_ZONE
            else:
                v = C.LEAD_S2S_OTHER_ZONE
            self._lead[k] = v
        return self._lead[k]

    def stock(self, loc: str, sku: str) -> int:
        """Projected units at a store x SKU (available + in - out)."""
        k = (loc, sku)
        return self.avail.get(k, 0) + self.recv[k] - self.given[k]

    def store_total(self, store: str) -> int:
        return self.store_start.get(store, 0) + self.store_in[store] - self.store_out[store]

    def cat_total(self, store: str, cat: str) -> int:
        return self.cat_start.get((store, cat), 0) + self.cat_in[(store, cat)] - self.cat_out[(store, cat)]

    def style_stock(self, store: str, style: str) -> int:
        return self.style_start.get((store, style), 0) + self.style_in[(store, style)] - self.style_out[(store, style)]

    def target(self, store: str, sku: str) -> int:
        """Units a store x SKU should hold: ceil(vel x (lead_WH + review + safety))."""
        return math.ceil(self.vel.get((store, sku), 0.0) * self.target_days[store])

    def vel_need(self, store: str, sku: str) -> int:
        return max(0, self.target(store, sku) - self.stock(store, sku))

    def cat_deficit(self, store: str, cat: str) -> int:
        return max(0, self.min_units.get((self.tier[store], cat), 0) - self.cat_total(store, cat))

    def min_display_reserve(self, store: str) -> int:
        cats = {c for (s, c) in self.cat_start if s == store}
        return sum(self.cat_deficit(store, c) for c in cats)

    # ---------- rules ----------
    def give_limit(self, store: str, sku: str, for_s2s: bool) -> int:
        """Max units `store` may give of `sku` right now (rules 1, 2, 5; never a SKU it receives)."""
        if store == C.WH_ID:
            raise ValueError("WH supply is governed by wh_free / wh_take")
        k = (store, sku)
        if self.recv[k] > 0:                                   # no round trips
            return 0
        it = self.items.loc[sku]
        style, cat = it["style_id"], it["cat_group"]
        if (store, style) in self.prot:                        # rule 2
            return 0
        # physical: only on-hand units leave; inbound to the giver is ignored (conservative vs replay)
        lim = self.on_hand.get(k, 0) - self.given[k]
        # rule 1: giver's cat_group total (start - out, inbound ignored) stays >= min display
        cat_now = self.cat_start.get((store, cat), 0) - self.cat_out[(store, cat)]
        lim = min(lim, cat_now - self.min_units.get((self.tier[store], cat), 0))
        if for_s2s:                                            # rule 5: style cover after >= 30 days
            V = self.style_vel.get((store, style), 0.0)
            if V > 0:
                S = self.style_start.get((store, style), 0) - self.style_out[(store, style)]
                x = min(lim, math.floor(S - C.DONOR_MIN_COVER_DAYS * V + 1e-9))
                while x > 0 and (S - x) / V < C.DONOR_MIN_COVER_DAYS:
                    x -= 1
                lim = min(lim, x)
        return max(0, int(lim))

    def receive_limit(self, store: str, reserve_min_display: bool = False) -> int:
        """Capacity headroom (outbound moves NOT credited — S3 replays receives before same-day gives)."""
        if store == C.WH_ID:
            return 10 ** 9
        start = self.store_start.get(store, 0)
        if start > self.capacity[store]:                       # already over capacity: receives nothing
            return 0
        head = self.capacity[store] - start - self.store_in[store]
        if reserve_min_display:
            head -= self.min_display_reserve(store)
        return max(0, int(head))

    # ---------- WH supply ----------
    def _wh_slack(self, sku: str) -> list[tuple[pd.Timestamp, int]]:
        """(date, supply - cumulative allocations) at each supply point."""
        alloc = self.wh_alloc[sku]
        out, used = [], 0
        dates = sorted(alloc)
        i = 0
        for d, cq in self.wh_points.get(sku, []):
            while i < len(dates) and dates[i] <= d:
                used += alloc[dates[i]]
                i += 1
            out.append((d, cq - used))
        return out

    def _wh_free_at(self, slack, d) -> int:
        vals = [s for (t, s) in slack if t >= d]
        prior = [t for (t, _) in slack if t <= d]
        if not prior:
            return 0
        return max(0, min(vals)) if vals else 0

    def wh_free(self, sku: str, by_date) -> int:
        """Units the WH can still ship of `sku` on or before `by_date` without going negative on any date."""
        slack = self._wh_slack(sku)
        pts = [t for (t, _) in slack if t <= pd.Timestamp(by_date)]
        if not pts:
            return 0
        return self._wh_free_at(slack, pts[-1])

    def wh_ship_date(self, sku: str, qty: int):
        """Earliest ship date on which `qty` units of `sku` can leave the WH, or None."""
        slack = self._wh_slack(sku)
        for t, _ in slack:
            if self._wh_free_at(slack, t) >= qty:
                return t
        return None

    def wh_take(self, sku: str, qty: int, latest) -> list[tuple[pd.Timestamp, int]]:
        """Plan up to `qty` WH units shipping by `latest`, earliest stock first. Returns [(ship_on, q)] (not recorded)."""
        out, rem = [], qty
        latest = pd.Timestamp(latest)
        slack = self._wh_slack(sku)
        taken = 0
        for t, _ in slack:
            if t > latest or rem <= 0:
                break
            f = self._wh_free_at(slack, t) - taken
            if f > 0:
                q = min(rem, f)
                out.append((t, q))
                rem -= q
                taken += q
        return out

    # ---------- write ----------
    def record(self, typ: str, kind: str, frm: str, to: str, sku: str, qty: int, ship_on, ctx: dict | None = None):
        qty = int(qty)
        if qty <= 0:
            return
        it = self.items.loc[sku]
        style, cat = it["style_id"], it["cat_group"]
        ship_on = pd.Timestamp(ship_on)
        lead = self.lead(frm, to)
        to_before = self.stock(to, sku) if to != C.WH_ID else None
        if frm == C.WH_ID:
            self.wh_alloc[sku][ship_on] += qty
        else:
            self.given[(frm, sku)] += qty
            self.store_out[frm] += qty
            self.cat_out[(frm, cat)] += qty
            self.style_out[(frm, style)] += qty
        if to != C.WH_ID:
            self.recv[(to, sku)] += qty
            self.store_in[to] += qty
            self.cat_in[(to, cat)] += qty
            self.style_in[(to, style)] += qty
        rar = 0.0
        if typ != "PULL_BACK" and to != C.WH_ID:
            short = max(0.0, self.vel.get((to, sku), 0.0) * self.target_days[to] - to_before)
            rar = min(qty, short) * float(it["mrp"])
        self.lines.append({
            "type": typ, "kind": kind, "from": frm, "to": to, "sku_id": sku, "style_id": style,
            "size": it["size"], "qty": qty, "mrp": int(it["mrp"]), "ship_on": ship_on,
            "arrives_on": ship_on + pd.Timedelta(days=lead), "lead_days": lead,
            "to_before": to_before, "revenue_at_risk": rar, "ctx": dict(ctx or {}),
        })


# ---------------------------------------------------------------- groups
def _style_cover_now(L: Ledger, store: str, style: str, delta: int = 0) -> float:
    return _cover(L.style_stock(store, style) + delta, L.style_vel.get((store, style), 0.0))


def assemble_groups(L: Ledger) -> list[dict]:
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for ln in L.lines:
        buckets[(ln["type"], ln["kind"], ln["from"], ln["to"], ln["style_id"], ln["ship_on"])].append(ln)
    groups = []
    for (typ, kind, frm, to, style, ship_on), lns in buckets.items():
        per_sku: dict[str, int] = defaultdict(int)
        for ln in lns:
            per_sku[ln["sku_id"]] += ln["qty"]
        skus = sorted(per_sku, key=lambda s: L.size_rank.get(s, 0))
        it0 = L.items.loc[skus[0]]
        sizes = {L.items.at[s, "size"]: per_sku[s] for s in skus}
        qty = sum(per_sku.values())
        mrp_value = int(sum(per_sku[s] * int(L.items.at[s, "mrp"]) for s in skus))
        rar = float(sum(ln["revenue_at_risk"] for ln in lns))
        if typ == "PULL_BACK":
            over = L.store_start.get(frm, 0) > L.capacity.get(frm, 10 ** 9)
            priority = 0.1 * mrp_value + 50000 * int(over)
        else:
            priority = rar
        lead = L.lead(frm, to)
        g = {
            "group_id": None, "type": typ, "problem_kind": kind, "style_id": style,
            "style_name": it0["style_name"], "category": it0["category"], "from": frm, "to": to,
            "ship_on": ship_on, "arrives_on": ship_on + pd.Timedelta(days=lead), "lead_days": lead,
            "sizes": sizes, "qty": qty, "mrp_value": mrp_value, "revenue_at_risk": round(rar, 2),
            "priority": round(priority, 2), "needs_approval": mrp_value > C.APPROVAL_MRP_THRESHOLD,
            "explanation": "", "evidence": {}, "lines": [{"sku_id": s, "size": L.items.at[s, "size"], "qty": per_sku[s]}
                                                         for s in skus],
            "_lines": lns,
        }
        g["evidence"] = _evidence(L, g)
        g["explanation"] = _explain(L, g)
        groups.append(g)
    groups.sort(key=lambda g: (-g["priority"], -g["mrp_value"], g["style_id"], g["from"], g["to"]))
    for i, g in enumerate(groups, 1):
        g["group_id"] = f"G{i:03d}"
        g.pop("_lines")
    return groups


def _evidence(L: Ledger, g: dict) -> dict:
    frm, to, style, qty = g["from"], g["to"], g["style_id"], g["qty"]
    ev = dict.fromkeys(["from_cover_before", "from_cover_after", "to_cover_before", "to_cover_after",
                        "to_vel_daily", "from_vel_daily", "lift", "age_days", "to_capacity_after"])
    return ev


def _explain(L: Ledger, g: dict) -> str:
    frm = "WH" if g["from"] == C.WH_ID else g["from"]
    to = "WH" if g["to"] == C.WH_ID else g["to"]
    sizes = " ".join(f"{s}{q}" for s, q in g["sizes"].items())
    return f"{frm} → {to} · {g['qty']} × {g['style_id']} ({sizes}): {g['problem_kind'].lower()}"


# ---------------------------------------------------------------- entry
def generate_moves(data: Data, feats: Features) -> dict:
    L = Ledger(data, feats)
    groups = assemble_groups(L)
    return {"groups": groups, "problems": []}
