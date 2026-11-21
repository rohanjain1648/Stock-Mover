# S1b · Explanations + evidence (handed over from S2 Task 4)

> You are **S1** again. Same rules as S1.md (shared Stock-Mover folder: add only your files by name; never stash/reset/clean/add -A; push with `git pull --rebase --autostash origin main && git push origin HEAD:main`). REQUIRED SUB-SKILL: superpowers:executing-plans. Push by **14:00 IST**.

**Why:** S2's moves are right but explanations are placeholders ("…: new_launch"). Judges read every line. You know the features best, so you own the words and the numbers behind them. S2 keeps `moves.py` and will call your two functions.

**You own (new):** `engine/explain.py`, `tests/test_explain.py`. Do not edit `engine/moves.py` (S2 wires the call).

## Interfaces (frozen)
```python
def evidence_for(group: dict, data: Data, feats: Features) -> dict
def explain_group(group: dict, data: Data, feats: Features) -> str
```
`group` has the C2 keys: `type, problem_kind, style_id, style_name, category, from, to, sizes{size: qty}, qty, mrp_value, lines[{sku_id,size,qty}], ship_on, arrives_on, lead_days`. Compute everything from the **start state** (`feats.sku_pos`, `feats.store_pos`, `feats.wh`, `feats.wh_timeline`, `data`) — not from S2's ledger. Build per-(location, style) and per-style lookup dicts **once** per `feats` (cache keyed on `id(feats)`): ~700 groups must explain in < 1 s total.

`evidence_for` returns exactly these 9 keys (None when not applicable; round to 1 decimal):
- `from_cover_before` / `from_cover_after`: giver's **style-level** days of cover, `Σavailable / Σvel_daily` over the style's SKUs at `from`, before and after removing `qty` (None when `from` is WH-KOL; `None` also when vel is 0, which the UI shows as ∞).
- `to_cover_before` / `to_cover_after`: same at `to`, before and after adding `qty` (None for PULL_BACK).
- `to_vel_daily`, `from_vel_daily`: style-level Σvel_daily at each end (None for WH).
- `lift`: season lift at the receiving store (giver for pull-backs).
- `age_days`: max `age_days` of the style at `from` (None for WH).
- `to_capacity_after`: `(store units + qty) / capacity` at `to`, this move alone (None for WH).

`explain_group` returns one line, ≤ 220 chars, starting `"<FROM> → <TO> · <qty> × <STYLE_ID> (<sizes e.g. M2 L4>): "` (WH-KOL shown as `WH`), then a reason with **at least two real numbers**, plain merchandiser English, no jargon like "vel" or "basis". One template per `problem_kind`:
- `CAPACITY`: "<from> holds <n> of <sku> (store at <util>% of capacity); <to> has <x>, sells <v>/day in festive season." For PULL_BACK: "…no store needs them before 12 Dec; takes <from> from <util>% to <util_after>% of capacity."
- `OVERSTOCK`: "<from> has <cover> days of cover; <to> runs out in <d> days."
- `UNDERSTOCK` (WH): "<to> has <x> left, sells <v>/day (×<lift> festive lift); this covers <d> days, arriving <arrives_on d Mon>." (S2S): add "<from> keeps <c> days of cover."
- `SCARCITY`: "only <supply> arrive for <n_stores> stores by <date>; <to> gets its share — sells <v>/day, has <x>."
- `NEW_LAUNCH`: "new launch (<launch d Mon>) selling <chain>/day chain-wide; <to> holds <x>; similar stores sell <peer>/day."
- `MIN_DISPLAY`: "<to> has <cat_units> <category> vs minimum display <min>."
- `AGEING`: "<age> days old at <from>, sold <s84> there in 12 weeks; <to> sells <v>/day."
- `SOLD_OUT_CONSOLIDATION`: "style sold out chain-wide, nothing inbound; <from> sold <s84> in 12 weeks, <to> sells <v>/day."
Numbers: units as integers, rates 1 decimal, percents integer, dates like "4 Nov".

## Tasks
- [ ] **Test first** — `tests/test_explain.py` builds groups by hand and asserts:
```python
def g(**kw):
    base = {"type": "WH_TO_STORE", "problem_kind": "UNDERSTOCK", "style_id": "KUR-09", "style_name": "x",
            "category": "Kurta Set", "from": "WH-KOL", "to": "PAT-02", "sizes": {"XL": 2}, "qty": 2,
            "mrp_value": 0, "lines": [{"sku_id": "KUR-09-XL", "size": "XL", "qty": 2}],
            "ship_on": "2026-11-01", "arrives_on": "2026-11-04", "lead_days": 3}
    base.update(kw); return base

def test_capacity_pullback(data, feats):
    e = explain_group(g(type="PULL_BACK", problem_kind="CAPACITY", style_id="SHW-02", category="Sherwani",
                        **{"from": "KNP-03", "to": "WH-KOL"}, sizes={"L": 195}, qty=195,
                        lines=[{"sku_id": "SHW-02-L", "size": "L", "qty": 195}], arrives_on="2026-11-05", lead_days=4), data, feats)
    assert e.startswith("KNP-03 → WH · 195 × SHW-02 (L195): ") and "208%" in e and "300" in e

def test_new_launch(data, feats):
    e = explain_group(g(problem_kind="NEW_LAUNCH", style_id="KUR-04", to="LKO-01", sizes={"L": 5}, qty=5,
                        lines=[{"sku_id": "KUR-04-L", "size": "L", "qty": 5}], arrives_on="2026-11-05", lead_days=4), data, feats)
    assert "KUR-04" in e and "LKO-01" in e and "new launch" in e

def test_shape_all_kinds(data, feats):  # every kind: one line, <=220, qty present, >=3 digits; evidence 9 keys
    ...
```
- [ ] Implement, all tests pass, commit + push ("feat(s1): explanations and evidence").
- [ ] Tell the user "explain.py pushed" so S2 can wire it (S2's update note already tells it how).
