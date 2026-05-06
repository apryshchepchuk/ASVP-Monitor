from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]

CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "docs" / "data"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_text(value: object) -> str:
    text = str(value or "").upper()
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_code(value: object) -> str:
    return re.sub(r"\D+", "", str(value or ""))
