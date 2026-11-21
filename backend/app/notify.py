"""Notifications (contract C4): merchandiser digest, area-manager alerts (capped per ISO week),
approval requests for moves above ₹1 lakh. Email goes out over Gmail SMTP when configured.

Env: SMTP_USER, SMTP_APP_PASSWORD, DIGEST_TO (comma-separated; default SMTP_USER),
     AM_EMAIL_<AM-ID with '-' -> '_'> (e.g. AM_EMAIL_AM_02), PUBLIC_APP_URL, SMTP_HOST, SMTP_PORT.
"""
from __future__ import annotations

import html as _html
import logging
import os
import smtplib
import threading
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage

from backend.app import runs, store

log = logging.getLogger("stock_mover.notify")

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:  # noqa: BLE001 - no tz database in the image: IST has no DST, a fixed offset is exact
    IST = timezone(timedelta(hours=5, minutes=30), "IST")

TOP_N = 10
_AM_CACHE: list[dict] | None = None
_AM_LOCK = threading.Lock()


# ---- helpers ------------------------------------------------------------------------------------
def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def current_week() -> str:
    """The real calendar week in India (the cap is about how often a person is pinged)."""
    return iso_week(datetime.now(IST).date())


def app_link() -> str:
    url = os.environ.get("PUBLIC_APP_URL", "").strip()
    if not url or url == "*":
        fo = os.environ.get("FRONTEND_ORIGIN", "").split(",")[0].strip()
        url = fo if fo and fo != "*" else "http://localhost:5173/"
    return url


def am_directory() -> list[dict]:
    """Area managers from the engine's data loader (cached: the CSV load takes seconds)."""
    global _AM_CACHE
    with _AM_LOCK:
        if _AM_CACHE is None:
            from engine.data import load_data
            am = load_data().area_managers
            _AM_CACHE = [{"area_manager_id": r["area_manager_id"], "name": r["name"], "city": r["city"],
                          "stores": list(r["stores"]), "max_alerts_per_week": int(r["max_alerts_per_week"])}
                         for r in am.to_dict("records")]
        return _AM_CACHE


def _fmt_date(iso: str) -> str:
    d = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
    return f"{d.day} {d:%b %Y}"


def _inr(v) -> str:
    v = float(v or 0)
    if v >= 1e7:
        return f"₹{v / 1e7:.2f} crore"
    if v >= 1e5:
        return f"₹{v / 1e5:.1f} lakh"
    return f"₹{v:,.0f}"


def move_line(g: dict) -> str:
    sizes = "/".join(str(s) for s in (g.get("sizes") or {}))
    return f"{g['from']} → {g['to']} · {g['qty']} × {g['style_id']}" + (f" ({sizes})" if sizes else "")


def _by_priority(groups: list[dict]) -> list[dict]:
    return sorted(groups, key=lambda g: -(g.get("priority") or 0))


# ---- C4 builder ---------------------------------------------------------------------------------
def build_notifications(run: dict, data_am: list[dict], sent_counts: dict, *, week: str | None = None,
                        link: str | None = None) -> dict:
    link = link or app_link()
    week = week or current_week()
    groups = _by_priority(run.get("groups", []))
    s = run.get("summary", {})
    n_groups = s.get("n_groups", len(groups))
    n_sign = s.get("needs_approval", sum(1 for g in groups if g.get("needs_approval")))
    n_breaks = len(run.get("validation", {}).get("violations", []))
    checked = run.get("validation", {}).get("checked_moves", 0)
    top = groups[:TOP_N]

    subject = f"Stock Mover · {_fmt_date(run['as_of'])} · {n_groups} moves to approve ({n_sign} need sign-off)"
    head = (f"{n_groups} moves, {s.get('units', sum(g['qty'] for g in groups))} units, "
            f"{_inr(s.get('mrp_value', 0))} at MRP; {_inr(s.get('revenue_protected', 0))} revenue protected.")
    rule = f"{n_breaks} rule breaks (validator checked {checked} moves)."
    text = "\n".join([head, "", f"Top {len(top)} by priority:",
                      *[f"{i}. {g['explanation']}" for i, g in enumerate(top, 1)],
                      "", rule, f"Approve: {link}"])
    e = _html.escape
    items_html = "".join("<li>" + e(g["explanation"]) + "</li>" for g in top)
    html = (f"<h2>{n_groups} moves to approve ({n_sign} need sign-off)</h2><p>{e(head)}</p>"
            f"<ol>{items_html}</ol>"
            f"<p><b>{e(rule)}</b></p><p><a href=\"{e(link)}\">Open Stock Mover to approve</a></p>")

    am_alerts = []
    for am in data_am:
        mine = [g for g in groups if (g["from"] in am["stores"] or g["to"] in am["stores"])
                and g.get("decision") != "reject"]
        if not mine:
            continue
        cap = int(am.get("max_alerts_per_week", 5))
        sent = int(sent_counts.get(am["area_manager_id"], 0))
        items = [{"group_id": g["group_id"], "text": move_line(g)} for g in mine[:max(cap - sent, 0)]]
        if items:
            more = len(mine) - len(items)
            body = (f"{am['name']}, {len(items)} stock move{'s' if len(items) > 1 else ''} for your "
                    f"{am['city']} stores: " + "; ".join(f"{i}) {it['text']}" for i, it in enumerate(items, 1))
                    + (f" (+{more} more in the app)" if more > 0 else "") + f". Details: {link}")
        else:
            body = (f"{am['name']}, weekly alert limit reached ({sent}/{cap}); {len(mine)} moves for your "
                    f"stores are waiting in Stock Mover: {link}")
        am_alerts.append({"am_id": am["area_manager_id"], "am_name": am["name"], "city": am["city"],
                          "stores": list(am["stores"]), "week": week, "sent_this_week": sent,
                          "items": items, "text": body})

    approval_requests = [{"group_id": g["group_id"], "mrp_value": g["mrp_value"],
                          "text": f"Approve {move_line(g)} worth {_inr(g['mrp_value'])} at MRP?"}
                         for g in groups if g.get("needs_approval") and g.get("decision") is None]

    return {"digest": {"subject": subject, "text": text, "html": html, "link": link},
            "am_alerts": am_alerts, "approval_requests": approval_requests}


