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
ALWAYS_MATERIAL = ("NEW_LAUNCH", "MIN_DISPLAY")   # kinds shown whatever their revenue at risk (plus all pull-backs)


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
        self.need0 = dict(zip(key, p["need_units"].astype(int)))   # S1: velocity need + min-display top-up
        self.is_core = it.set_index("style_id")["is_core"].astype(bool).groupby(level=0).first().to_dict()
        self.store_start = p.groupby("location_id")["available"].sum().astype(int).to_dict()
        self.cat_start = p.groupby(["location_id", "cat_group"])["available"].sum().astype(int).to_dict()
        self.store_cats = defaultdict(list)
        for (s, c) in self.cat_start:
            self.store_cats[s].append(c)
        self.style_start = p.groupby(["location_id", "style_id"])["available"].sum().astype(int).to_dict()
        self.style_vel = p.groupby(["location_id", "style_id"])["vel_daily"].sum().astype(float).to_dict()
        self.chain_vel_sku = p.groupby("sku_id")["vel_daily"].sum().astype(float).to_dict()
        self.chain_vel_style = p.groupby("style_id")["vel_daily"].sum().astype(float).to_dict()
        self.chain_sold84_style = p.groupby("style_id")["sold_84"].sum().astype(int).to_dict()

        self.given = defaultdict(int)       # (loc, sku) -> units out
        self.recv = defaultdict(int)        # (loc, sku) -> units in
        self.store_in = defaultdict(int)
        self.store_in0 = defaultdict(int)   # receives shipping as_of + 1
        self.store_inl = defaultdict(int)   # receives shipping later
        self.store_out = defaultdict(int)
        self.cat_in = defaultdict(int)
        self.cat_out = defaultdict(int)
        self.style_in = defaultdict(int)
        self.style_out = defaultdict(int)
        self.style_s2s_out = defaultdict(int)

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
        self.banned: set[tuple] = set()      # ban_key()s the materiality loop held back
        self._lead: dict[tuple[str, str], int] = {}
        self._wh_style: dict[str, bool] = {}

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
        return sum(self.cat_deficit(store, c) for c in self.store_cats.get(store, ()))

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
        # rule 5: style cover after >= 30 days. Once the store has given this style store->store, later
        # pull-backs keep the cover too (S3 replays by date then group order, so final stock must hold).
        if for_s2s or self.style_s2s_out[(store, style)] > 0:
            V = self.style_vel.get((store, style), 0.0)
            if V > 0:
                S = self.style_start.get((store, style), 0) - self.style_out[(store, style)]
                x = min(lim, math.floor(S - C.DONOR_MIN_COVER_DAYS * V + 1e-9))
                while x > 0 and (S - x) / V < C.DONOR_MIN_COVER_DAYS:
                    x -= 1
                lim = min(lim, x)
        return max(0, int(lim))

    def receive_limit(self, store: str, ship_on=None, cat: str | None = None, reserve_min_display: bool = False) -> int:
        """Capacity headroom for a receive shipping on `ship_on` (default: as_of + 1).

        All store-origin moves ship as_of + 1 and S3 replays lines by ship_on, then group order. So a
        receive shipping as_of + 1 may be replayed before that day's gives (outbound NOT credited), while a
        receive shipping later is replayed after every give (outbound credited). With `reserve_min_display`
        the store's outstanding min-display deficits in OTHER categories stay free for pass 4.
        """
        if store == C.WH_ID:
            return 10 ** 9
        start = self.store_start.get(store, 0)
        cap = self.capacity[store]
        if start > cap:                                        # already over capacity: receives nothing
            return 0
        d = self.ship0 if ship_on is None else pd.Timestamp(ship_on)
        in0, inl, out = self.store_in0[store], self.store_inl[store], self.store_out[store]
        if d <= self.ship0:
            head = cap - start - in0 - max(0, inl - out)
        else:
            head = cap - start - in0 - inl + out
        if reserve_min_display:
            own = self.cat_deficit(store, cat) if cat else 0
            other = self.min_display_reserve(store) - own
            head = head - other if head >= other + own else min(own, head - other)
        return max(0, int(head))

    def can_pull_back(self, sku: str) -> bool:
        """Never pull back a style the WH holds none of (sold out: nothing to redeploy; stores consolidate)."""
        style = self.items.at[sku, "style_id"]
        if style not in self._wh_style:
            self._wh_style[style] = any(self.wh_points.get(k) and self.wh_points[k][-1][1] > 0
                                        for k in self.style_skus[style])
        return self._wh_style[style]

    def can_receive(self, store: str, sku: str) -> bool:
        return store != C.WH_ID and self.given[(store, sku)] == 0 and \
            self.store_start.get(store, 0) <= self.capacity[store]

    # ---------- WH supply ----------
    def _wh_slack(self, sku: str) -> list[tuple[pd.Timestamp, int]]:
        """(date, supply shipped-able by date - allocations by date) at every supply point and allocation date."""
        pts = self.wh_points.get(sku, [])
        alloc = self.wh_alloc[sku]
        out = []
        for d in sorted({t for t, _ in pts} | set(alloc)):
            sup = [cq for t, cq in pts if t <= d]
            used = sum(q for t, q in alloc.items() if t <= d)
            out.append((d, (sup[-1] if sup else 0) - used))
        return out

    def _wh_free_at(self, slack, d) -> int:
        if not any(t <= d for t, _ in slack):
            return 0
        vals = [s for (t, s) in slack if t >= d]
        if not vals:                                           # d after the last point: free = last slack
            vals = [slack[-1][1]]
        return max(0, min(vals))

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

    def send_from_wh(self, kind: str, store: str, sku: str, qty: int, latest, reserve: bool, ctx=None) -> int:
        """Ship up to `qty` of `sku` from the WH to `store` by `latest`, respecting capacity by ship date.
        Units that do not fit on as_of + 1 (before that day's gives) move to as_of + 2. Returns units sent."""
        if qty <= 0 or not self.can_receive(store, sku):
            return 0
        cat = self.items.at[sku, "cat_group"]
        sent = 0
        for d, qd in self.wh_take(sku, qty, latest):
            days = [d] if d > self.ship0 else [self.ship0, self.ship0 + pd.Timedelta(days=1)]
            for day in days:
                if qd <= 0 or day > pd.Timestamp(latest):
                    break
                a = min(qd, self.receive_limit(store, day, cat, reserve))
                if a > 0:
                    a = self.record("WH_TO_STORE", kind, C.WH_ID, store, sku, a, day, ctx)
                    if a == 0:
                        break
                    qd -= a
                    sent += a
        return sent

    # ---------- write ----------
    def record(self, typ: str, kind: str, frm: str, to: str, sku: str, qty: int, ship_on, ctx: dict | None = None):
        qty = int(qty)
        if qty <= 0:
            return 0
        it = self.items.loc[sku]
        style, cat = it["style_id"], it["cat_group"]
        banned = self.banned and typ != "PULL_BACK" and kind not in ALWAYS_MATERIAL
        if banned and ban_key(typ, kind, frm, to, style, ship_on) in self.banned:   # immaterial earlier
            return 0
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
                self.style_s2s_out[(frm, style)] += qty
        if to != C.WH_ID:
            self.recv[(to, sku)] += qty
            self.store_in[to] += qty
            if ship_on <= self.ship0:
                self.store_in0[to] += qty
            else:
                self.store_inl[to] += qty
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
        return qty


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
        groups.append(g)
    groups.sort(key=lambda g: (-g["priority"], -g["mrp_value"], g["style_id"], g["from"], g["to"]))
    for i, g in enumerate(groups, 1):
        g["group_id"] = f"G{i:03d}"
        g.pop("_lines")
    return groups


