def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["data_as_of"] == "2026-10-31"


def test_latest_has_groups_with_decision_field(client):
    run = client.get("/api/runs/latest").json()
    assert run["groups"] and all("decision" in g for g in run["groups"])
    assert run["validation"]["passed"] is True


def test_latest_is_sample_until_a_run_exists(client):
    run = client.get("/api/runs/latest").json()
    assert run["is_sample"] is True
    assert client.get("/api/health").json()["latest_run_id"] == run["run_id"]


def test_stores_twenty(client):
    s = client.get("/api/stores").json()
    assert len(s) == 20 and {"inbound_units", "outbound_units", "group_ids"} <= set(s[0])


def test_stores_inbound_outbound_from_groups(client):
    s = {r["store_id"]: r for r in client.get("/api/stores").json()}
    # sample: G001 KNP-03 -> PAT-01 (12), G005 WH-KOL -> PAT-01; G002 KNP-03 -> WH-KOL
    assert "G001" in s["PAT-01"]["group_ids"] and "G005" in s["PAT-01"]["group_ids"]
    assert s["KNP-03"]["outbound_units"] >= 12 and s["KNP-03"]["inbound_units"] == 0


def test_runs_history_lists_sample_when_empty(client):
    rows = client.get("/api/runs").json()
    assert rows and set(rows[0]) >= {"run_id", "generated_at", "trigger", "n_groups", "passed"}


# ---- Task 2: decisions, export, trigger ---------------------------------------------------------
import copy

import pytest


def test_decision_roundtrip(client):
    gid = client.get("/api/runs/latest").json()["groups"][0]["group_id"]
    assert client.post(f"/api/groups/{gid}/decision", json={"decision": "approve", "note": "ok"}).status_code == 200
    g = next(g for g in client.get("/api/runs/latest").json()["groups"] if g["group_id"] == gid)
    assert g["decision"] == "approve"
    assert g["decision_note"] == "ok"


def test_decision_response_shape(client):
    r = client.post("/api/groups/G002/decision", json={"decision": "reject", "by": "merch"})
    assert r.json() == {"group_id": "G002", "decision": "reject"}


def test_unknown_group_404(client):
    assert client.post("/api/groups/NOPE/decision", json={"decision": "approve"}).status_code == 404


def test_bad_decision_value_422(client):
    assert client.post("/api/groups/G001/decision", json={"decision": "maybe"}).status_code == 422


def test_batch_and_export(client):
    gids = [g["group_id"] for g in client.get("/api/runs/latest").json()["groups"][:2]]
    assert client.post("/api/groups/decision", json={"group_ids": gids, "decision": "approve"}).json()["updated"] == 2
    csv = client.get("/api/export.csv").text.splitlines()
    assert csv[0].startswith("group_id,type,from,to,sku_id,size,qty")
    assert len(csv) > 1


def test_batch_skips_unknown_ids(client):
    r = client.post("/api/groups/decision", json={"group_ids": ["G001", "NOPE"], "decision": "reject"})
    assert r.json() == {"updated": 1}


def test_export_header_only_when_nothing_approved(client):
    r = client.get("/api/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines() == ["group_id,type,from,to,sku_id,size,qty,ship_on,arrives_on,"
                                   "mrp_value_line,explanation,decision"]


def test_export_one_row_per_line_with_line_value(client):
    run = client.get("/api/runs/latest").json()
    g = next(g for g in run["groups"] if len(g["lines"]) > 1)
    client.post(f"/api/groups/{g['group_id']}/decision", json={"decision": "approve"})
    import csv as _csv
    rows = list(_csv.DictReader(client.get("/api/export.csv").text.splitlines()))
    assert len(rows) == len(g["lines"])
    assert {r["sku_id"] for r in rows} == {ln["sku_id"] for ln in g["lines"]}
    assert sum(int(r["mrp_value_line"]) for r in rows) == pytest.approx(g["mrp_value"], abs=len(rows))
    assert all(r["decision"] == "approve" for r in rows)


