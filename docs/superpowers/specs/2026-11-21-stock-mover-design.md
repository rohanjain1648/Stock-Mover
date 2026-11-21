# Stock Mover — Design

Date: 2026-11-21 · Hackathon: Vedant Fashions (Manyavar) × Calcutta AI Club, VCH3 · Problem B
Submission locks **16:45 IST today**: live link, repo, ≤2-min demo video, 2-line description.

---

## 1. Intent

Every morning, find Manyavar stock that is in the wrong place and hand a merchandiser a
**ready-to-approve list** — warehouse → store sends, store → store moves, pull-backs —
that they can approve in **ten minutes**, where **every move makes sense in one line**
and **no rule is broken**. It must **run on its own**.

Judges will: (1) check we found the stock problems they planted, (2) spot-check numbers,
(3) check no rule is broken, (4) check it runs unattended. "A product with zero sales isn't
always a slow product."

### Goals
- Correct, stock-out-corrected, season-aware **velocity** per store × SKU (everything follows from it).
- Moves covering all four brief cases: WH→store under scarcity, under-stocked stores, store→store, ageing.
- A **rule validator** independent of the move generator; UI shows "0 rule breaks".
- One-line, number-backed explanation per move (deterministic, never invented).
- Approve / reject per move and per group; export approved list.
- Daily unattended run with a visible run history; notifications to merchandiser and area managers.

### Non-goals
- Transport cost optimisation (brief says ignore it).
- Store Coach (Problem A) features: salespeople, roster, conversion coaching.
- Auth, multi-tenant, real ERP integration.

### Anti-goals (fails even if it "works")
- Any rule violation in the output.
- Treating sold-out styles as slow movers (pulling back or ignoring them).
- An LLM generating quantities or numbers in explanations.
- A wall of 2,000 SKU-level rows nobody can approve in 10 minutes.
- Missing the 16:45 deadline or shipping without the demo video.

---

## 2. Constraints

- Time: ~5 h of build. Feature freeze 15:30, video 15:30–16:15, submit by 16:30.
- Data: `manyavar-vch3-data/csv/` (17 tables). "Today" = close of **2026-10-31** (read from `stock_snapshot.as_of_date`, never hard-code).
- Rules (from `rules.csv`, all hard unless noted):
  1. **Min display**: each store keeps ≥ `min_display_units` per tier × category group. "Accessories (Safa/Mala/Stole)" = Safa + Mala + Stole summed. A giver must not drop below it.
  2. **Flagship protection**: S++ stores (LKO-01, PAT-01, BLR-01, BLR-02) never give away stock of their top-20 styles (`flagship_protected`, style-level, all sizes) — no store→store, no pull-back.
  3. **Capacity**: never send a store more than `stock_capacity_units` (on_hand + in_transit + inbound moves − outbound moves).
  4. **In-transit** counts as arriving. Never send it twice.
  5. **Donor cover**: no store→store transfer if the giver drops below **30 days of cover for that style** (style-level, per `rules.csv` wording).
  6. **Approval** (flag, not block): any single move worth > ₹1,00,000 at MRP needs human approval.
  7. **Replenishment cycle**: company tops up Mondays; we may recommend any day.
  8. **Logistics**: ignore cost; lead time matters (`lead_times.csv`, route sentence → map by zone/city).
- Lead times: WH→East 3 d, WH→North 4 d, WH→South 6 d; store→store same city 2, same zone 4, different zone 7. Store→WH pull-back = same as WH→that store's zone (our call).

---

## 3. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | Streamlit + daily GitHub Action | Fastest, one language, plain look | Not picked |
| **B** | **FastAPI backend + React (Vite/shadcn) frontend, reusing OptiLogiX** | Most polished; two deploys; splits cleanly into parallel sessions | **Picked by user** |
| C | Static page fed by daily job JSON | Strong "runs on its own"; approvals only in browser | Not picked |

B was picked. Its risk (two services in 5 h) is mitigated by **contract-first parallel work**
(§9) and a **bundled snapshot fallback** in the frontend (§7).

---

## 4. Architecture

