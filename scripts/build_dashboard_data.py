from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from common import DATA_DIR, load_json, save_json


CURRENT_PATH = DATA_DIR / "current.json"
EVENTS_PATH = DATA_DIR / "history" / "events.json"
DASHBOARD_PATH = DATA_DIR / "dashboard.json"

WINDOW_DAYS = 14


ACTIVE_STATES = {
    "Відкрито",
    "Примусове виконання",
}

STOPPED_STATES = {
    "Зупинено",
}

COMPLETED_STATES = {
    "Завершено",
}

REFUSED_STATES = {
    "Вімовлено у відкритті",
    "Відмовлено у відкритті",
}


def parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def state_category(state: str) -> str:
    if state in ACTIVE_STATES:
        return "active"

    if state in STOPPED_STATES:
        return "stopped"

    if state in COMPLETED_STATES:
        return "completed"

    if state in REFUSED_STATES:
        return "refused"

    return "other"


def load_events() -> list[dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return []

    data = load_json(EVENTS_PATH)

    if isinstance(data, list):
        return data

    return data.get("events", [])


def build_events_by_match_key(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}

    for event in events:
        match_key = event.get("match_key")
        if not match_key:
            continue

        result.setdefault(match_key, []).append(event)

    for items in result.values():
        items.sort(key=lambda event: str(event.get("detected_at") or ""))

    return result


def is_recent(event: dict[str, Any], threshold: datetime) -> bool:
    detected_at = parse_dt(event.get("detected_at"))
    if not detected_at:
        return False

    return detected_at >= threshold


def build_record(
    record: dict[str, Any],
    events: list[dict[str, Any]],
    threshold: datetime,
) -> dict[str, Any]:
    recent_events = [
        event
        for event in events
        if is_recent(event, threshold)
    ]

    first_seen = None
    last_changed = None

    for event in events:
        event_dt = parse_dt(event.get("detected_at"))
        if not event_dt:
            continue

        if first_seen is None or event_dt < first_seen:
            first_seen = event_dt

        if event.get("event_type") in {"state_changed", "details_changed"}:
            if last_changed is None or event_dt > last_changed:
                last_changed = event_dt

    is_new_14d = any(
        event.get("event_type") == "new_case"
        for event in recent_events
    )

    is_changed_14d = any(
        event.get("event_type") in {"state_changed", "details_changed"}
        for event in recent_events
    )

    state = record.get("vp_state") or ""

    return {
        "match_key": record.get("match_key"),
        "vp_ordernum": record.get("vp_ordernum"),

        "subject": {
            "id": record.get("subject_id"),
            "type": record.get("subject_type"),
            "name": record.get("subject_name"),
            "code": record.get("subject_code"),
            "role": record.get("role"),
        },

        "state": {
            "current": state,
            "category": state_category(state),
        },

        "dates": {
            "vp_begin": record.get("vp_begindate"),
            "first_seen": first_seen.isoformat() if first_seen else None,
            "last_changed": last_changed.isoformat() if last_changed else None,
            "last_seen": record.get("last_seen"),
        },

        "flags": {
            "is_new_14d": is_new_14d,
            "is_changed_14d": is_changed_14d,
        },

        "parties": {
            "debtor_name": record.get("debtor_name"),
            "debtor_birthdate": record.get("debtor_birthdate"),
            "debtor_code": record.get("debtor_code"),
            "creditor_name": record.get("creditor_name"),
            "creditor_code": record.get("creditor_code"),
        },

        "dvs": {
            "org_name": record.get("org_name"),
            "dvs_code": record.get("dvs_code"),
        },

        "events": events,
        "recent_events": recent_events,
    }


def build_kpi(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(records),
        "debtors": sum(1 for r in records if r["subject"]["role"] == "debtor"),
        "creditors": sum(1 for r in records if r["subject"]["role"] == "creditor"),
        "active": sum(1 for r in records if r["state"]["category"] == "active"),
        "completed": sum(1 for r in records if r["state"]["category"] == "completed"),
        "stopped": sum(1 for r in records if r["state"]["category"] == "stopped"),
        "refused": sum(1 for r in records if r["state"]["category"] == "refused"),
        "other": sum(1 for r in records if r["state"]["category"] == "other"),
        "new_14d": sum(1 for r in records if r["flags"]["is_new_14d"]),
        "changed_14d": sum(1 for r in records if r["flags"]["is_changed_14d"]),
    }


def main() -> None:
    if not CURRENT_PATH.exists():
        raise RuntimeError("current.json does not exist")

    current = load_json(CURRENT_PATH)
    events = load_events()

    generated_at = current.get("generated_at") or datetime.now(timezone.utc).isoformat()
    generated_dt = parse_dt(generated_at) or datetime.now(timezone.utc)
    threshold = generated_dt - timedelta(days=WINDOW_DAYS)

    events_by_match_key = build_events_by_match_key(events)

    records = [
        build_record(
            record=record,
            events=events_by_match_key.get(record.get("match_key"), []),
            threshold=threshold,
        )
        for record in current.get("records", [])
    ]

def parse_vp_begin_for_sort(value: object) -> datetime:
    text = str(value or "").strip()

    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)

    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return datetime.min.replace(tzinfo=timezone.utc)


records.sort(
    key=lambda item: (
        parse_vp_begin_for_sort(item["dates"]["vp_begin"]),
        item["vp_ordernum"] or "",
    ),
    reverse=True,
)

    dashboard = {
        "schema_version": 1,
        "generated_at": generated_at,
        "window_days": WINDOW_DAYS,
        "source": {
            "rows_scanned": current.get("rows_scanned"),
            "matched_records_total": current.get("matched_records_total"),
            "reader": current.get("reader"),
            "is_partial": current.get("is_partial"),
            "csv_file_name": current.get("csv_file_name"),
        },
        "kpi": build_kpi(records),
        "records": records,
    }

    save_json(DASHBOARD_PATH, dashboard)

    print(f"Dashboard records: {len(records)}")
    print(f"Saved dashboard data: {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
