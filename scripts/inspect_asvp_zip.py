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


class SemicolonDialect(csv.Dialect):
    delimiter = ";"
    quotechar = '"'
    escapechar = None
    doublequote = True
    skipinitialspace = False
    lineterminator = "\n"
    quoting = csv.QUOTE_MINIMAL


def download_zip() -> bytes:
    print("Downloading ZIP...")

    response = requests.get(ZIP_URL, timeout=600)
    response.raise_for_status()

    size_mb = len(response.content) / 1024 / 1024
    print(f"Downloaded: {size_mb:.2f} MB")

    return response.content


def detect_dialect(text_stream: io.TextIOWrapper) -> csv.Dialect:
    sample = text_stream.read(32_768)
    text_stream.seek(0)

    if not sample.strip():
        print("Empty CSV sample. Falling back to semicolon delimiter.")
        return SemicolonDialect

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=";,|\t,"
        )
        print(f"Detected delimiter: {repr(dialect.delimiter)}")
        return dialect
    except csv.Error:
        print("Could not detect CSV delimiter. Falling back to semicolon delimiter.")
        return SemicolonDialect


def inspect_zip(zip_bytes: bytes) -> dict:
    result = {
        "zip_files_total": 0,
        "csv_files_total": 0,
        "files": [],
    }

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        result["zip_files_total"] = len(names)

        print(f"Files inside ZIP: {len(names)}")

        for name in names:
            print(f"Found in ZIP: {name}")

            if not name.lower().endswith(".csv"):
                continue

            print(f"Inspecting CSV: {name}")
            result["csv_files_total"] += 1

            file_info = {
                "file_name": name,
                "headers": [],
                "delimiter": None,
                "sample_rows": [],
                "sample_rows_count": 0,
                "encoding": "cp1251",
                "decode_errors": "replace",
            }

            with zf.open(name) as raw_file:
                text_stream = io.TextIOWrapper(
                    raw_file,
                    encoding="cp1251",
                    newline="",
                    errors="replace",
                )

                dialect = detect_dialect(text_stream)
                file_info["delimiter"] = dialect.delimiter

                reader = csv.DictReader(
                    text_stream,
                    dialect=dialect,
                )

                file_info["headers"] = reader.fieldnames or []

                for index, row in enumerate(reader):
                    if index >= MAX_ROWS:
                        break

                    file_info["sample_rows"].append(row)

                file_info["sample_rows_count"] = len(file_info["sample_rows"])

            result["files"].append(file_info)

    return result


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    zip_bytes = download_zip()
    result = inspect_zip(zip_bytes)

    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved sample to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
