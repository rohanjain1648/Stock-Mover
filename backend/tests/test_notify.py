import copy
import json
from datetime import date

import pytest

from backend.tests.conftest import ROOT

AMS = [
    {"area_manager_id": "AM-02", "name": "Alok Tiwari", "city": "Kanpur",
     "stores": ["KNP-01", "KNP-02", "KNP-03"], "max_alerts_per_week": 5},
    {"area_manager_id": "AM-09", "name": "Nobody", "city": "Nowhere", "stores": ["ZZZ-01"],
     "max_alerts_per_week": 5},
]


@pytest.fixture()
def sample():
    run = json.loads((ROOT / "contracts" / "sample_run.json").read_text(encoding="utf-8"))
    for g in run["groups"]:
        g.setdefault("decision", None)
    return run


# ---- plan tests ---------------------------------------------------------------------------------
def test_am_alerts_capped(client):
    n = client.get("/api/notifications/today").json()
    assert set(n) == {"digest", "am_alerts", "approval_requests"}
    for a in n["am_alerts"]:
        assert len(a["items"]) <= 5 - a["sent_this_week"]
    assert n["digest"]["subject"].startswith("Stock Mover · 31 Oct 2026")


def test_log_post(client):
    assert client.post("/api/notifications/log", json={"channel": "fo", "to": "AM-02", "subject": "x", "ok": True}).json() == {"ok": True}
    assert client.get("/api/notifications/log").json()[0]["channel"] == "fo"


# ---- builder ------------------------------------------------------------------------------------
def test_iso_week():
    from backend.app.notify import iso_week
    assert iso_week(date(2026, 10, 31)) == "2026-W44"
    assert iso_week(date(2027, 1, 1)) == "2026-W53"


def test_digest_subject_text_link(sample):
    from backend.app.notify import build_notifications
    d = build_notifications(sample, AMS, {})["digest"]
    assert d["subject"] == "Stock Mover · 31 Oct 2026 · 8 moves to approve (3 need sign-off)"
    assert "0 rule breaks" in d["text"] and "https://stock-mover.vercel.app/" in d["text"]
    for g in sample["groups"]:                     # 8 groups < 10 -> every explanation listed
        assert g["explanation"] in d["text"]
    assert d["link"] == "https://stock-mover.vercel.app/"
    assert "<ol>" in d["html"]


def test_digest_lists_only_top_ten_by_priority(sample):
    from backend.app.notify import build_notifications
    run = copy.deepcopy(sample)
    base = run["groups"][0]
    run["groups"] = [{**base, "group_id": f"G{i:03d}", "priority": i, "explanation": f"move number {i}."}
                     for i in range(1, 16)]
    text = build_notifications(run, AMS, {})["digest"]["text"]
    assert "move number 15." in text and "move number 6." in text and "move number 5." not in text


def test_am_items_are_their_stores_highest_priority_first(sample):
    from backend.app.notify import build_notifications
    alerts = build_notifications(sample, AMS, {})["am_alerts"]
    assert [a["am_id"] for a in alerts] == ["AM-02"]        # AM-09 has no moves -> no alert
    a = alerts[0]
    mine = [g for g in sample["groups"] if {g["from"], g["to"]} & set(AMS[0]["stores"])]
    want = [g["group_id"] for g in sorted(mine, key=lambda g: -g["priority"])][:5]
    assert [i["group_id"] for i in a["items"]] == want
    assert a["items"][0]["text"].startswith("KNP-03 → WH-KOL · 250 × SHW-02 (L)")
    assert a["stores"] == AMS[0]["stores"] and a["am_name"] == "Alok Tiwari" and a["week"].startswith("20")


def test_am_cap_counts_already_sent(sample):
    from backend.app.notify import build_notifications
    a = build_notifications(sample, AMS, {"AM-02": 4})["am_alerts"][0]
    assert a["sent_this_week"] == 4 and len(a["items"]) == 1
    full = build_notifications(sample, AMS, {"AM-02": 5})["am_alerts"][0]
    assert full["items"] == [] and "limit" in full["text"]


def test_rejected_groups_not_alerted_and_decided_not_requested(sample):
    from backend.app.notify import build_notifications
    run = copy.deepcopy(sample)
    for g in run["groups"]:
        if g["group_id"] == "G002":
            g["decision"] = "reject"
        if g["group_id"] == "G001":
            g["decision"] = "approve"
    n = build_notifications(run, AMS, {})
    assert "G002" not in [i["group_id"] for i in n["am_alerts"][0]["items"]]
    assert {r["group_id"] for r in n["approval_requests"]} == \
        {g["group_id"] for g in run["groups"] if g["needs_approval"]} - {"G001", "G002"}


def test_approval_requests_for_big_moves(sample):
    from backend.app.notify import build_notifications
    req = build_notifications(sample, AMS, {})["approval_requests"]
    assert {r["group_id"] for r in req} == {g["group_id"] for g in sample["groups"] if g["needs_approval"]}
    assert all(r["mrp_value"] > 100000 and r["text"].startswith("Approve ") for r in req)


