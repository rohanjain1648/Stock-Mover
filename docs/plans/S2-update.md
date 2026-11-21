# S2 · Update from S0 (12:55) — read, then continue

S0 ran the full engine on main: **682 groups, 7 rule violations, 0 problems**, explanations placeholder. Changes to your plan:

1. **Fix the 7 DONOR_COVER violations (top priority).** All are KNP-03 giving away its last units of slow styles in pass 1 (e.g. G344 `KNP-03 → LKO-01 KUR-22-S: keeps 1 at 0.09/day = 11 days < 30`). The capacity pass may only use STORE_TO_STORE where `give_limit(for_s2s=True)` allows (style cover ≥ 30 days after); everything else KNP-03 must shed goes as PULL_BACK (rule 5 does not apply to pull-backs). Run `python -m engine.run` (strict) until it prints `validation passed=True`.

2. **Materiality: the list must be approvable in 10 minutes.** 533 of 682 groups are 1–2 units. Keep a group only if `revenue_at_risk ≥ 10_000` **or** `problem_kind ∈ {CAPACITY, NEW_LAUNCH, MIN_DISPLAY, AGEING}` **or** `type == "PULL_BACK"`. Apply it so the validator stays green: either skip below-bar candidates inside the passes, or prune after the passes and re-check (never drop a move whose removal would push a store over capacity). Target ≈ 250–300 groups (S0 measured: 265 groups keep 88% of revenue at risk). Return the held-back totals as a new key:
   `generate_moves(...) -> {"groups": [...], "problems": [...], "deferred": {"groups": int, "units": int, "revenue_at_risk": float}}`
   (`engine/run.py` on main already copies it into `summary.deferred`.) Add a test: `len(res["groups"]) <= 320` and `res["deferred"]["groups"] > 0`.

3. **Task 4 (explanations + evidence) moves to S1.** Don't write `engine/explain.py`. In `assemble_groups`, after a group dict is complete, call:
```python
try:
    from engine.explain import explain_group, evidence_for
    g["evidence"] = evidence_for(g, data, feats); g["explanation"] = explain_group(g, data, feats)
except ImportError:
    pass   # keep your placeholder until S1 pushes explain.py
```
   Keep your `test_explanations_are_one_line_with_numbers` test; it will pass once S1 lands.

4. **Problems (Task 3):** besides the headline cards, cluster routine `WH_TO_STORE / UNDERSTOCK` groups into one card **per receiving store**: title `"Routine top-up · PAT-01 · 30 styles, 212 units"`. Order cards: CAPACITY, NEW_LAUNCH, SCARCITY, UNDERSTOCK-store-starved (MZF-01), MIN_DISPLAY, AGEING, SOLD_OUT_CONSOLIDATION, then routine top-ups. Every group in exactly one card.

Order of work: 1 → Task 3 (passes 4–5 + problems with point 4) → 2 → 3 → Task 5. Push after each.