def today(run: dict | None = None) -> dict:
    run = runs.with_decisions(run or runs.current_run())
    am = am_directory()
    week = current_week()
    counts = {a["area_manager_id"]: store.alerts_sent_count(a["area_manager_id"], week) for a in am}
    return build_notifications(run, am, counts, week=week)


def record_am_items(am_id: str, n: dict | None = None) -> int:
    """Mark this AM's current items as sent this week (used when Fo reports a delivered alert)."""
    n = n or today()
    alert = next((a for a in n["am_alerts"] if a["am_id"] == am_id), None)
    if not alert:
        return 0
    for it in alert["items"]:
        store.record_alert(am_id, alert["week"], it["group_id"])
    return len(alert["items"])


# ---- sending ------------------------------------------------------------------------------------
def _smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_USER") and os.environ.get("SMTP_APP_PASSWORD"))


def _send_email(to: list[str], subject: str, text: str, html: str | None = None) -> None:
    user = os.environ["SMTP_USER"]
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = f"Stock Mover <{user}>", ", ".join(to), subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, timeout=20) as s:
        s.login(user, os.environ["SMTP_APP_PASSWORD"])
        s.send_message(msg)


def _deliver(to: list[str], subject: str, text: str, html: str | None = None) -> dict:
    entry = {"channel": "email", "to": ", ".join(to), "subject": subject, "ok": True, "reason": None}
    try:
        _send_email(to, subject, text, html)
    except Exception as e:  # noqa: BLE001 - a mail failure is logged, never fatal to a run
        entry.update(ok=False, reason=f"{type(e).__name__}: {e}"[:300])
        log.warning("email to %s failed: %s", entry["to"], entry["reason"])
    store.log_notification(**entry)
    return entry


def send_all(run: dict) -> list[dict]:
    """Email the digest and each AM's capped alert; record alerts + the notification log."""
    run = runs.with_decisions(run)
    week = current_week()
    if not _smtp_configured():
        subject = f"Stock Mover · {_fmt_date(run['as_of'])} · digest"
        entry = {"channel": "email", "to": os.environ.get("DIGEST_TO", ""), "subject": subject,
                 "ok": False, "reason": "smtp not configured"}
        store.log_notification(**entry)
        return [entry]
    am = am_directory()
    counts = {a["area_manager_id"]: store.alerts_sent_count(a["area_manager_id"], week) for a in am}
    n = build_notifications(run, am, counts, week=week)

    digest_to = [a.strip() for a in os.environ.get("DIGEST_TO", "").split(",") if a.strip()] \
        or [os.environ["SMTP_USER"]]
    out = [_deliver(digest_to, n["digest"]["subject"], n["digest"]["text"], n["digest"]["html"])]
    for a in n["am_alerts"]:
        addr = os.environ.get(f"AM_EMAIL_{a['am_id'].replace('-', '_')}", "").strip()
        if not addr or not a["items"]:
            continue
        subject = f"Stock Mover · {len(a['items'])} moves for your {a['city']} stores · {a['week']}"
        entry = _deliver([addr], subject, a["text"])
        if entry["ok"]:
            for it in a["items"]:
                store.record_alert(a["am_id"], a["week"], it["group_id"])
        out.append(entry)
    return out
