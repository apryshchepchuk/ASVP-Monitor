from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import requests

ZIP_URL = (
    "https://data.gov.ua/dataset/"
    "22aef563-3e87-4ed9-92e8-d764dc02f426/"
    "resource/d1a38c08-0f3a-4687-866f-f28f50df7c46/"
    "download/30-ex_csv_asvp.zip"
)

OUTPUT_PATH = Path("samples/asvp_sample.json")

MAX_ROWS = 100


def download_zip() -> bytes:
    print("Downloading ZIP...")

    response = requests.get(ZIP_URL, timeout=600)
    response.raise_for_status()

    print(f"Downloaded: {len(response.content) / 1024 / 1024:.2f} MB")

    return response.content


def inspect_zip(zip_bytes: bytes) -> dict:
    result = {
        "files": []
    }

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()

        print(f"Files inside ZIP: {len(names)}")

        for name in names:
            print(f"Inspecting: {name}")

            if not name.lower().endswith(".csv"):
                continue

            file_info = {
                "file_name": name,
                "headers": [],
                "sample_rows": []
            }

            with zf.open(name) as raw_file:
                text_stream = io.TextIOWrapper(
                    raw_file,
                    encoding="utf-8",
                    newline=""
                )

                reader = csv.DictReader(text_stream)

                file_info["headers"] = reader.fieldnames or []

                for index, row in enumerate(reader):
                    if index >= MAX_ROWS:
                        break

                    file_info["sample_rows"].append(row)

            result["files"].append(file_info)

    return result


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    zip_bytes = download_zip()

    result = inspect_zip(zip_bytes)

    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved sample to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
