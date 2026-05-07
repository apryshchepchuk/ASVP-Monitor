from __future__ import annotations

import csv
import io
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from common import (
    CONFIG_DIR,
    DATA_DIR,
    load_json,
    normalize_code,
    normalize_text,
    save_json,
)

ZIP_URL = (
    "https://data.gov.ua/dataset/"
    "22aef563-3e87-4ed9-92e8-d764dc02f426/"
    "resource/d1a38c08-0f3a-4687-866f-f28f50df7c46/"
    "download/30-ex_csv_asvp.zip"
)

WATCHLIST_PATH = CONFIG_DIR / "watchlist.json"
OUTPUT_PATH = DATA_DIR / "current.json"

ENCODING = "cp1251"
CHUNK_SIZE = 1024 * 1024 * 8
SNIFF_BYTES = 64 * 1024

REQUIRED_COLUMNS = [
    "DEBTOR_NAME",
    "DEBTOR_BIRTHDATE",
    "DEBTOR_CODE",
    "CREDITOR_NAME",
    "CREDITOR_CODE",
    "VP_ORDERNUM",
    "VP_BEGINDATE",
    "VP_STATE",
    "ORG_NAME",
    "DVS_CODE",
]


class SemicolonDialect(csv.Dialect):
    delimiter = ";"
    quotechar = '"'
    escapechar = None
    doublequote = True
    skipinitialspace = False
    lineterminator = "\n"
    quoting = csv.QUOTE_MINIMAL


class PrefixRawStream(io.RawIOBase):
    def __init__(self, prefix: bytes, stream: io.BufferedReader):
        self._prefix = memoryview(prefix)
        self._prefix_pos = 0
        self._stream = stream

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray) -> int:
        if self._prefix_pos < len(self._prefix):
            size = min(len(buffer), len(self._prefix) - self._prefix_pos)
            buffer[:size] = self._prefix[self._prefix_pos:self._prefix_pos + size]
            self._prefix_pos += size
            return size

        data = self._stream.read(len(buffer))

        if not data:
            return 0

        buffer[:len(data)] = data
        return len(data)


def download_zip_to_tempfile() -> Path:
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_path = Path(temp.name)

        print(f"Downloading ASVP ZIP, attempt {attempt}/{max_attempts}: {temp_path}")

        try:
            with requests.get(ZIP_URL, stream=True, timeout=600) as response:
                response.raise_for_status()

                total = 0

                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue

                    temp.write(chunk)
                    total += len(chunk)

                    if total % (1024 * 1024 * 500) < CHUNK_SIZE:
                        print(f"Downloaded: {total / 1024 / 1024:.1f} MB")

            temp.close()

            print(f"Download complete: {temp_path.stat().st_size / 1024 / 1024:.1f} MB")
            return temp_path

        except Exception as exc:
            temp.close()
            temp_path.unlink(missing_ok=True)

            print(f"Download attempt {attempt} failed: {exc}")

            if attempt >= max_attempts:
                raise

            time.sleep(20 * attempt)

    raise RuntimeError("Download failed")


def get_csv_name_with_unzip(zip_path: Path) -> str:
    result = subprocess.run(
        ["unzip", "-Z1", str(zip_path)],
        text=True,
        capture_output=True,
        check=True,
    )

    names = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().lower().endswith(".csv")
    ]

    if not names:
        raise RuntimeError("No CSV files found inside ZIP")

    return names[0]


def detect_dialect_from_sample(sample_text: str) -> csv.Dialect:
    if not sample_text.strip():
        print("Empty CSV sample. Falling back to semicolon delimiter.")
        return SemicolonDialect

    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=";,|\t,")
        print(f"Detected delimiter: {repr(dialect.delimiter)}")
        return dialect

    except csv.Error:
        print("Could not detect CSV delimiter. Falling back to semicolon delimiter.")
        return SemicolonDialect


def build_indexes(headers: list[str]) -> dict[str, int]:
    index_by_name = {name: idx for idx, name in enumerate(headers)}
    missing = [col for col in REQUIRED_COLUMNS if col not in index_by_name]

    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    return {col: index_by_name[col] for col in REQUIRED_COLUMNS}


def build_watch_indexes(watchlist: dict[str, Any]) -> dict[str, Any]:
    companies_by_code: dict[str, list[dict[str, Any]]] = {}
    persons_by_name: dict[str, list[dict[str, Any]]] = {}

    for subject in watchlist.get("subjects", []):
        if subject.get("enabled") is False:
            continue

        subject_type = subject.get("type")
        roles = set(subject.get("roles", []))

        normalized = {
            **subject,
            "roles": list(roles),
            "name_norm": normalize_text(subject.get("name")),
            "code_norm": normalize_code(subject.get("code")),
            "birthdate_norm": str(subject.get("birthdate") or "").strip(),
        }

        if subject_type == "company" and normalized["code_norm"]:
            companies_by_code.setdefault(normalized["code_norm"], []).append(normalized)

        if subject_type == "person" and normalized["name_norm"]:
            persons_by_name.setdefault(normalized["name_norm"], []).append(normalized)

    return {
        "companies_by_code": companies_by_code,
        "persons_by_name": persons_by_name,
    }


