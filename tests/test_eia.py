from __future__ import annotations

from typing import Any

from helix.eia import EiaClient


class StubEiaClient(EiaClient):
    def __init__(self) -> None:
        super().__init__("test-key", page_size=2)
        self.offsets: list[int] = []

    def _fetch_page(self, route: str, **kwargs: Any) -> dict[str, Any]:
        offset = kwargs["offset"]
        self.offsets.append(offset)
        rows = [{"period": str(index)} for index in range(offset, min(offset + 2, 5))]
        return {"response": {"total": "5", "data": rows}}


def test_iter_rows_paginates_until_total() -> None:
    client = StubEiaClient()

    rows = client.fetch_all(
        "sample-route",
        frequency="hourly",
        data_fields=["value"],
        start="2025-04-01T00",
        end="2025-04-01T23",
    )

    assert client.offsets == [0, 2, 4]
    assert [row["period"] for row in rows] == ["0", "1", "2", "3", "4"]