EVIDENCE_KEYS = ("from_cover_before", "from_cover_after", "to_cover_before", "to_cover_after",
                 "to_vel_daily", "from_vel_daily", "lift", "age_days", "to_capacity_after")


def _placeholder_explanation(g: dict) -> str:
    frm = "WH" if g["from"] == C.WH_ID else g["from"]
    to = "WH" if g["to"] == C.WH_ID else g["to"]
    sizes = " ".join(f"{s}{q}" for s, q in g["sizes"].items())
    return f"{frm} → {to} · {g['qty']} × {g['style_id']} ({sizes}): {g['problem_kind'].lower().replace('_', ' ')}"


def explain_groups(groups: list[dict], data: Data, feats: Features) -> None:
    """Evidence + one-line explanation per group from S1's engine/explain.py (start-state numbers).
    Falls back to a placeholder when explain.py is missing or fails on a group, so a run never breaks."""
    try:
        from engine.explain import evidence_for, explain_group
    except ImportError:
        evidence_for = explain_group = None
    for g in groups:
        g["evidence"], g["explanation"] = dict.fromkeys(EVIDENCE_KEYS), _placeholder_explanation(g)
        if explain_group is None:
            continue
        try:
            g["evidence"] = evidence_for(g, data, feats)
            g["explanation"] = explain_group(g, data, feats)
        except Exception:                                      # keep the placeholder for this group only
            pass


