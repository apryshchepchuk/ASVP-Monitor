from __future__ import annotations

import sys
from datetime import datetime, timezone

from common import CONFIG_DIR, load_json, save_json


WATCHLIST_PATH = CONFIG_DIR / "watchlist.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    if len(sys.argv) != 3:
        raise RuntimeError(
            "Usage: manage_subject.py <subject_id> <enable|disable>"
        )

    subject_id = sys.argv[1].strip()
    action = sys.argv[2].strip().lower()

    if action not in {"enable", "disable"}:
        raise RuntimeError("Action must be: enable or disable")

    enabled = action == "enable"

    data = load_json(WATCHLIST_PATH)

    subjects = data.get("subjects", [])

    found = False

    for subject in subjects:
        if subject.get("id") != subject_id:
            continue

        subject["enabled"] = enabled
        subject["updated_at"] = now_iso()

        found = True

        print(
            f"Updated subject {subject_id}: "
            f"enabled={enabled}"
        )

        break

    if not found:
        raise RuntimeError(f"Subject not found: {subject_id}")

    save_json(WATCHLIST_PATH, data)

    print("watchlist.json updated")


if __name__ == "__main__":
    main()
