"""Fetch, cache, and parse one explicitly provided CarWale variant page."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from scraping.sources.carwale_variant_parser import parse_carwale_variant


RAW_HTML_DIR = Path("datasets/raw/carwale/html")
RAW_RECORD_DIR = Path("datasets/raw/carwale/records")
FETCH_LOG_PATH = Path("scraping/logs/carwale_fetch_log.jsonl")

REQUEST_TIMEOUT_SECONDS = 20
DEFAULT_DELAY_SECONDS = 2
MAX_RETRIES = 3
BACKOFF_SECONDS = 2
TEMPORARY_STATUS_CODES = {429, 500, 502, 503, 504}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.carwale.com/",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_carwale_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "www.carwale.com" or not parsed.path:
        raise ValueError("Only valid https://www.carwale.com/ URLs are accepted.")


def safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_slug = re.sub(r"[^a-zA-Z0-9]+", "_", parsed.path.strip("/")).strip("_")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{path_slug}_{digest}.html"


def record_filename_from_url(url: str) -> str:
    return safe_filename_from_url(url).replace(".html", ".json")


def append_fetch_log(metadata: dict) -> None:
    FETCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FETCH_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(metadata, sort_keys=True) + "\n")


def fetch_carwale_html(
    url: str,
    output_dir: str | Path,
    force_refresh: bool = False,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
) -> dict:
    """Fetch or load cached HTML for one CarWale URL."""
    metadata = {
        "url": url,
        "http_status": None,
        "cached_or_fetched": None,
        "saved_path": None,
        "response_size": 0,
        "fetched_at": None,
        "error": None,
    }

    try:
        validate_carwale_url(url)
    except ValueError as exc:
        metadata["error"] = str(exc)
        append_fetch_log(metadata)
        return metadata

    output_path = Path(output_dir) / safe_filename_from_url(url)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata["saved_path"] = str(output_path)

    if output_path.exists() and not force_refresh:
        metadata["cached_or_fetched"] = "cached"
        metadata["response_size"] = output_path.stat().st_size
        append_fetch_log(metadata)
        return metadata

    session = requests.Session()
    last_error = None

    if delay_seconds > 0:
        time.sleep(delay_seconds)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS ** attempt)
                continue
            metadata["error"] = last_error
            append_fetch_log(metadata)
            return metadata

        metadata["http_status"] = response.status_code

        if response.status_code < 400 or response.status_code in TEMPORARY_STATUS_CODES:
            if response.status_code < 400:
                output_path.write_text(response.text or "", encoding="utf-8")
                metadata["cached_or_fetched"] = "fetched"
                metadata["response_size"] = len(response.content)
                metadata["fetched_at"] = utc_now_iso()
                append_fetch_log(metadata)
                return metadata

            last_error = f"Temporary HTTP {response.status_code}"
            if attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_for = min(int(retry_after), 30)
                else:
                    sleep_for = BACKOFF_SECONDS ** attempt
                time.sleep(sleep_for)
                continue

        metadata["error"] = f"HTTP {response.status_code}"
        append_fetch_log(metadata)
        return metadata

    metadata["error"] = last_error or "Request failed after retries."
    append_fetch_log(metadata)
    return metadata


def fetch_and_parse_variant(url: str, force_refresh: bool = False) -> dict:
    """Fetch/load one CarWale variant page and parse it into a canonical record."""
    result = {
        "fetch_metadata": None,
        "parsed_record": None,
        "record_path": None,
        "error": None,
    }

    try:
        fetch_metadata = fetch_carwale_html(
            url=url,
            output_dir=RAW_HTML_DIR,
            force_refresh=force_refresh,
        )
        result["fetch_metadata"] = fetch_metadata

        if fetch_metadata.get("error"):
            result["error"] = fetch_metadata["error"]
            return result

        saved_path = fetch_metadata.get("saved_path")
        if not saved_path:
            result["error"] = "No saved HTML path was returned."
            return result

        parsed_record = parse_carwale_variant(saved_path, url)
        record_path = RAW_RECORD_DIR / record_filename_from_url(url)
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(parsed_record, indent=2), encoding="utf-8")

        result["parsed_record"] = parsed_record
        result["record_path"] = str(record_path)
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch/cache one CarWale variant page and parse it.",
    )
    parser.add_argument("variant_url")
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    result = fetch_and_parse_variant(args.variant_url, force_refresh=args.force_refresh)
    print(json.dumps(result, indent=2))

    if result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