# ---- sending ------------------------------------------------------------------------------------
def test_send_all_without_smtp_logs_reason(db, sample, monkeypatch):
    from backend.app import notify
    monkeypatch.setattr(notify, "am_directory", lambda: AMS)
    out = notify.send_all(sample)
    assert out and out[0]["ok"] is False and out[0]["reason"] == "smtp not configured"
    assert db.notification_log()[0]["reason"] == "smtp not configured"


def test_send_all_emails_digest_and_am_and_records_alerts(db, sample, monkeypatch):
    from backend.app import notify
    sent = []
    monkeypatch.setattr(notify, "am_directory", lambda: AMS)
    monkeypatch.setattr(notify, "_send_email", lambda to, subject, text, html=None: sent.append((to, subject)))
    monkeypatch.setenv("SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-pass")
    monkeypatch.setenv("DIGEST_TO", "merch@example.com, boss@example.com")
    monkeypatch.setenv("AM_EMAIL_AM_02", "alok@example.com")
    out = notify.send_all(sample)
    assert sent[0] == (["merch@example.com", "boss@example.com"], out[0]["subject"])
    assert sent[1][0] == ["alok@example.com"]
    assert all(o["ok"] for o in out) and len(out) == 2
    kanpur = [g for g in sample["groups"] if {g["from"], g["to"]} & set(AMS[0]["stores"])]
    assert db.alerts_sent_count("AM-02", notify.current_week()) == min(5, len(kanpur))


def test_send_failure_is_logged_not_raised_and_not_counted(db, sample, monkeypatch):
    from backend.app import notify

    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(notify, "am_directory", lambda: AMS)
    monkeypatch.setattr(notify, "_send_email", boom)
    monkeypatch.setenv("SMTP_USER", "me@gmail.com")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-pass")
    monkeypatch.setenv("AM_EMAIL_AM_02", "alok@example.com")
    out = notify.send_all(sample)
    assert [o["ok"] for o in out] == [False, False] and "connection refused" in out[0]["reason"]
    assert out[0]["to"] == "me@gmail.com"        # no DIGEST_TO -> digest goes to the sender
    assert db.alerts_sent_count("AM-02", notify.current_week()) == 0


def test_fo_log_for_am_counts_toward_cap(client):
    before = next(a for a in client.get("/api/notifications/today").json()["am_alerts"] if a["am_id"] == "AM-02")
    client.post("/api/notifications/log", json={"channel": "fo", "to": "AM-02", "subject": "call", "ok": True})
    after = next(a for a in client.get("/api/notifications/today").json()["am_alerts"] if a["am_id"] == "AM-02")
    assert after["sent_this_week"] == before["sent_this_week"] + len(before["items"])


def test_trigger_sends_notifications_in_background(client, monkeypatch, real_run):
    from backend.app import main, notify, runs
    called = []
    monkeypatch.setattr(runs, "run_engine", lambda trigger="manual", strict=True, **k: copy.deepcopy(real_run))
    monkeypatch.setattr(notify, "send_all", lambda run: called.append(run["run_id"]) or [])
    assert client.post("/api/runs", headers={"X-Run-Token": "test-token"}).status_code == 200
    main.app.state.last_notify.join(5)
    assert called == [real_run["run_id"]]


# ---- scheduler ----------------------------------------------------------------------------------
def test_scheduler_registers_daily_0700_ist():
    from types import SimpleNamespace
    from backend.app import scheduler
    app = SimpleNamespace(state=SimpleNamespace())
    scheduler.start(app)
    try:
        job = app.state.scheduler.get_job("daily-run")
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["hour"] == "7" and fields["minute"] == "0"
        assert "Kolkata" in str(job.trigger.timezone) or "05:30" in str(job.trigger.timezone)
    finally:
        scheduler.stop(app)


def test_daily_job_runs_then_notifies(monkeypatch, real_run):
    from backend.app import notify, runs, scheduler
    calls = []
    monkeypatch.setattr(runs, "trigger_run", lambda trigger: calls.append(("run", trigger)) or real_run)
    monkeypatch.setattr(notify, "send_all", lambda run: calls.append(("send", run["run_id"])))
    scheduler.daily_job()
    assert calls == [("run", "schedule"), ("send", real_run["run_id"])]


def test_daily_job_swallows_validation_failure(monkeypatch, real_run):
    from backend.app import notify, runs, scheduler

    def blocked(trigger):
        raise runs.ValidationFailed({**real_run, "validation": {"passed": False, "checked_moves": 1,
                                                                "violations": [{"rule": "X"}]}})
    monkeypatch.setattr(runs, "trigger_run", blocked)
    monkeypatch.setattr(notify, "send_all", lambda run: pytest.fail("must not notify a blocked run"))
    scheduler.daily_job()       # no exception