def test_export_status_filters(client):
    client.post("/api/groups/G001/decision", json={"decision": "approve"})
    client.post("/api/groups/G002/decision", json={"decision": "reject"})
    rej = {r.split(",")[0] for r in client.get("/api/export.csv?status=rejected").text.splitlines()[1:]}
    assert rej == {"G002"}
    n_lines = sum(len(g["lines"]) for g in client.get("/api/runs/latest").json()["groups"])
    assert len(client.get("/api/export.csv?status=all").text.splitlines()) == n_lines + 1


def test_trigger_requires_token(client):
    assert client.post("/api/runs").status_code == 401


def test_trigger_wrong_token_401(client):
    assert client.post("/api/runs", headers={"X-Run-Token": "nope"}).status_code == 401


def test_trigger_empty_token_never_matches_unset_env(client, monkeypatch):
    monkeypatch.delenv("RUN_TOKEN", raising=False)
    assert client.post("/api/runs", headers={"X-Run-Token": ""}).status_code == 401


def _fake_engine(monkeypatch, result):
    from backend.app import runs

    def fake(trigger="manual", strict=True, **kw):
        if isinstance(result, Exception):
            raise result
        return {**copy.deepcopy(result), "trigger": trigger}
    monkeypatch.setattr(runs, "run_engine", fake)


AUTH = {"X-Run-Token": "test-token"}


def test_trigger_stores_and_serves_new_run(client, monkeypatch, real_run):
    _fake_engine(monkeypatch, real_run)
    r = client.post("/api/runs?trigger=github", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"run_id": real_run["run_id"], "summary": real_run["summary"], "passed": True}
    latest = client.get("/api/runs/latest").json()
    assert latest["run_id"] == real_run["run_id"] and latest["is_sample"] is False
    assert latest["trigger"] == "github"
    assert client.get("/api/runs").json()[0]["run_id"] == real_run["run_id"]


def test_trigger_validation_failure_409_previous_run_stays_live(client, monkeypatch, real_run):
    from engine.run import ValidationFailed
    bad = copy.deepcopy(real_run)
    bad["validation"] = {"passed": False, "checked_moves": 9,
                         "violations": [{"rule": "CAPACITY", "group_id": f"G{i}", "detail": "over"} for i in range(8)]}
    _fake_engine(monkeypatch, ValidationFailed(bad))
    r = client.post("/api/runs", headers=AUTH)
    assert r.status_code == 409
    assert len(r.json()["detail"]["violations"]) == 5
    assert client.get("/api/runs/latest").json()["is_sample"] is True
    assert client.get("/api/runs").json()[0]["passed"] is False


def test_trigger_while_running_409(client):
    from backend.app import runs
    assert runs._LOCK.acquire(blocking=False)
    try:
        r = client.post("/api/runs", headers=AUTH)
    finally:
        runs._LOCK.release()
    assert r.status_code == 409 and r.json() == {"detail": "run in progress"}


def test_decision_carries_over_to_identical_move(client, monkeypatch, real_run):
    client.post("/api/groups/G001/decision", json={"decision": "approve", "note": "go"})
    client.post("/api/groups/G002/decision", json={"decision": "reject"})
    changed = copy.deepcopy(real_run)
    g2 = next(g for g in changed["groups"] if g["group_id"] == "G002")
    g2["qty"] += 1                                     # different move under the same id
    _fake_engine(monkeypatch, changed)
    assert client.post("/api/runs", headers=AUTH).status_code == 200
    dec = {g["group_id"]: g["decision"] for g in client.get("/api/runs/latest").json()["groups"]}
    assert dec["G001"] == "approve" and dec["G002"] is None


def test_cors_preflight_localhost(client):
    r = client.options("/api/runs/latest", headers={"Origin": "http://localhost:5173",
                                                    "Access-Control-Request-Method": "POST",
                                                    "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_origins_from_env(monkeypatch):
    from backend.app.main import cors_origins
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://stock-mover.vercel.app/, https://x.example")
    o = cors_origins()
    assert {"https://stock-mover.vercel.app", "https://x.example", "http://localhost:5173"} <= set(o)
    monkeypatch.setenv("FRONTEND_ORIGIN", "*")
    assert cors_origins() == ["*"]
