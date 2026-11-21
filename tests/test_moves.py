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