# ---------------------------------------------------------------- pass helpers
def _is_new_launch(L: Ledger, style: str) -> bool:
    ld = L.items.at[L.style_skus[style][0], "launch_date"]
    return pd.notna(ld) and 0 <= (L.as_of - ld).days <= 60


def _wh_latest(L: Ledger, store: str) -> pd.Timestamp:
    return L.as_of + pd.Timedelta(days=L.target_days[store])


def _surplus(L: Ledger, store: str, sku: str, days: int = C.DONOR_MIN_COVER_DAYS) -> int:
    """SKU units above `days` of the store's own cover."""
    return max(0, L.stock(store, sku) - math.ceil(L.vel.get((store, sku), 0.0) * days))


def _style_has_wh_supply(L: Ledger, style: str) -> bool:
    return any(L.wh_points.get(s) and L.wh_points[s][-1][1] > 0 for s in L.style_skus[style])


def _s2s_to_needs(L: Ledger, kind: str, giver: str, sku: str, max_qty: int) -> int:
    """Offer up to `max_qty` of the giver's SKU to stores with a velocity need, nearest first."""
    sent = 0
    cat = L.items.at[sku, "cat_group"]
    recvs = [s for s in L.store_ids if s != giver and L.can_receive(s, sku) and L.vel_need(s, sku) > 0]
    recvs.sort(key=lambda s: (L.lead(giver, s), -L.vel.get((s, sku), 0.0)))
    for r in recvs:
        if sent >= max_qty:
            break
        q = min(max_qty - sent, L.vel_need(r, sku), L.receive_limit(r, None, cat, True),
                L.give_limit(giver, sku, True))
        if q > 0:
            sent += L.record("STORE_TO_STORE", kind, giver, r, sku, q, L.ship0)
    return sent


def _proportional(total: int, caps: dict, weights: dict) -> dict:
    """Largest-remainder split of `total` by `weights`, never above `caps`."""
    out = defaultdict(int)
    left = total
    while left > 0:
        live = {k: w for k, w in weights.items() if w > 0 and caps[k] - out[k] > 0}
        W = sum(live.values())
        if not live or W <= 0:
            break
        raw = {k: left * w / W for k, w in live.items()}
        add = {k: min(int(math.floor(v)), caps[k] - out[k]) for k, v in raw.items()}
        for k, v in add.items():
            out[k] += v
        given = sum(add.values())
        left -= given
        for k in sorted(live, key=lambda k: -(raw[k] - math.floor(raw[k]))):
            if left <= 0:
                break
            if caps[k] - out[k] > 0:
                out[k] += 1
                left -= 1
        if given == 0 and left == total:
            break
        total = left
    return out


# ---------------------------------------------------------------- passes
def pass1_capacity_overstock(L: Ledger) -> None:
    """Over-capacity stores release their slowest stock (to need stores first, rest pulled back);
    then gross overstock rows (> 120 days cover, >= 10 units) offer stock to need stores and pull back
    what exceeds 120 days."""
    by_store = defaultdict(list)
    for (loc, sku), a in L.avail.items():
        if loc in L.capacity and a > 0:
            by_store[loc].append(sku)

    for store in L.store_ids:
        if L.store_start.get(store, 0) <= L.capacity[store]:
            continue
        release = L.store_total(store) - L.capacity[store]
        skus = sorted(by_store[store], key=lambda k: (-_cover(L.stock(store, k), L.vel.get((store, k), 0.0)),
                                                      -L.stock(store, k)))
        for sku in skus:
            if release <= 0:
                break
            sur = _surplus(L, store, sku)
            if sur <= 0:
                continue
            moved = _s2s_to_needs(L, "CAPACITY", store, sku, sur)
            release -= moved
            q = min(sur - moved, release, L.give_limit(store, sku, False))
            if q > 0 and L.can_pull_back(sku):
                release -= L.record("PULL_BACK", "CAPACITY", store, C.WH_ID, sku, q, L.ship0)

    rows = []
    for store in L.store_ids:
        for sku in by_store[store]:
            st, v = L.stock(store, sku), L.vel.get((store, sku), 0.0)
            if st >= 10 and _cover(st, v) > 120 and L.given[(store, sku)] == 0:
                rows.append((store, sku))
    rows.sort(key=lambda r: -_surplus(L, r[0], r[1], 120) * int(L.items.at[r[1], "mrp"]))
    for store, sku in rows:
        _s2s_to_needs(L, "OVERSTOCK", store, sku, _surplus(L, store, sku))
        q = min(_surplus(L, store, sku, 120), L.give_limit(store, sku, False))
        if q > 0 and L.can_pull_back(sku):
            L.record("PULL_BACK", "OVERSTOCK", store, C.WH_ID, sku, q, L.ship0)