```
                        ┌──────────────────────────── GitHub Actions (cron 07:00 IST) ──┐
                        │  POST /api/runs  (token)  + keep-warm ping                     │
                        └───────────────────────────────┬────────────────────────────────┘
                                                        ▼
 data/csv/*.csv ──► ENGINE (python package `engine/`) ──► run JSON (contract C2) ──► BACKEND (FastAPI, Render)
   load+clean        velocity → position → moves         outputs/runs/<run_id>.json      /api/runs/latest
   quality flags     → validator → explain                outputs/latest.json             /api/moves/{id}/decision
                                                                                         /api/stores  /api/export.csv
                                                         SQLite: decisions, runs,        /api/notifications/today
                                                         alert counts                    APScheduler 07:00 IST
                                                                                               │
                         FRONTEND (React/Vite/shadcn, Vercel) ◄─────── REST (VITE_API_URL) ────┘
                         Today list · Stores · Findings · Runs        fallback: public/sample_run.json

 NOTIFY: backend builds digest + AM alerts (≤5/AM/week) + approval requests
         ├─ Gmail SMTP (automatic, every run)
         └─ Fo (Wajo) via Claude Code + `wajo-fo` MCP: `/dispatch-alerts` skill → email/call AMs
            (+ stretch: Sarvam Hindi TTS briefing mp3)
```

### Repo layout and ownership (each path has exactly one owning session)

```
Stock-Mover/
├── contracts/                 S0  run.schema.json, sample_run.json, api.md, features.md
├── data/csv/                  S0  the 17 CSVs (see open question Q1)
├── engine/                        python package
│   ├── config.py              S0  constants: rules, lead times, thresholds, paths
│   ├── interfaces.py          S0  stage seams with fallbacks (so every session runs end-to-end at once)
│   ├── naive.py               S0  placeholder features until S1 lands
│   ├── data.py                S0  load, type, clean, accessory group, lead_days(), protected_styles()
│   ├── run.py                 S0  orchestration CLI: python -m engine.run → outputs/  (calls validator)
│   ├── velocity.py            S1  de-censored, shrunk, season-adjusted daily rate
│   ├── position.py            S1  available, cover, targets, need/excess per store×SKU and style
│   ├── moves.py               S2  ledger + move generators (5 passes, §5.5)
│   ├── explain.py             S2  one-line explanations from numbers
│   ├── rules.py               S3  independent validator over a run
│   └── quality.py             S3  data-quality + non-move findings (flags)
├── tests/                     S3  test_rules.py, test_planted.py (acceptance), test_velocity.py
├── backend/                   S4  FastAPI app, SQLite, scheduler, notify, Dockerfile, render.yaml
├── .github/workflows/         S4  daily-run.yml, keep-warm
├── frontend/                  S5  Vite React TS + shadcn (copied from OptiLogiX), vercel.json
├── .claude/skills/dispatch-alerts/  S6  Fo MCP dispatch skill
└── docs/                      S0  this spec, plans, demo script, README
```

---

## 5. Engine design

### 5.1 Data prep (S1, `data.py`)
- Read all CSVs with `dtype=str`, convert numeric columns explicitly. IDs stay strings.
- Exclude packaging (`is_packaging=1`) from sales and stock math.
- Category group: Safa/Mala/Stole → "Accessories (Safa/Mala/Stole)" for min-display only.
- Negative `on_hand` (MYS-02 KUR-02-M = −4) → treat as 0, emit DATA_QUALITY flag "stock count needed".
- Lead-time lookup built from zone/city, not by parsing the sentence loosely.
- WH availability timeline: `WH-KOL on_hand` today + `warehouse_inbound` by `expected_date`
  (2026-11-01, 11-03, 11-16, 12-01, 12-16).

### 5.2 Velocity (S1, `velocity.py`) — the heart
For each store × SKU, output `vel_daily` (forecast units/day for the next ~30 days) plus its parts:
1. **In-stock-day rate**: over the 84 days covered by `stock_weekly` (weeks ending 2026-08-15 … 10-31),
   `rate_instock = units_sold / in_stock_days`, where `in_stock_days = max(Σ days_in_stock, days with a sale)`
   (191 units were sold in weeks marked 0 days in stock — the column is not fully reliable).
   Require ≥ 7 in-stock days to trust it.
