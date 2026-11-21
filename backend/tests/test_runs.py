import copy


def test_store_latest_run_none_when_empty(db):
    assert db.latest_run() is None


def test_failed_run_is_recorded_but_never_served(db, real_run):
    from backend.app import runs
    bad = copy.deepcopy(real_run)
    bad["run_id"] = "20261121T020000Z"
    bad["validation"] = {"passed": False, "checked_moves": 3, "violations": [{"rule": "CAPACITY", "group_id": "G001", "detail": "x"}]}
    db.save_run(real_run)
    db.save_run(bad)
    assert runs.current_run()["run_id"] == real_run["run_id"]
    hist = db.list_runs()
    assert [h["run_id"] for h in hist] == [bad["run_id"], real_run["run_id"]]
    assert hist[0]["passed"] is False


def test_current_run_prefers_stored_passing_run(db, real_run):
    from backend.app import runs
    db.save_run(real_run)
    cur = runs.current_run()
    assert cur["run_id"] == real_run["run_id"] and cur["is_sample"] is False


def test_decisions_roundtrip_in_store(db):
    db.set_decision("R1", "G001", "approve", "ok", "merch")
    db.set_decision("R1", "G001", "reject", "changed mind", "merch")
    d = db.decisions("R1")
    assert d["G001"]["decision"] == "reject" and d["G001"]["note"] == "changed mind"
    assert db.decisions("R2") == {}


def test_alert_counts_per_week(db):
    db.record_alert("AM-02", "2026-W47", "G001")
    db.record_alert("AM-02", "2026-W47", "G002")
    db.record_alert("AM-02", "2026-W47", "G002")   # same item twice counts once
    db.record_alert("AM-02", "2026-W46", "G009")
    assert db.alerts_sent_count("AM-02", "2026-W47") == 2
    assert db.alerts_sent_count("AM-01", "2026-W47") == 0


def test_notification_log_newest_first(db):
    db.log_notification("email", "a@x", "first", True)
    db.log_notification("fo", "AM-02", "second", False, reason="busy")
    log = db.notification_log()
    assert [l["subject"] for l in log] == ["second", "first"]
    assert log[0]["ok"] is False and log[0]["reason"] == "busy"
