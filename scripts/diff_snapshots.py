from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import DATA_DIR, load_json, save_json


CURRENT_PATH = DATA_DIR / "current.json"
PREVIOUS_PATH = DATA_DIR / "previous.json"
CHANGES_PATH = DATA_DIR / "changes.json"


COMPARE_FIELDS = [
    "vp_state",
    "vp_begindate",
    "debtor_name",
    "debtor_birthdate",
    "debtor_code",
    "creditor_name",
    "creditor_code",
    "org_name",
    "dvs_code",
]


def index_records(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        record["match_key"]: record
        for record in snapshot.get("records", [])
    }


def build_field_changes(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}

    for field in COMPARE_FIELDS:
        old_value = previous.get(field)
        new_value = current.get(field)

        if old_value != new_value:
            changes[field] = {
                "old": old_value,
                "new": new_value,
            }

    return changes


def main() -> None:
    if not CURRENT_PATH.exists():
        raise RuntimeError("current.json does not exist")

    current = load_json(CURRENT_PATH)

    if not PREVIOUS_PATH.exists():
        print("previous.json does not exist yet")

        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_initial_snapshot": True,
            "added": current.get("records", []),
            "state_changed": [],
            "details_changed": [],
            "removed": [],
        }

        save_json(CHANGES_PATH, result)
        return

    previous = load_json(PREVIOUS_PATH)

    current_records = index_records(current)
    previous_records = index_records(previous)

    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    state_changed: list[dict[str, Any]] = []
    details_changed: list[dict[str, Any]] = []

    current_keys = set(current_records.keys())
    previous_keys = set(previous_records.keys())

    added_keys = current_keys - previous_keys
    removed_keys = previous_keys - current_keys
    common_keys = current_keys & previous_keys

    for key in sorted(added_keys):
        added.append(current_records[key])

    allow_removed = (
        not current.get("is_partial")
        and not previous.get("is_partial")
    )

    if allow_removed:
        for key in sorted(removed_keys):
            removed.append(previous_records[key])

    for key in sorted(common_keys):
        old_record = previous_records[key]
        new_record = current_records[key]

        if old_record.get("vp_state") != new_record.get("vp_state"):
            state_changed.append({
                "match_key": key,
                "previous": old_record,
                "current": new_record,
            })

        field_changes = build_field_changes(
            previous=old_record,
            current=new_record,
        )

        non_state_changes = {
            field: value
            for field, value in field_changes.items()
            if field != "vp_state"
        }

        if non_state_changes:
            details_changed.append({
                "match_key": key,
                "changes": non_state_changes,
                "previous": old_record,
                "current": new_record,
            })

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_partial": current.get("is_partial"),
        "previous_partial": previous.get("is_partial"),
        "added_total": len(added),
        "removed_total": len(removed),
        "state_changed_total": len(state_changed),
        "details_changed_total": len(details_changed),
        "added": added,
        "removed": removed,
        "state_changed": state_changed,
        "details_changed": details_changed,
    }

    save_json(CHANGES_PATH, result)

    print(f"Added: {len(added)}")
    print(f"Removed: {len(removed)}")
    print(f"State changed: {len(state_changed)}")
    print(f"Details changed: {len(details_changed)}")


if __name__ == "__main__":
    main()