2. **Shrinkage for sparse SKUs**: blend with `style rate at this store × size share`
   (size share from chain 12-month sales of that style/category); weight
   `w = in_stock_days / (in_stock_days + 28)`.
3. **Never-stocked / out-of-stock-all-window**: use peer stores (same tier, same zone, else same tier)
   rate for that SKU, scaled by store volume ratio. This is what makes LKO-01/MZF-01 show demand for KUR-04.
4. **New store BLR-05** (opened 2026-10-10): peer-based (B tier, South + Bengaluru) — not its 3-week ramp.
5. **New style KUR-04** (launched 2026-09-20, in stores from ~10 Oct): in-stock-day rate handles it.
6. **Season lift** per state (and category if cheap): `lift = LY festive-season daily rate ÷ LY off-season
   daily rate`, festive season located from `calendar` (Diwali −10 d through the wedding dates),
   applied to this year's de-censored base. Cap 1.0–3.5. Diwali is **8 Nov 2026** (was 20 Oct 2025);
   Chhath 15 Nov (Bihar); wedding dates 20 Nov – 12 Dec in all three states.
   **Sanity check**: chain forecast for the next 30 days should land ~300–450 units/day
   (Nov 2025 actual 434/day; Aug–Oct 2026 ran 163/day). A plain 90-day average under-sends ~2.7×.
- Expose components (`rate_instock`, `rate_shrunk`, `lift`, `vel_daily`, `basis`) so explanations can cite them.

### 5.3 Position (S1, `position.py`)
- `available = max(on_hand,0) + in_transit` (in-transit arriving 11-01/11-02 counts).
- `cover_days = available / vel_daily` (∞ when vel = 0).
- Targets per store: `target_days = lead_time_WH(zone) + review 7 + safety 7`.
- `need_units = max(0, ceil(vel_daily × target_days) − available)`, raised to fill category min-display deficit.
- `excess_units` for donors = units above **max(30 days style cover, min-display share)**; S++ protected styles → 0.
- Store totals: `units`, `capacity`, `utilisation`, category vs min display.
- Ages: `age_days = as_of − oldest_stock_received_on` (blank only when on_hand = 0).

### 5.4 Contract C1 — features (S1 → S2/S3)
Two DataFrames returned by `engine.interfaces.build_features(data) -> Features`:
- `sku_pos` one row per location × SKU (stores + WH):
  `location_id, sku_id, style_id, style_name, category, cat_group, size, mrp, is_core,
   tier, city, zone, on_hand, in_transit, available, sold_84, in_stock_days, rate_instock,
   vel_daily, lift, basis, cover_days, age_days, need_units, excess_units, is_protected`
- `store_pos` one row per store: `store_id, tier, city, zone, capacity, units, utilisation,
   cover_days, below_min_categories (list)`
- plus `wh_timeline`: `sku_id, date, cumulative_available`.
S0 ships naive versions (90-day calendar rate, no lift) so S2/S3 can start immediately; S1 replaces internals, **same columns**.

### 5.5 Moves (S2, `moves.py`) — one shared ledger, five passes
A **ledger** tracks projected stock per location × SKU and per store total; every pass reads and writes it,
so nothing is double-counted and capacity / min display / donor cover are checked at the moment of allocation.

1. **Capacity breaches & gross overstock** (e.g. KNP-03 at 208%, 300 × SHW-02-L received 2026-09-03,
   chain sells ~40 in 90 days): move excess to stores with need (store→store, nearest first),
   remainder → **pull back to WH-KOL**.
2. **Store→store rebalancing**: for each receiver need, find donors with `excess_units` (same city 2 d →
   same zone 4 d → other zone 7 d). Prefer when WH has none or donor is faster. Covers sold-out fashion
   styles (KUR-12/15/18/24, MOJ-03/06, JKT-06, STL-03) by consolidating stragglers to where they sell.
3. **Warehouse → store allocation under scarcity**: supply = WH on hand + inbound by date. If total need
   ≤ supply, fill all. Else allocate by priority: (a) every selling store gets presentation minimum
   (1 per core size it sells), (b) then by revenue-at-risk = expected lost units before next replenishment ×
   price, weighting days-to-stock-out vs lead time and festival dates. Sends dated `ship_on` = date stock
   is available; `arrives_on = ship_on + lead`. Key cases: KUR-01 (core bestseller, stores at 1–8/size,
   Nov need ≫ supply), KUR-04 (new launch, LKO-01 and MZF-01 hold none).