def pass2_store_to_store(L: Ledger) -> None:
    """Needs the WH cannot cover within the target window are filled from donors' surplus
    (same city -> same zone -> other zone)."""
    latest = max(_wh_latest(L, s) for s in L.store_ids)
    skus = sorted(L.chain_vel_sku, key=lambda k: -L.chain_vel_sku[k] * int(L.items.at[k, "mrp"]))
    for sku in skus:
        recvs = [s for s in L.store_ids if L.can_receive(s, sku) and L.vel_need(s, sku) > 0]
        if not recvs:
            continue
        shortage = sum(L.vel_need(s, sku) for s in recvs) - L.wh_free(sku, latest)
        if shortage <= 0:
            continue
        style = L.items.at[sku, "style_id"]
        kind = "UNDERSTOCK" if _style_has_wh_supply(L, style) else "SOLD_OUT_CONSOLIDATION"
        cat = L.items.at[sku, "cat_group"]
        donors = [s for s in L.store_ids if s not in recvs and _surplus(L, s, sku) > 0
                  and L.give_limit(s, sku, True) > 0]
        if not donors:
            continue
        for r in sorted(recvs, key=lambda s: -L.vel.get((s, sku), 0.0)):
            if shortage <= 0:
                break
            want = min(L.vel_need(r, sku), shortage)
            for d in sorted(donors, key=lambda d: (L.lead(d, r), -_surplus(L, d, sku))):
                if want <= 0:
                    break
                q = min(want, _surplus(L, d, sku), L.give_limit(d, sku, True), L.receive_limit(r, None, cat, True))
                if q > 0:
                    q = L.record("STORE_TO_STORE", kind, d, r, sku, q, L.ship0)
                    want -= q
                    shortage -= q


def pass3_wh_to_store(L: Ledger) -> None:
    """WH supply (on hand + inbound shipping inside each store's target window) to store needs.
    Enough supply: fill all. Scarce: 1 unit to every selling store (highest velocity first), then the
    rest by need x velocity (largest remainder)."""
    latest = max(_wh_latest(L, s) for s in L.store_ids)

    def need_value(sku):
        return sum(L.vel_need(s, sku) for s in L.store_ids) * int(L.items.at[sku, "mrp"])

    skus = [k for k in L.wh_points if k in L.items.index and L.wh_points[k][-1][1] > 0]
    skus.sort(key=lambda k: -need_value(k))
    for sku in skus:
        style = L.items.at[sku, "style_id"]
        for _round in range(2):
            needs = {s: L.vel_need(s, sku) for s in L.store_ids if L.can_receive(s, sku)}
            needs = {s: n for s, n in needs.items() if n > 0}
            supply = L.wh_free(sku, latest)
            if not needs or supply <= 0:
                break
            total = sum(needs.values())
            if _round == 0:
                kind = "NEW_LAUNCH" if _is_new_launch(L, style) else ("SCARCITY" if supply < total else "UNDERSTOCK")
            if supply >= total:
                alloc = dict(needs)
            else:
                alloc = defaultdict(int)
                left = supply
                for s in sorted(needs, key=lambda s: -L.vel.get((s, sku), 0.0)):
                    if left <= 0:
                        break
                    if L.vel.get((s, sku), 0.0) > 0:
                        alloc[s] += 1
                        left -= 1
                rem = {s: needs[s] - alloc[s] for s in needs}
                extra = _proportional(left, rem, {s: rem[s] * L.vel.get((s, sku), 0.0) for s in needs})
                for s, q in extra.items():
                    alloc[s] += q
            sent = 0
            for s in sorted(alloc, key=lambda s: -L.vel.get((s, sku), 0.0)):
                sent += L.send_from_wh(kind, s, sku, alloc[s], _wh_latest(L, s), reserve=True)
            if sent == 0:
                break


