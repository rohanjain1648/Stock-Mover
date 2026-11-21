"""Writes contracts/sample_run.json and sample_notifications.json (C2 / C4 shapes).

Real store rows from the engine + hand-made illustrative groups. Owned by S0.
Run: python -m scripts.make_sample_run
"""
import json

from engine.data import load_data
from engine.interfaces import build_features
from engine.run import _clean, _summary

data = load_data()
f = build_features(data)
by_style = data.items.groupby("style_id").first()
mrp, names, cats = by_style["mrp"].to_dict(), by_style["style_name"].to_dict(), by_style["category"].to_dict()


def g(gid, typ, kind, style, frm, to, ship, arr, lead, sizes, rar, expl, ev):
    qty = sum(sizes.values())
    val = qty * mrp[style]
    return {"group_id": gid, "type": typ, "problem_kind": kind, "style_id": style, "style_name": names[style],
            "category": cats[style], "from": frm, "to": to, "ship_on": ship, "arrives_on": arr, "lead_days": lead,
            "sizes": sizes, "qty": qty, "mrp_value": val, "revenue_at_risk": rar,
            "priority": rar if rar else val * 0.1, "needs_approval": val > 100000,
            "explanation": expl, "evidence": ev,
            "lines": [{"sku_id": f"{style}-{s}", "size": s, "qty": q} for s, q in sizes.items()]}


def ev(fcb=None, fca=None, tcb=None, tca=None, tv=None, fv=None, lift=1.0, age=None, cap=None):
    return {"from_cover_before": fcb, "from_cover_after": fca, "to_cover_before": tcb, "to_cover_after": tca,
            "to_vel_daily": tv, "from_vel_daily": fv, "lift": lift, "age_days": age, "to_capacity_after": cap}


