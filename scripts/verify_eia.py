"""Verify that Helix can reach the EIA routes required by the MVP."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE_URL = "https://api.eia.gov/v2"
ROUTES = (
    "electricity/rto/region-data",
    "electricity/rto/fuel-type-data",
    "nuclear-outages/facility-nuclear-outages",
)


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def fetch_route_metadata(route: str, api_key: str) -> dict[str, object]:
    query = urlencode({"api_key": api_key})
    with urlopen(f"{BASE_URL}/{route}/?{query}", timeout=15) as response:
        payload = json.load(response)
    return payload["response"]


def main() -> int:
    load_local_env()
    api_key = os.getenv("EIA_API_KEY")
    if not api_key:
        print("Missing EIA_API_KEY. Add it to .env or the environment.", file=sys.stderr)
        return 1

    try:
        for route in ROUTES:
            metadata = fetch_route_metadata(route, api_key)
            print(f"OK  {route}: {metadata['name']}")
    except HTTPError as exc:
        print(f"EIA returned HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Could not reach EIA: {exc.reason}", file=sys.stderr)
        return 1

    print("Helix EIA access is configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