def _s2s_one(L: Ledger, kind: str, store: str, sku: str, qty: int) -> int:
    """Fill up to `qty` of `sku` at `store` from donors' surplus (nearest first). Returns units sent."""
    if qty <= 0 or not L.can_receive(store, sku):
        return 0
    cat = L.items.at[sku, "cat_group"]
    donors = [d for d in L.store_ids if d != store and _surplus(L, d, sku) > 0 and L.give_limit(d, sku, True) > 0]
    sent = 0
    for d in sorted(donors, key=lambda d: (L.lead(d, store), -_surplus(L, d, sku))):
        if sent >= qty:
            break
        q = min(qty - sent, _surplus(L, d, sku), L.give_limit(d, sku, True), L.receive_limit(store, None, cat, True))
        if q > 0:
            sent += L.record("STORE_TO_STORE", kind, d, store, sku, q, L.ship0)
    return sent


def pass4_min_display(L: Ledger) -> None:
    """Store x cat_group still below min display: first fill S1's need_units headroom (velocity need +
    min-display top-up, spread over the store's fastest SKUs), then one unit at a time round-robin over
    the ranked SKUs. Each unit comes from the WH if it can ship inside the target window, else from a
    donor store's surplus."""
    cats_of = L.items.groupby("cat_group").groups
    for store in L.store_ids:
        if L.store_start.get(store, 0) > L.capacity[store]:
            continue
        for cat in sorted(L.store_cats.get(store, ())):
            if L.cat_deficit(store, cat) <= 0:
                continue
            skus = [k for k in cats_of.get(cat, []) if (store, k) in L.avail]
            live = [k for k in skus if L.vel.get((store, k), 0.0) > 0 or L.chain_vel_sku.get(k, 0.0) > 0]
            ranked = sorted(live or skus, key=lambda k: (-L.vel.get((store, k), 0.0), -L.chain_vel_sku.get(k, 0.0), k))
            latest = _wh_latest(L, store)

            def give(k, q):
                if q <= 0 or not L.can_receive(store, k):
                    return 0
                s = L.send_from_wh("MIN_DISPLAY", store, k, q, latest, reserve=True)
                return s + _s2s_one(L, "MIN_DISPLAY", store, k, q - s)

            for k in ranked:                                       # phase A: S1's per-SKU need headroom
                left = L.cat_deficit(store, cat)
                if left <= 0:
                    break
                give(k, min(left, L.need0.get((store, k), 0) - L.recv[(store, k)]))
            stuck = set()
            while L.cat_deficit(store, cat) > 0 and len(stuck) < len(ranked):   # phase B: round robin
                for k in ranked:
                    if L.cat_deficit(store, cat) <= 0:
                        break
                    if k not in stuck and give(k, 1) == 0:
                        stuck.add(k)


def _aged(L: Ledger, store: str, sku: str) -> bool:
    age = L.age.get((store, sku))
    if age is None or pd.isna(age):
        return False
    core = L.is_core.get(L.items.at[sku, "style_id"], True)
    return age > (C.AGEING_DAYS_CORE if core else C.AGEING_DAYS_FASHION)


DEAD_MAX_SOLD_84 = 10  # chain-wide 12-week sales at or below which a style is dead (S3 DEAD_STOCK bar)
AGEING_SLOW = 0.02     # units/day at or below which aged stock "does not sell" where it sits


def _aged_rows(L: Ledger) -> list[tuple[str, str]]:
    rows = [(s, k) for (s, k), oh in L.on_hand.items()
            if s in L.capacity and oh > 0 and L.vel.get((s, k), 0.0) <= AGEING_SLOW and _aged(L, s, k)
            and L.given[(s, k)] == 0 and L.recv[(s, k)] == 0]
    rows.sort(key=lambda r: (-L.age.get(r, 0), -L.on_hand[r] * int(L.items.at[r[1], "mrp"]), r))
    return rows


def pass5a_ageing_to_sellers(L: Ledger) -> None:
    """Aged store x SKU stock (> 180 days core, > 90 days fashion) that does not sell there
    (vel_daily <= 0.02) goes to the stores selling that SKU fastest (> 0.02/day), within their need and
    arriving by season end. Runs before passes 2-3 so aged units fill needs before fresh WH stock does.
    Fastest seller first; each takes from the nearest aged donor (oldest first on ties)."""
    donors_of = defaultdict(list)
    for store, sku in _aged_rows(L):
        donors_of[sku].append(store)
    for sku in sorted(donors_of, key=lambda k: (-L.chain_vel_sku.get(k, 0.0), k)):
        cat = L.items.at[sku, "cat_group"]
        sellers = [r for r in L.store_ids if L.vel.get((r, sku), 0.0) > AGEING_SLOW and L.can_receive(r, sku)]
        for r in sorted(sellers, key=lambda r: (-L.vel.get((r, sku), 0.0), r)):
            for d in sorted(donors_of[sku], key=lambda d: (L.lead(d, r), -L.age.get((d, sku), 0), d)):
                want = L.vel_need(r, sku)
                if want <= 0:
                    break
                if d == r or L.ship0 + pd.Timedelta(days=L.lead(d, r)) > L.season_end:
                    continue
                q = min(want, L.give_limit(d, sku, True), L.receive_limit(r, None, cat, True))
                if q > 0:
                    L.record("STORE_TO_STORE", "AGEING", d, r, sku, q, L.ship0)


