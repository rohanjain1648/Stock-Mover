# Contracts (frozen — change only via S0, the integrator session)

Spec: `docs/superpowers/specs/2026-11-21-stock-mover-design.md`

## C0 — `Data` (engine/data.py, S0)
`load_data() -> Data`; fields and column types are documented on the dataclass.
Packaging is already removed from `items` and `sales`. `snapshot.on_hand` is clipped at 0;
`on_hand_raw` keeps the original. Helpers: `lead_days(src, dst, stores) -> int`,
`protected_styles(data) -> set[(store_id, style_id)]`, `cat_group(category) -> str`.

## C1 — `Features` (engine/interfaces.py; produced by S1, consumed by S2/S3)
`build_features(data) -> Features` calls `engine.velocity.compute_velocity(data)` then
`engine.position.build_positions(data, vel)`; until S1 lands it uses `engine/naive.py`.

| frame | rows | columns |
|---|---|---|
| `vel` (from compute_velocity) | store × SKU full grid (20 × 382) | `store_id, sku_id, sold_84, in_stock_days, rate_instock, lift, vel_daily, basis` |
| `sku_pos` | store × SKU full grid | `location_id, sku_id, style_id, style_name, category, cat_group, size, mrp, is_core, tier, city, zone, on_hand, in_transit, available, sold_84, in_stock_days, rate_instock, lift, vel_daily, basis, cover_days, age_days, need_units, excess_units, is_protected` |
| `store_pos` | one per store | `store_id, tier, city, zone, capacity, units, utilisation, vel_daily, cover_days, below_min (list[str])` |
| `wh` | SKUs at WH-KOL | `sku_id, on_hand, age_days` |
| `wh_timeline` | SKU × date | `sku_id, date, qty, cum_qty` (row at as_of = WH on hand; one row per inbound date) |

Semantics: `vel_daily` = forecast units/day for the next ~30 days (season-adjusted).
`cover_days = available / vel_daily` (inf if vel 0). `need_units` = units to reach
`vel_daily × (lead_WH + 7 + 7)`, raised for min-display deficits. `excess_units` = units above
30 days of cover (0 for protected styles at S++). `basis` ∈ {`instock`, `shrunk`, `peer`, `history`, `new_store_peer`, `not_ranged`, `naive_84d`}.

## C2 — run JSON (engine/run.py writes `outputs/latest.json`; example `contracts/sample_run.json`)
Top level: `run_id, as_of, generated_at, trigger, summary, problems[], groups[], flags[], stores[], validation`.

- `summary`: `n_groups, n_moves, units, mrp_value, revenue_protected, needs_approval, by_type{WH_TO_STORE, STORE_TO_STORE, PULL_BACK}, stores_touched`
- `problems[]`: `problem_id, kind, title, detail, group_ids[]` — one card per headline finding.
- `groups[]` (the approvable unit = one style × from × to × type):
  `group_id, type (WH_TO_STORE|STORE_TO_STORE|PULL_BACK), problem_kind (CAPACITY|OVERSTOCK|UNDERSTOCK|SCARCITY|NEW_LAUNCH|MIN_DISPLAY|AGEING|SOLD_OUT_CONSOLIDATION), style_id, style_name, category, from, to, ship_on, arrives_on, lead_days, sizes{size: qty}, qty, mrp_value, revenue_at_risk, priority, needs_approval, explanation, evidence{from_cover_before, from_cover_after, to_cover_before, to_cover_after, to_vel_daily, from_vel_daily, lift, age_days, to_capacity_after}, lines[{sku_id, size, qty}]`
  - `from`/`to` are store ids or `WH-KOL`. Dates are `YYYY-MM-DD`. Any evidence value may be `null`.
  - `needs_approval = mrp_value > 100000`.
- `flags[]`: `flag_id, kind (DATA_QUALITY|REORDER|DEAD_STOCK|NEW_STORE|CAPACITY), location_id?, sku_id?, style_id?, message`
- `stores[]`: `store_pos` rows (inf → null).
- `validation`: `passed (bool), checked_moves (int), violations[{rule, group_id, detail}]`.
  Rule ids: `MIN_DISPLAY, FLAGSHIP_PROTECTED, CAPACITY, IN_TRANSIT, DONOR_COVER, NEGATIVE_STOCK, WH_NEGATIVE, NON_POSITIVE_QTY, ROUND_TRIP, LEAD_TIME`.

## C3 — REST API (backend/, S4). Base `${VITE_API_URL}` e.g. `https://stock-mover-api.onrender.com`
| method | path | body / query | returns |
|---|---|---|---|
| GET | `/api/health` | | `{status:"ok", latest_run_id, data_as_of}` |
| GET | `/api/runs/latest` | | C2 run, each group gets `decision: "approve"|"reject"|null`, `decision_note` |
| GET | `/api/runs` | | `[{run_id, generated_at, trigger, n_groups, passed}]` newest first |
| POST | `/api/runs` | header `X-Run-Token` (env `RUN_TOKEN`); `?trigger=github|manual` | `{run_id, summary, passed}`; 409 if validation fails (previous run stays live) |
| GET | `/api/stores` | | `[store_pos + {inbound_units, outbound_units, group_ids[]}]` |
| POST | `/api/groups/{group_id}/decision` | `{decision:"approve"|"reject", note?:str, by?:str}` | `{group_id, decision}` |
| POST | `/api/groups/decision` | `{group_ids:[...], decision, note?, by?}` | `{updated:int}` |
| GET | `/api/export.csv` | `?status=approved|rejected|all` (default approved) | CSV one row per **line** (group_id, type, from, to, sku_id, size, qty, ship_on, arrives_on, mrp_value_line, explanation, decision) |
| GET | `/api/notifications/today` | | C4 |
| GET | `/api/notifications/log` | | `[{sent_at, channel:"email"|"fo", to, subject, ok}]` |
| POST | `/api/notifications/log` | `{channel, to, subject, ok}` (used by the Fo dispatch skill) | `{ok:true}` |

CORS: allow the Vercel origin and `http://localhost:5173`.

## C4 — notifications (example `contracts/sample_notifications.json`)
`digest{subject, text, html, link}`, `am_alerts[{am_id, am_name, city, stores[], week, sent_this_week, items[{group_id, text}] (≤ max_alerts_per_week − sent_this_week), text}]`,
`approval_requests[{group_id, mrp_value, text}]` for groups with `needs_approval`.