4. **Under-stocked stores & min display**: fill category deficits (BLR-05 Sherwani 2 vs 5,
   MZF-01 Mojari 5 vs 8; MZF-01 at 37% utilisation, 29 d cover) using best-selling SKUs of that category for the store.
5. **Ageing**: units with `age_days > 180` (or > 90 for fashion `is_core=0`) at stores where they don't sell →
   to the store with the highest rate for that SKU, arriving before 12 Dec (end of wedding dates);
   if no store sells it (e.g. JKT-08 Neon Lime, 36 sold ever) → pull back / consolidate + DEAD_STOCK flag.

**Approvable unit** = one *style* × from × to × type (sizes grouped, size breakdown shown). The ₹1 lakh
approval threshold applies to that unit (conservative). SKU-level lines stay in the JSON for audit.

### 5.6 Validator (S3, `rules.py`) — written independently of `moves.py`
Re-derives start positions from raw data, replays all moves in date order, and asserts every rule in §2
for every move and every end state. Output `validation = {passed, checked_moves, violations[]}` embedded in
the run JSON. Also asserts: no move of qty ≤ 0, no SKU sent to a store and pulled from it the same run,
WH never negative on any date. `run.py` **fails the run** (non-zero exit, no publish) if violations > 0.

### 5.7 Explanations (S2, `explain.py`)
Template per type, numbers only from the ledger/features. Examples:
- `PULL/S2S` "KNP-03 → PAT-01 · 40 × SHW-02 (L): KNP-03 holds 300 L (store at 208% capacity, ~8 yrs cover); PAT-01 has 4, sells 0.3/day ×2.4 festive lift; arrives 4 Nov."
- `WH→STORE` "WH → LKO-01 · 26 × KUR-04 (M4 L8 XL8 XXL4 XXXL2): new launch selling 38/day chain-wide, LKO-01 holds none; peers its tier sell 3.1/day."
Optional LLM polish of wording is a stretch and must never change numbers.

### 5.8 Prioritisation & the 10-minute view
`priority = revenue_at_risk (₹)` for sends, `₹ freed / capacity relieved` for pull-backs.
Moves are clustered into **headline problems** (problem cards) — each card = one finding with its moves,
batch-approvable. Long tail collapsed under "Other moves".

### 5.9 Flags (non-move findings, S3 `quality.py`)
`DATA_QUALITY` (negative stock, sales while 0 days in stock), `REORDER` (sold-out fashion styles with no
inbound — buyer action, not a move), `DEAD_STOCK` (JKT-08), `NEW_STORE` (BLR-05 velocity is peer-based),
`CAPACITY` (KNP-03).

### 5.10 Planted-problem acceptance list (S3 `tests/test_planted.py`; must all pass)
| # | Problem | Expected in output |
|---|---|---|
| P1 | KNP-03: 300 × SHW-02-L, 208% capacity | moves out of KNP-03 for SHW-02-L (to need stores and/or WH); CAPACITY flag; KNP-03 receives nothing |
| P2 | MZF-01 under-stocked (37% util, 29 d cover, Mojari < min) | WH→MZF-01 sends incl. Mojari to ≥ 8 |
| P3 | KUR-04 new launch missing at LKO-01, MZF-01 | WH→LKO-01 and WH→MZF-01 KUR-04 sends |
| P4 | KUR-01 scarce core bestseller | scarcity allocation across stores; no store over-served |
| P5 | Sold-out 2025 fashion styles | never classed slow; REORDER flags; S2S consolidation where stragglers exist |
| P6 | JKT-08 genuinely dead | pull-back/consolidation + DEAD_STOCK flag |
| P7 | BLR-05 new store, Sherwani < min | Sherwani to ≥ 5; NEW_STORE flag |
| P8 | Ageing stragglers (1,458 units > 180 d) | ageing moves to selling stores |
| P9 | MYS-02 KUR-02-M = −4 | DATA_QUALITY flag; treated as 0 |
| P10 | Festive lift | chain 30-day forecast in 300–450/day band |