def pass5b_ageing_pull_back(L: Ledger) -> None:
    """Aged stock still in place goes back to the WH when the whole style is dead at that store
    (style-level vel_daily <= 0.02) and the store receives nothing of that style in this run
    (fringe sizes of a style that sells stay, so size runs are not broken). Chain-dead styles (<= 10 sold
    chain-wide in 12 weeks, S3's DEAD_STOCK bar) stay for markdown in place: freight to the WH frees no
    sale anywhere."""
    for store, sku in _aged_rows(L):
        style = L.items.at[sku, "style_id"]
        if L.style_vel.get((store, style), 0.0) > AGEING_SLOW or L.style_in[(store, style)] > 0:
            continue
        if L.chain_sold84_style.get(style, 0) <= DEAD_MAX_SOLD_84 or not L.can_pull_back(sku):
            continue
        q = L.give_limit(store, sku, False)
        if q > 0:
            L.record("PULL_BACK", "AGEING", store, C.WH_ID, sku, q, L.ship0)


# ---------------------------------------------------------------- problems
def _fmt_units(n) -> str:
    return f"{int(n):,}"


def _units(n) -> str:
    n = int(n)
    return f"{n:,} unit" if n == 1 else f"{n:,} units"


def _inr(v) -> str:
    v = float(v)
    if v >= 1e7:
        return f"Rs {v / 1e7:.2f} cr"
    if v >= 1e5:
        return f"Rs {v / 1e5:.1f} L"
    return f"Rs {v:,.0f}"


STARVED_UTILISATION = 0.5   # a store holding < 50% of its capacity is starved (its top-ups get a headline card)
SMALL_SHORTAGE_UNITS = 10   # shortage styles sending fewer units than this share one combined card
SMALL_SHORTAGE_REF = "_SMALL"
CARD_ORDER = ("CAPACITY", "NEW_LAUNCH", "SCARCITY", "STARVED", "MIN_DISPLAY", "AGEING",
              "SOLD_OUT_CONSOLIDATION", "OVERSTOCK", "ROUTINE")