def make_record(
    *,
    row: list[str],
    idx: dict[str, int],
    subject: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    return {
        "match_key": f"{row[idx['VP_ORDERNUM']]}|{role}|{subject['id']}",
        "subject_id": subject["id"],
        "subject_type": subject.get("type"),
        "subject_name": subject.get("name"),
        "subject_code": subject.get("code"),
        "role": role,
        "vp_ordernum": row[idx["VP_ORDERNUM"]],
        "vp_begindate": row[idx["VP_BEGINDATE"]],
        "vp_state": row[idx["VP_STATE"]],
        "debtor_name": row[idx["DEBTOR_NAME"]],
        "debtor_birthdate": row[idx["DEBTOR_BIRTHDATE"]],
        "debtor_code": row[idx["DEBTOR_CODE"]],
        "creditor_name": row[idx["CREDITOR_NAME"]],
        "creditor_code": row[idx["CREDITOR_CODE"]],
        "org_name": row[idx["ORG_NAME"]],
        "dvs_code": row[idx["DVS_CODE"]],
    }


def find_matches(
    row: list[str],
    idx: dict[str, int],
    watch: dict[str, Any],
) -> list[tuple[dict[str, Any], str]]:
    matches: list[tuple[dict[str, Any], str]] = []

    debtor_code = normalize_code(row[idx["DEBTOR_CODE"]])
    creditor_code = normalize_code(row[idx["CREDITOR_CODE"]])

    debtor_name = normalize_text(row[idx["DEBTOR_NAME"]])
    creditor_name = normalize_text(row[idx["CREDITOR_NAME"]])
    debtor_birthdate = str(row[idx["DEBTOR_BIRTHDATE"]] or "").strip()

    for subject in watch["companies_by_code"].get(debtor_code, []):
        if "debtor" in subject["roles"]:
            matches.append((subject, "debtor"))

    for subject in watch["companies_by_code"].get(creditor_code, []):
        if "creditor" in subject["roles"]:
            matches.append((subject, "creditor"))

    for subject in watch["persons_by_name"].get(debtor_name, []):
        if "debtor" not in subject["roles"]:
            continue

        expected_birthdate = subject.get("birthdate_norm")

        if expected_birthdate and expected_birthdate != debtor_birthdate:
            continue

        matches.append((subject, "debtor"))

    for subject in watch["persons_by_name"].get(creditor_name, []):
        if "creditor" in subject["roles"]:
            matches.append((subject, "creditor"))

    return matches


def scan_csv_from_zip_with_unzip(
    zip_path: Path,
    watch: dict[str, Any],
) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    rows_scanned = 0
    csv_file_name = get_csv_name_with_unzip(zip_path)

    print(f"CSV file: {csv_file_name}")
    print("Reading CSV via: unzip -p")

    process = subprocess.Popen(
        ["unzip", "-p", str(zip_path), csv_file_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if process.stdout is None:
        raise RuntimeError("Could not open unzip stdout")

    try:
        prefix = process.stdout.read(SNIFF_BYTES)

        sample_text = prefix.decode(
            ENCODING,
            errors="replace",
        )

        dialect = detect_dialect_from_sample(sample_text)

        prefixed_raw = PrefixRawStream(
            prefix=prefix,
            stream=process.stdout,
        )

        buffered = io.BufferedReader(prefixed_raw)

        text_stream = io.TextIOWrapper(
            buffered,
            encoding=ENCODING,
            newline="",
            errors="replace",
        )

        reader = csv.reader(
            text_stream,
            dialect=dialect,
        )

        headers = next(reader)
        idx = build_indexes(headers)

        print(f"Headers: {headers}")

        for row in reader:
            rows_scanned += 1

            if len(row) < len(headers):
                continue

            matches = find_matches(row, idx, watch)

            for subject, role in matches:
                record = make_record(
                    row=row,
                    idx=idx,
                    subject=subject,
                    role=role,
                )

                records[record["match_key"]] = record

            if rows_scanned % 1_000_000 == 0:
                print(
                    f"Rows scanned: {rows_scanned:,}; "
                    f"matched records: {len(records):,}"
                )

    finally:
        return_code = process.wait()
        stderr_text = ""

        if process.stderr is not None:
            stderr_text = process.stderr.read().decode(
                "utf-8",
                errors="replace",
            ).strip()

        if return_code != 0:
            warning = (
                f"unzip exited with code {return_code} "
                f"after scanning {rows_scanned:,} rows."
            )

            if stderr_text:
                warning += f" stderr: {stderr_text[-1000:]}"

            print(f"WARNING: {warning}")
            warnings.append(warning)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_url": ZIP_URL,
        "csv_file_name": csv_file_name,
        "reader": "unzip -p",
        "rows_scanned": rows_scanned,
        "matched_records_total": len(records),
        "is_partial": bool(warnings),
        "warnings": warnings,
        "records": sorted(
            records.values(),
            key=lambda item: (
                item.get("subject_id") or "",
                item.get("role") or "",
                item.get("vp_ordernum") or "",
            ),
        ),
    }


def main() -> None:
    watchlist = load_json(WATCHLIST_PATH)
    watch = build_watch_indexes(watchlist)

    print("Watchlist loaded")
    print(f"Company codes: {len(watch['companies_by_code'])}")
    print(f"Person names: {len(watch['persons_by_name'])}")

    zip_path = download_zip_to_tempfile()

    try:
        snapshot = scan_csv_from_zip_with_unzip(
            zip_path=zip_path,
            watch=watch,
        )

        save_json(OUTPUT_PATH, snapshot)

        print(f"Saved current snapshot: {OUTPUT_PATH}")
        print(f"Rows scanned: {snapshot['rows_scanned']:,}")
        print(f"Matched records: {snapshot['matched_records_total']:,}")
        print(f"Partial snapshot: {snapshot['is_partial']}")

    finally:
        zip_path.unlink(missing_ok=True)
        print("Temporary ZIP removed")


if __name__ == "__main__":
    main()
