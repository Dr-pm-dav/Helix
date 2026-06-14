"""Start Helix briefly and exercise the real local HTTP routes.

Verifies the static dashboard always serves. The data endpoints require an
ingested dataset (run ``scripts/ingest_slice.py`` with an EIA key first); if
none is present the app returns a clean 503, which this smoke test reports
without failing.
"""
from __future__ import annotations

import json
import threading
import time
from urllib.error import HTTPError
from urllib.request import urlopen

import uvicorn

from helix.api import create_app

BASE_URL = "http://127.0.0.1:8011"
REQUEST_TIMEOUT_SECONDS = 30


def get_json(path: str) -> dict[str, object]:
    with urlopen(f"{BASE_URL}{path}", timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.load(response)


def get_text(path: str) -> str:
    with urlopen(f"{BASE_URL}{path}", timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def main() -> int:
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=8011, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Helix server did not start")

    try:
        html = get_text("/")
        javascript = get_text("/static/dashboard.js")
        print(f"html title present: {'<title>Helix Grid Intelligence</title>' in html}")
        print(f"dashboard javascript bytes: {len(javascript.encode('utf-8'))}")
        try:
            health = get_json("/api/health")
            dashboard = get_json("/api/dashboard?respondent=CISO&start=2025-04-01&end=2025-04-30")
            summary = dashboard["summary"]
            coverage = dashboard["coverage"]
            print(f"health: {health['status']}")
            print(f"hourly observations: {coverage['hourlyRows']}")
            print(f"peak demand MWh: {summary['peakDemandMwh']}")
            print(f"minimum net load MWh: {summary['minimumNetLoadMwh']}")
            print(f"steepest hourly ramp MWh: {summary['steepestHourlyRampMwh']}")
        except HTTPError as error:
            if error.code == 503:
                print("data endpoints: 503 (no data ingested yet) "
                      "-> run scripts/ingest_slice.py with EIA_API_KEY; static app verified")
            else:
                raise
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