def build_problems(groups: list[dict], data: Data, feats: Features) -> list[dict]:
    """C2 problem cards, in CARD_ORDER. One per CAPACITY store, NEW_LAUNCH style, SCARCITY style,
    starved store (UNDERSTOCK into a store < 50% full) and MIN_DISPLAY store; one combined card each for
    AGEING, SOLD_OUT_CONSOLIDATION and OVERSTOCK; then one "Routine top-up" card per receiving store for
    the remaining UNDERSTOCK groups. Every group sits in exactly one card."""
    st = data.stores.set_index("store_id")
    sp = feats.sku_pos
    start_units = sp.groupby("location_id")["available"].sum()
    starved = {s for s in st.index if start_units.get(s, 0) < STARVED_UTILISATION * int(st.at[s, "capacity"])}
    style_name = data.items.groupby("style_id")["style_name"].first()
    scarcity_units: dict[str, int] = defaultdict(int)
    for g in groups:
        if g["problem_kind"] == "SCARCITY":
            scarcity_units[g["style_id"]] += g["qty"]
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for g in groups:
        k = g["problem_kind"]
        if k == "CAPACITY":
            key = (k, g["from"])
        elif k == "SCARCITY" and scarcity_units[g["style_id"]] < SMALL_SHORTAGE_UNITS:
            key = (k, SMALL_SHORTAGE_REF)
        elif k in ("NEW_LAUNCH", "SCARCITY"):
            key = (k, g["style_id"])
        elif k == "MIN_DISPLAY":
            key = (k, g["to"])
        elif k == "UNDERSTOCK":
            key = ("STARVED" if g["to"] in starved else "ROUTINE", g["to"])
        else:
            key = (k, None)
        buckets[key].append(g)

    cards = []
    for (bucket, ref), gs in buckets.items():
        kind = "UNDERSTOCK" if bucket in ("STARVED", "ROUTINE") else bucket
        units = sum(g["qty"] for g in gs)
        mrp = sum(g["mrp_value"] for g in gs)
        stores = sorted({g["to"] for g in gs if g["to"] != C.WH_ID} | {g["from"] for g in gs if g["from"] != C.WH_ID})
        back = sum(g["qty"] for g in gs if g["type"] == "PULL_BACK")
        if kind == "CAPACITY":
            u, cap = int(start_units.get(ref, 0)), int(st.at[ref, "capacity"])
            title = f"{ref} is at {u / cap:.0%} of capacity"
            detail = (f"{ref} holds {_units(u)} against capacity {_fmt_units(cap)}. Release {_fmt_units(units)} "
                      f"units ({_fmt_units(units - back)} to stores that need them, {_fmt_units(back)} back to WH).")
        elif kind == "NEW_LAUNCH":
            ld = data.items.loc[data.items.style_id == ref, "launch_date"].min()
            days = (data.as_of - ld).days if pd.notna(ld) else None
            title = f"{ref} {style_name.get(ref, '')} launched {days} days ago: {_units(units)} to {len(stores)} stores"
            detail = f"New launch: send {_units(units)} ({_inr(mrp)} at MRP) to the {len(stores)} stores selling it, sized by need."
        elif kind == "SCARCITY" and ref == SMALL_SHORTAGE_REF:
            styles = sorted({g["style_id"] for g in gs})
            need = int(sp.loc[sp.style_id.isin(styles) & (sp.location_id != C.WH_ID), "need_units"].sum())
            title = f"Small warehouse shortages · {len(styles)} styles: {_units(units)} for {_units(need)} of need"
            detail = (f"The warehouse holds only a few units of {', '.join(styles)}; each unit goes to the selling "
                      f"store that needs it most. Buyer to review re-orders.")
        elif kind == "SCARCITY":
            need = int(sum(sp.loc[(sp.style_id == ref) & (sp.location_id != C.WH_ID), "need_units"]))
            title = f"{ref} {style_name.get(ref, '')}: {_units(units)} for {_units(need)} of need"
            detail = (f"Warehouse supply is short of demand, so {len(stores)} selling stores each get a presentation "
                      f"minimum first and the rest is split by need x velocity.")
        elif bucket == "STARVED":
            u, cap = int(start_units.get(ref, 0)), int(st.at[ref, "capacity"])
            n_styles = len({g["style_id"] for g in gs})
            title = f"{ref} is starved: {_units(u)} at {u / cap:.0%} of capacity"
            detail = (f"{ref} holds {_units(u)} against capacity {_fmt_units(cap)}. Send {_units(units)} "
                      f"across {n_styles} styles ({_inr(mrp)} at MRP) to cover {L_TARGET_TEXT}.")
        elif bucket == "ROUTINE":
            n_styles = len({g["style_id"] for g in gs})
            title = f"Routine top-up · {ref} · {n_styles} styles, {_units(units)}"
            detail = f"Top up {ref} to {L_TARGET_TEXT}: {_units(units)} worth {_inr(mrp)} at MRP."
        elif kind == "MIN_DISPLAY":
            cats = sorted({g["category"] for g in gs})
            title = f"{ref} is below minimum display in {', '.join(cats)}: {_units(units)}"
            detail = f"Bring {ref} back to its tier minimum display ({st.at[ref, 'tier']} tier) with {_units(units)}."
        elif kind == "AGEING":
            title = f"{_fmt_units(units)} aged units are not selling where they sit"
            detail = (f"Stock older than {C.AGEING_DAYS_CORE} days (core) / {C.AGEING_DAYS_FASHION} days (fashion) selling "
                      f"<= 0.02/day: {_units(units - back)} move to stores that sell them, {_fmt_units(back)} go back to WH.")
        elif kind == "SOLD_OUT_CONSOLIDATION":
            styles = len({g["style_id"] for g in gs})
            title = f"{styles} styles sold out at the WH: {_units(units)} consolidated between stores"
            detail = f"No warehouse stock for these styles, so slow stores' surplus ({_units(units)}, {_inr(mrp)}) moves to stores that sell them."
        else:  # OVERSTOCK
            title = f"{_units(units)} are overstocked (> 120 days of cover)"
            detail = (f"Deep cover rows: {_units(units - back)} go to stores that need them, "
                      f"{_fmt_units(back)} go back to WH.")
        cards.append({"problem_id": None, "kind": kind, "title": title, "detail": detail,
                      "group_ids": [g["group_id"] for g in gs],
                      "_order": CARD_ORDER.index(bucket), "_rank": sum(g["priority"] for g in gs)})
    cards.sort(key=lambda c: (c["_order"], -c["_rank"], c["title"]))
    for i, c in enumerate(cards, 1):
        c["problem_id"] = f"P{i:02d}"
        c.pop("_rank")
        c.pop("_order")
    return cards


