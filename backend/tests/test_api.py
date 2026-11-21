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