groups = [
    g("G001", "STORE_TO_STORE", "CAPACITY", "SHW-02", "KNP-03", "PAT-01", "2026-11-01", "2026-11-08", 7, {"L": 12}, 180000,
      "KNP-03 → PAT-01 · 12 × SHW-02 (L): KNP-03 holds 300 L (store at 208% capacity); PAT-01 has 4, sells 0.33/day ×2.4 festive lift.",
      ev(2700, 2590, 5, 20, 0.8, 0.11, 2.4, 58, 0.78)),
    g("G002", "PULL_BACK", "CAPACITY", "SHW-02", "KNP-03", "WH-KOL", "2026-11-01", "2026-11-05", 4, {"L": 250}, 0,
      "KNP-03 → WH-KOL · 250 × SHW-02 (L): no store needs them before 12 Dec; takes KNP-03 from 208% to 108% of capacity.",
      ev(2700, 300, None, None, None, 0.11, 2.4, 58, None)),
    g("G003", "WH_TO_STORE", "NEW_LAUNCH", "KUR-04", "WH-KOL", "LKO-01", "2026-11-01", "2026-11-05", 4,
      {"M": 5, "L": 9, "XL": 8, "XXL": 4, "XXXL": 1}, 96000,
      "WH → LKO-01 · 27 × KUR-04: new launch selling 38/day chain-wide; LKO-01 (S++) holds none; S++ peers sell 1.6/day.",
      ev(None, None, 0, 17, 1.6, None, 2.2, None, 0.8)),
    g("G004", "WH_TO_STORE", "UNDERSTOCK", "MOJ-01", "WH-KOL", "MZF-01", "2026-11-01", "2026-11-04", 3,
      {"7": 1, "8": 2, "9": 2, "10": 1}, 14000,
      "WH → MZF-01 · 6 × MOJ-01: Mojari at 5 vs min display 8; MZF-01 at 37% capacity with 29 days cover.",
      ev(None, None, 9, 21, 0.3, None, 2.6, None, 0.39)),
    g("G005", "WH_TO_STORE", "SCARCITY", "KUR-01", "WH-KOL", "PAT-01", "2026-11-01", "2026-11-04", 3,
      {"L": 10, "XL": 12, "XXL": 4}, 62000,
      "WH → PAT-01 · 26 × KUR-01: core bestseller, PAT-01 down to 2 units; only 190 arrive 1 Nov for 20 stores, PAT-01 gets its share by revenue at risk.",
      ev(None, None, 1, 12, 2.1, None, 2.7, None, 0.79)),
    g("G006", "STORE_TO_STORE", "SOLD_OUT_CONSOLIDATION", "KUR-15", "KNP-02", "LKO-02", "2026-11-01", "2026-11-05", 4,
      {"M": 1, "XXXL": 1}, 3500,
      "KNP-02 → LKO-02 · 2 × KUR-15: style sold out chain-wide (nothing inbound); KNP-02's units unsold for 84 days, LKO-02 sold 59 last year.",
      ev(None, None, 0, 6, 0.3, 0.0, 2.0, 200, 0.8)),
    g("G007", "PULL_BACK", "AGEING", "JKT-08", "LKO-03", "WH-KOL", "2026-11-01", "2026-11-05", 4,
      {"S": 1, "M": 2, "L": 2, "XL": 2, "XXL": 1}, 0,
      "LKO-03 → WH-KOL · 8 × JKT-08: Neon Lime jacket, 36 sold chain-wide ever; 240+ days old; no store sells it.",
      ev(None, None, None, None, None, 0.0, 1.0, 244, None)),
    g("G008", "WH_TO_STORE", "MIN_DISPLAY", "SHW-01", "WH-KOL", "BLR-05", "2026-11-01", "2026-11-07", 6,
      {"M": 1, "L": 1, "XL": 1}, 8000,
      "WH → BLR-05 · 3 × SHW-01: new store (opened 10 Oct) has 2 Sherwanis vs min display 5; velocity from peer B stores.",
      ev(None, None, 12, 30, 0.1, None, 2.0, None, 0.87)),
]
problems = [
    {"problem_id": "P-CAP-KNP-03", "kind": "CAPACITY", "title": "KNP-03 is at 208% of capacity",
     "detail": "300 × SHW-02-L arrived 3 Sep; the chain sells ~40 of this SKU in 90 days.", "group_ids": ["G001", "G002"]},
    {"problem_id": "P-NEW-KUR-04", "kind": "NEW_LAUNCH", "title": "New launch KUR-04 missing at LKO-01 and MZF-01",
     "detail": "808 sold in October; 4,378 arriving Nov–Dec.", "group_ids": ["G003"]},
    {"problem_id": "P-UND-MZF-01", "kind": "UNDERSTOCK", "title": "MZF-01 is starved",
     "detail": "37% of capacity, 29 days cover, Mojari below minimum display.", "group_ids": ["G004"]},
    {"problem_id": "P-SCA-KUR-01", "kind": "SCARCITY", "title": "KUR-01 bestseller can't cover everyone in November",
     "detail": "Stores hold 1–8 per size; November need is about 3× supply.", "group_ids": ["G005"]},
    {"problem_id": "P-OTHER", "kind": "AGEING", "title": "Other moves",
     "detail": "Consolidation, ageing and min-display fills.", "group_ids": ["G006", "G007", "G008"]},
]
flags = [
    {"flag_id": "F001", "kind": "DATA_QUALITY", "location_id": "MYS-02", "sku_id": "KUR-02-M", "style_id": "KUR-02",
     "message": "On hand is -4 in the snapshot; treated as 0. Stock count needed."},
    {"flag_id": "F002", "kind": "REORDER", "location_id": None, "sku_id": None, "style_id": "KUR-18",
     "message": "Sold out chain-wide, nothing inbound. Zero recent sales means sold out, not slow. Buyer to re-order."},
    {"flag_id": "F003", "kind": "DEAD_STOCK", "location_id": None, "sku_id": None, "style_id": "JKT-08",
     "message": "In stock at 15 locations for 12 weeks; 36 sold ever. Consolidate and mark down."},
    {"flag_id": "F004", "kind": "NEW_STORE", "location_id": "BLR-05", "sku_id": None, "style_id": None,
     "message": "Opened 10 Oct 2026; velocity borrowed from peer B stores."},
    {"flag_id": "F005", "kind": "CAPACITY", "location_id": "KNP-03", "sku_id": None, "style_id": None,
     "message": "520 units in a 250-unit store (208%)."},
]
touched = {x["from"] for x in groups} | {x["to"] for x in groups}
touched.discard("WH-KOL")
run = _clean({"run_id": "SAMPLE", "as_of": data.as_of, "generated_at": "2026-11-21T07:00:00+05:30",
              "trigger": "schedule", "summary": _summary(groups, touched), "problems": problems,
              "groups": groups, "flags": flags, "stores": f.store_pos.to_dict("records"),
              "validation": {"passed": True, "checked_moves": sum(len(x["lines"]) for x in groups), "violations": []}})
with open("contracts/sample_run.json", "w", encoding="utf-8") as fh:
    json.dump(run, fh, indent=1, ensure_ascii=False)

notif = {
    "digest": {"subject": "Stock Mover · 31 Oct 2026 · 8 moves to approve (2 need sign-off)",
               "text": "8 moves, 315 units. Top: KNP-03 at 208% capacity (release 262 SHW-02-L); new launch KUR-04 to LKO-01; MZF-01 Mojari below min. 0 rule breaks. Approve: https://stock-mover.vercel.app/",
               "html": "<h2>8 moves to approve</h2><p>0 rule breaks.</p>",
               "link": "https://stock-mover.vercel.app/"},
    "am_alerts": [{"am_id": "AM-02", "am_name": "Alok Tiwari", "city": "Kanpur", "stores": ["KNP-01", "KNP-02", "KNP-03"],
                   "week": "2026-W44", "sent_this_week": 1,
                   "items": [{"group_id": "G001", "text": "KNP-03 → PAT-01 · 12 × SHW-02 (L)"},
                             {"group_id": "G002", "text": "KNP-03 → WH-KOL · 250 × SHW-02 (L)"}],
                   "text": "KNP-03 is at 208% capacity. Please release 262 SHW-02-L: 12 to PAT-01, 250 back to WH-KOL."}],
    "approval_requests": [{"group_id": "G001", "mrp_value": groups[0]["mrp_value"],
                           "text": "Approve 12 × SHW-02-L KNP-03 → PAT-01?"}],
}
with open("contracts/sample_notifications.json", "w", encoding="utf-8") as fh:
    json.dump(notif, fh, indent=1, ensure_ascii=False)
print("ok", run["summary"])