---

## 6. Backend (S4, FastAPI on Render)

Pattern copied from OptiLogiX `georisk_backend/main.py` (lifespan, CORS, routers, pydantic v2).
- `GET  /api/health`
- `GET  /api/runs/latest` → run JSON (C2) merged with decisions
- `GET  /api/runs` → history `[run_id, started_at, trigger (schedule|github|manual), n_moves, passed]`
- `POST /api/runs` (header `X-Run-Token`) → runs engine in-process (~seconds), stores JSON, sends notifications
- `GET  /api/stores` → `store_pos` + per-store inbound/outbound moves
- `POST /api/moves/{group_id}/decision` `{decision: approve|reject, note?, by?}`; `POST /api/groups/decision` batch
- `GET  /api/export.csv?status=approved`
- `GET  /api/notifications/today` → C4 `{digest, am_alerts[], approval_requests[]}`
- SQLite (`backend/state.db`): runs, decisions, alerts_sent (for the 5-per-AM-per-ISO-week cap).
- APScheduler daily 07:00 IST + GitHub Actions cron calling `POST /api/runs` (proof in Actions history) and a keep-warm ping.
- Notify: Gmail SMTP (env `SMTP_USER`, `SMTP_APP_PASSWORD`, `DIGEST_TO`) on every run; skipped silently if unset.

### Contract C2 — run JSON (`contracts/run.schema.json`; S0 writes it + `sample_run.json`)
```
{ run_id, as_of, generated_at, trigger,
  summary: { n_groups, n_moves, units, mrp_value, revenue_protected, by_type{}, stores_touched },
  problems: [ { problem_id, kind, title, detail, group_ids[] } ],
  groups:   [ { group_id, type: WH_TO_STORE|STORE_TO_STORE|PULL_BACK, problem_kind:
                CAPACITY|OVERSTOCK|UNDERSTOCK|SCARCITY|NEW_LAUNCH|MIN_DISPLAY|AGEING|SOLD_OUT_CONSOLIDATION,
                style_id, style_name, category, from, to, ship_on, arrives_on, lead_days,
                sizes: {size: qty}, qty, mrp_value, priority, needs_approval, explanation,
                evidence: { from_cover_before, from_cover_after, to_cover_before, to_cover_after,
                            to_vel_daily, from_vel_daily, lift, age_days, to_capacity_after },
                lines: [ { sku_id, size, qty } ] } ],
  flags:    [ { flag_id, kind, location_id?, sku_id?, style_id?, message } ],
  stores:   [ store_pos rows ],
  validation: { passed, checked_moves, violations: [] } }
```

### Contract C4 — notifications
`digest {subject, text, html, link}`; `am_alerts [{am_id, am_name, city, stores[], items[≤5 this week], text}]`;
`approval_requests [{group_id, mrp_value, text}]`.

---

## 7. Frontend (S5, React on Vercel)

Fresh Vite + React 18 + TS + Tailwind + shadcn; **copy from OptiLogiX**: `src/components/ui/*`,
`tailwind.config.ts`, `src/lib/utils.ts`, `components.json`, the `GeoRiskLayout` shell pattern, recharts,
TanStack Query, sonner toasts. Do **not** copy OptiLogiX's heavy deps (three, ethers, firebase, razorpay).

Screens:
1. **Today** (default): KPI strip (moves, units, ₹ value, revenue protected, **"0 rule breaks"** badge,
   last run time + trigger) → problem cards → grouped approval table (approve / reject / approve-all-in-card,
   filters: type, city, area manager, category, needs-approval) → row expand = evidence + size breakdown.
   Moves > ₹1 lakh pinned with an "Approval needed" badge. "Export approved CSV".
2. **Stores**: 20 stores + WH as cards (or a simple India map): utilisation bar, cover, below-min badges, inbound/outbound.
3. **Findings**: flags grouped by kind (data quality, re-order, dead stock, new store).
4. **Runs**: history table, "Run now", notifications sent (email / Fo).
- `VITE_API_URL` env; if the API is unreachable within 5 s, load bundled `public/sample_run.json`
  (copied from latest real run) and show a "snapshot" banner — the live link never looks broken.

---

## 8. Communications

