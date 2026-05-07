from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from common import DATA_DIR, load_json, save_json


CURRENT_PATH = DATA_DIR / "current.json"
CHANGES_PATH = DATA_DIR / "changes.json"
EVENTS_PATH = DATA_DIR / "history" / "events.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def event_id(parts: list[object]) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_events() -> dict[str, Any]:
    if not EVENTS_PATH.exists():
        return {
            "schema_version": 1,
            "events": [],
        }

    data = load_json(EVENTS_PATH)

    if isinstance(data, list):
        return {
            "schema_version": 1,
            "events": data,
        }

    data.setdefault("events", [])
    return data


def make_new_case_event(record: dict[str, Any], detected_at: str) -> dict[str, Any]:
    eid = event_id([
        "new_case",
        record.get("match_key"),
        record.get("vp_state"),
    ])

    return {
        "event_id": eid,
        "event_type": "new_case",
        "detected_at": detected_at,
        "match_key": record.get("match_key"),
        "vp_ordernum": record.get("vp_ordernum"),
        "subject_id": record.get("subject_id"),
        "subject_name": record.get("subject_name"),
        "subject_code": record.get("subject_code"),
        "role": record.get("role"),
        "state": record.get("vp_state"),
        "record": record,
    }


def make_state_changed_event(item: dict[str, Any], detected_at: str) -> dict[str, Any]:
    previous = item.get("previous", {})
    current = item.get("current", {})

    old_state = previous.get("vp_state")
    new_state = current.get("vp_state")

    eid = event_id([
        "state_changed",
        current.get("match_key"),
        old_state,
        new_state,
    ])

    return {
        "event_id": eid,
        "event_type": "state_changed",
        "detected_at": detected_at,
        "match_key": current.get("match_key"),
        "vp_ordernum": current.get("vp_ordernum"),
        "subject_id": current.get("subject_id"),
        "subject_name": current.get("subject_name"),
        "subject_code": current.get("subject_code"),
        "role": current.get("role"),
        "old_state": old_state,
        "new_state": new_state,
        "record": current,
    }


def make_details_changed_event(item: dict[str, Any], detected_at: str) -> dict[str, Any]:
    current = item.get("current", {})
    changes = item.get("changes", {})

    change_fingerprint = "|".join(
        f"{field}:{value.get('old')}->{value.get('new')}"
        for field, value in sorted(changes.items())
    )

    eid = event_id([
        "details_changed",
        current.get("match_key"),
        change_fingerprint,
    ])

    return {
        "event_id": eid,
        "event_type": "details_changed",
        "detected_at": detected_at,
        "match_key": current.get("match_key"),
        "vp_ordernum": current.get("vp_ordernum"),
        "subject_id": current.get("subject_id"),
        "subject_name": current.get("subject_name"),
        "subject_code": current.get("subject_code"),
        "role": current.get("role"),
        "changes": changes,
        "record": current,
    }


def main() -> None:
    if not CURRENT_PATH.exists():
        raise RuntimeError("current.json does not exist")

    if not CHANGES_PATH.exists():
        raise RuntimeError("changes.json does not exist")

    current = load_json(CURRENT_PATH)
    changes = load_json(CHANGES_PATH)
    store = load_events()

    existing_ids = {
        event.get("event_id")
        for event in store.get("events", [])
        if event.get("event_id")
    }

    detected_at = current.get("generated_at") or changes.get("generated_at") or now_iso()
    is_initial_snapshot = bool(changes.get("is_initial_snapshot"))

    new_events: list[dict[str, Any]] = []

    if not is_initial_snapshot:
        for record in changes.get("added", []):
            new_events.append(make_new_case_event(record, detected_at))
    else:
        print("Initial snapshot detected: skipping new_case events for baseline.")

    for item in changes.get("state_changed", []):
        new_events.append(make_state_changed_event(item, detected_at))

    for item in changes.get("details_changed", []):
        new_events.append(make_details_changed_event(item, detected_at))

    appended = 0

    for event in new_events:
        if event["event_id"] in existing_ids:
            continue

        store["events"].append(event)
        existing_ids.add(event["event_id"])
        appended += 1

    store["schema_version"] = 1
    store["updated_at"] = now_iso()
    store["events_total"] = len(store["events"])

    save_json(EVENTS_PATH, store)

    print(f"Events appended: {appended}")
    print(f"Events total: {len(store['events'])}")


if __name__ == "__main__":
    main()
