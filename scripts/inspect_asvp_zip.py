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


class SemicolonDialect(csv.excel):
    delimiter = ";"


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
        print("Could not detect CSV delimiter