- **Every run, automatic**: Gmail SMTP digest to merchandiser (summary + top 10 + link).
- **Area managers**: `max_alerts_per_week = 5` → each AM gets at most 5 alerts per ISO week, highest priority first, tracked in SQLite.
- **Fo (Wajo)** via the `wajo-fo` MCP (`https://mcp.api.wajo.ai/fo`, OAuth; user has used Fo before):
  Claude Code skill `/dispatch-alerts` reads `/api/notifications/today` and asks Fo to email the digest,
  call/text each AM with their items, and phone the approver for > ₹1 lakh moves. Run from an interactive
  Claude Code session (OAuth tokens last 1 h), optionally on a local scheduled task. Record a Fo call for the video.
- **Stretch**: Sarvam Hindi TTS 30-second briefing mp3 → `/api/briefing.mp3`, play button on Today.

---

## 9. Parallel build plan

Sessions run in **separate git worktrees**, each on its own branch, editing **only its owned paths**.
When a chunk is done: `git fetch && git rebase origin/main && git push origin HEAD:main` (disjoint paths →
fast-forward, no conflicts). Contracts in `contracts/` change only via S0.

| Session | Owns | Starts | Delivers |
|---|---|---|---|
| **S0 Integrator** (this session) | contracts/, engine/config.py, engine/interfaces.py, data/, docs/, README | now | scaffold + contracts + naive features + sample_run.json pushed by ~12:10; then merges, integration, deploy, video |
| **S1 Demand** | engine/data.py, velocity.py, position.py | after S0 push | real features per C1 + `tests/test_velocity.py` sanity |
| **S2 Moves** | engine/moves.py, explain.py, run.py | after S0 push (uses naive features) | run JSON per C2 from real data |
| **S3 Rules & QA** | engine/rules.py, quality.py, tests/ | after S0 push | validator, flags, planted acceptance tests |
| **S4 Backend** | backend/, .github/workflows/ | after S0 push (serves sample_run.json) | API live on Render, scheduler, SMTP, Action |
| **S5 Frontend** | frontend/ | after S0 push (mocks sample_run.json) | UI live on Vercel |
| **S6 Comms** (S0 after 14:30, or a 6th window) | .claude/skills/dispatch-alerts/, backend/notify_tts.py (stretch) | 14:30 | Fo dispatch, demo call |

### Timeline (IST)
- 12:10 S0 pushes scaffold → S1–S5 start
- 13:30 **Engine integration**: S1+S2+S3 on main, `python -m engine.run` on real data, planted tests green, 0 violations
- 14:15 Backend serves real run; frontend on live API
- 14:45 Both deployed; **live link works**; GitHub Action ran once
- 15:30 **Feature freeze**; refresh `sample_run.json`
- 15:30–16:15 Demo video (≤2 min) + README + two-liner
- 16:30 Submit (locks 16:45)

---

## 10. Calls made by Claude (check these)
- Pull-back lead time = WH→store lead time for that zone.
- Donor 30-day cover checked at **style** level (rules.csv wording), not SKU.
- Approvable unit = style × from × to × type; ₹1 lakh threshold applied to that unit.
- Target cover = WH lead + 7 review + 7 safety days.
- Ageing thresholds: > 180 days, or > 90 days for fashion styles.
- Season lift capped 1.0–3.5, sanity band 300–450 units/day chain-wide.
- Render (Docker) for backend, Vercel for frontend, SQLite for state (resets on redeploy — acceptable for demo).
- Explanations deterministic; LLM wording polish only as stretch.

## 11. Left to the builder
Exact shrinkage weights, lift computation details within the sanity band, priority weighting constants,
UI visual styling, map vs cards on Stores screen.

## 12. Open questions for the user
- **Q1** The repo is public. Commit the Manyavar CSVs (≈15 MB, "belong to Vedant Fashions") so Render can
  build? Alternative: keep data out of git and upload to Render as a disk/secret file (slower to set up).
- **Q2** Do you have Render and Vercel accounts ready (OptiLogiX suggests yes)? Gmail app password for SMTP?
- **Q3** How many parallel Claude windows can you actually drive — 5 (S1–S5) or fewer (then S1+S2 merge, S3 stays separate)?
