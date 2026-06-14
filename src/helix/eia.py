"""Small EIA API v2 client with explicit pagination."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE_URL = "https://api.eia.gov/v2"
MAX_PAGE_SIZE = 5000


class EiaClient:
    def __init__(
        self,
        api_key: str,
        *,
        page_size: int = MAX_PAGE_SIZE,
        retries: int = 3,
        retry_delay_seconds: float = 0.5,
    ) -> None:
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        self.api_key = api_key
        self.page_size = page_size
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

    def fetch_all(
        self,
        route: str,
        *,
        frequency: str,
        data_fields: Sequence[str],
        start: str,
        end: str,
        facets: Mapping[str, Sequence[str]] | None = None,
    ) -> list[dict[str, Any]]:
        return list(
            self.iter_rows(
                route,
                frequency=frequency,
                data_fields=data_fields,
                start=start,
                end=end,
                facets=facets,
            )
        )

    def iter_rows(
        self,
        route: str,
        *,
        frequency: str,
        data_fields: Sequence[str],
        start: str,
        end: str,
        facets: Mapping[str, Sequence[str]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            payload = self._fetch_page(
                route,
                frequency=frequency,
                data_fields=data_fields,
                start=start,
                end=end,
                facets=facets,
                offset=offset,
            )
            response = payload["response"]
            rows = response["data"]
            yield from rows
            offset += len(rows)
            if offset >= int(response["total"]) or not rows:
                break

    def _fetch_page(
        self,
        route: str,
        *,
        frequency: str,
        data_fields: Sequence[str],
        start: str,
        end: str,
        facets: Mapping[str, Sequence[str]] | None,
        offset: int,
    ) -> dict[str, Any]:
        params: list[tuple[str, str | int]] = [
            ("api_key", self.api_key),
            ("frequency", frequency),
            ("start", start),
            ("end", end),
            ("offset", offset),
            ("length", self.page_size),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
        ]
        params.extend((f"data[{index}]", field) for index, field in enumerate(data_fields))
        for facet_name, values in (facets or {}).items():
            params.extend((f"facets[{facet_name}][]", value) for value in values)

        url = f"{BASE_URL}/{route}/data/?{urlencode(params)}"
        for attempt in range(self.retries + 1):
            try:
                with urlopen(url, timeout=30) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise
            except URLError:
                if attempt == self.retries:
                    raise
            time.sleep(self.retry_delay_seconds * (2**attempt))
        raise AssertionError("unreachable")