L_TARGET_TEXT = f"lead time + {C.REVIEW_DAYS} review + {C.SAFETY_DAYS} safety days of cover"


# ---------------------------------------------------------------- materiality
MATERIAL_RAR = 10_000                   # Rs revenue at risk a routine group must protect to be shown today
MAX_ITERATIONS = 4      # retained revenue at risk plateaus by the 3rd re-run (~1.5 s each)


def ban_key(typ: str, kind: str, frm: str, to: str, style: str, ship_on) -> tuple:
    """The group key with any donor for store->store (banning one donor only makes the next donor's small
    group). Kind, route and ship date stay in the key so a big WH send is never banned for a small
    store->store or later-dated group of the same style."""
    return (typ, kind, frm if frm == C.WH_ID else "*", to, style, pd.Timestamp(ship_on))


def _group_key(g: dict) -> tuple:
    return ban_key(g["type"], g["problem_kind"], g["from"], g["to"], g["style_id"], g["ship_on"])


def is_material(g: dict) -> bool:
    """Shown today if it protects >= Rs 10,000, or is a new launch / min display move, or is a pull-back.
    Rulings (S0's list kept every CAPACITY and AGEING group, which gave ~480 groups): AGEING and CAPACITY
    store->store moves face the revenue bar like routine moves. A held-back CAPACITY unit joins the store's
    CAPACITY pull-back for that style, so the over-capacity store still releases every unit, in fewer groups."""
    return (g["revenue_at_risk"] >= MATERIAL_RAR or g["type"] == "PULL_BACK"
            or g["problem_kind"] in ALWAYS_MATERIAL)


def _safe_to_drop(L: Ledger, g: dict) -> bool:
    """A small group left after the last re-run may be dropped only if no rule can break: WH sends (less
    stock at the receiver, less WH supply used), or a store->store give whose giver started within
    capacity and fits capacity even if every receipt lands before every give (S3 replays by date, then
    group order). Pull-backs are always material, so they never get here."""
    if g["from"] == C.WH_ID:
        return True
    giver = g["from"]
    start = L.store_start.get(giver, 0)
    return start <= L.capacity[giver] and start + L.store_in[giver] <= L.capacity[giver]


def _run_passes(data: Data, feats: Features, banned: set) -> tuple[Ledger, list[dict]]:
    L = Ledger(data, feats)
    L.banned = banned
    pass1_capacity_overstock(L)
    pass5a_ageing_to_sellers(L)
    pass2_store_to_store(L)
    pass3_wh_to_store(L)
    pass4_min_display(L)
    pass5b_ageing_pull_back(L)
    return L, assemble_groups(L)


# ---------------------------------------------------------------- entry
def generate_moves(data: Data, feats: Features) -> dict:
    """Run all passes; hold back immaterial groups by banning their ban_key() and re-running (up to
    MAX_ITERATIONS), so freed stock and capacity flow to material moves and the ledger re-checks every
    rule. Small groups still left are dropped only when _safe_to_drop() proves no rule can break.
    `deferred` = the small groups of the first run (what the full plan would have shown)."""
    banned: set[tuple] = set()
    deferred = {"groups": 0, "units": 0, "revenue_at_risk": 0.0}
    for it in range(MAX_ITERATIONS):
        L, groups = _run_passes(data, feats, banned)
        small = [g for g in groups if not is_material(g)]
        if it == 0:
            deferred = {"groups": len(small), "units": int(sum(g["qty"] for g in small)),
                        "revenue_at_risk": round(float(sum(g["revenue_at_risk"] for g in small)), 2)}
        if not small or it == MAX_ITERATIONS - 1:
            break
        banned |= {_group_key(g) for g in small}
    groups = [g for g in groups if is_material(g) or not _safe_to_drop(L, g)]
    for i, g in enumerate(groups, 1):
        g["group_id"] = f"G{i:03d}"
    explain_groups(groups, data, feats)
    return {"groups": groups, "problems": build_problems(groups, data, feats), "deferred": deferred}
