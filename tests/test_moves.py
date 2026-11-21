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
