"""Download the public data.gov.sg datasets the experiment reads (no key needed)."""

import json
import time
from pathlib import Path

import httpx

DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{id}/poll-download"
METADATA_URL = "https://api-production.data.gov.sg/v2/public/api/datasets/{id}/metadata"

DATASETS = {
    "nparks_tracks": "d_306cc1018cb733346681883ee6d73054",
    "park_connector_loop": "d_a69ef89737379f231d2ae93fd1c5707f",
    "parks_and_nature_reserves": "d_77d7ec97be83d44f61b85454f844382f",
    "singapore_boundary": "d_4765db0e87b9c86336792efe8a1f7a66",
}
POLL_ATTEMPTS = 5
POLL_PAUSE_SECONDS = 5


def fetch_dataset(http: httpx.Client, dataset_id: str, target: Path) -> None:
    for _ in range(POLL_ATTEMPTS):
        poll = http.get(DOWNLOAD_URL.format(id=dataset_id), timeout=30).json()
        url = (poll.get("data") or {}).get("url")
        if url:
            response = http.get(url, timeout=120)
            response.raise_for_status()
            target.write_bytes(response.content)
            return
        time.sleep(POLL_PAUSE_SECONDS)
    raise RuntimeError(f"data.gov.sg did not offer a download for {dataset_id}")


def fetch_all(http: httpx.Client, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, dataset_id in DATASETS.items():
        fetch_dataset(http, dataset_id, data_dir / f"{name}.geojson")
        metadata = http.get(METADATA_URL.format(id=dataset_id), timeout=30).json()
        (data_dir / f"{name}.metadata.json").write_text(json.dumps(metadata, indent=2))
        print(f"{name}: {dataset_id} -> {data_dir / name}.geojson")
