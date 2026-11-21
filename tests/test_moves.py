import pytest
from engine.data import load_data
from engine.interfaces import build_features

C2_GROUP_KEYS = {"group_id","type","problem_kind","style_id","style_name","category","from","to","ship_on",
                 "arrives_on","lead_days","sizes","qty","mrp_value","revenue_at_risk","priority",
                 "needs_approval","explanation","evidence","lines"}

@pytest.fixture(scope="module")
def ctx():
    data = load_data(); feats = build_features(data)
    from engine.moves import generate_moves
    return data, feats, generate_moves(data, feats)

def test_shape(ctx):
    _, _, res = ctx
    assert res["groups"], "no moves generated"
    for g in res["groups"]:
        assert C2_GROUP_KEYS <= set(g)
        assert g["qty"] == sum(g["sizes"].values()) == sum(l["qty"] for l in g["lines"]) > 0
        assert g["needs_approval"] == (g["mrp_value"] > 100000)
        assert g["type"] in {"WH_TO_STORE","STORE_TO_STORE","PULL_BACK"}

def test_no_protected_style_leaves_spp(ctx):
    data, _, res = ctx
    from engine.data import protected_styles
    prot = protected_styles(data)
    assert not [g for g in res["groups"] if (g["from"], g["style_id"]) in prot]

def test_nothing_sent_to_over_capacity_store(ctx):
    _, _, res = ctx
    assert not [g for g in res["groups"] if g["to"] == "KNP-03"]

def _sum(res, **kw):
    return sum(g["qty"] for g in res["groups"] if all(g[k] == v for k, v in kw.items()))

def test_p1_knp03_releases_shw02(ctx):
    _, _, res = ctx
    assert _sum(res, **{"from": "KNP-03", "style_id": "SHW-02"}) >= 200

def test_p3_kur04_reaches_lko01_and_mzf01(ctx):
    _, _, res = ctx
    assert _sum(res, **{"to": "LKO-01", "style_id": "KUR-04"}) > 0
    assert _sum(res, **{"to": "MZF-01", "style_id": "KUR-04"}) > 0

def test_p4_kur01_spread_not_hoarded(ctx):
    _, _, res = ctx
    kur01 = [g for g in res["groups"] if g["style_id"] == "KUR-01" and g["type"] == "WH_TO_STORE"]
    stores = {g["to"] for g in kur01}
    assert len(stores) >= 8
    assert max(sum(g["qty"] for g in kur01 if g["to"] == s) for s in stores) <= 0.25 * sum(g["qty"] for g in kur01)

def _end_cat_units(data, feats, res, store, cat_group):
    p = feats.sku_pos
    start = p[(p.location_id == store) & (p.cat_group == cat_group)].available.sum()
    cats = data.items.set_index("sku_id").cat_group
    delta = sum((l["qty"] if g["to"] == store else -l["qty"])
                for g in res["groups"] for l in g["lines"]
                if store in (g["to"], g["from"]) and cats[l["sku_id"]] == cat_group)
    return start + delta

def test_p2_mzf01_mojari_reaches_min(ctx):
    data, feats, res = ctx
    assert _end_cat_units(data, feats, res, "MZF-01", "Mojari") >= 8

def test_p7_blr05_sherwani_reaches_min(ctx):
    data, feats, res = ctx
    assert _end_cat_units(data, feats, res, "BLR-05", "Sherwani") >= 5

def test_p6_jkt08_moves_out_of_stores(ctx):
    _, _, res = ctx
    assert any(g["style_id"] == "JKT-08" and g["problem_kind"] == "AGEING" for g in res["groups"])

def test_problems_cover_every_group_once(ctx):
    _, _, res = ctx
    ids = [gid for p in res["problems"] for gid in p["group_ids"]]
    assert sorted(ids) == sorted(g["group_id"] for g in res["groups"])

def test_materiality_cap_and_deferred(ctx):
    _, _, res = ctx
    assert len(res["groups"]) <= 320
    assert res["deferred"]["groups"] > 0 and res["deferred"]["units"] > 0

def test_explanations_are_one_line_with_numbers(ctx):
    pytest.importorskip("engine.explain")
    import re
    _, _, res = ctx
    for g in res["groups"]:
        e = g["explanation"]
        frm = "WH" if g["from"] == "WH-KOL" else g["from"]
        to = "WH" if g["to"] == "WH-KOL" else g["to"]
        assert "\n" not in e and len(e) <= 220, e
        assert e.startswith(f"{frm} → {to} · {g['qty']} × {g['style_id']} ("), e
        reason = e.split("): ", 1)[1]
        assert len(re.findall(r"\d+(?:\.\d+)?", reason)) >= 2, e
