"""Client tests. The session is injected, so nothing connects to curlbus."""

import json
from pathlib import Path

import pytest

from custom_components.public_transport_il.curlbus import CurlbusClient
from custom_components.public_transport_il.source import BadResponseError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_BASE_URL = "https://curlbus.test"


def _load_text(name: str) -> str:
    """Return a fixture body as text."""
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Response:
    """Async context manager that serves one canned body."""

    def __init__(self, body: str, status: int = 200) -> None:
        self.status = status
        self._body = body

    async def text(self) -> str:
        """Return the canned body."""
        return self._body

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _Session:
    """Record GET calls and return a canned response."""

    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body
        self._status = status
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> _Response:
        """Record the request and return the canned response."""
        self.calls.append((url, dict(headers or {})))
        return _Response(self._body, self._status)


async def test_fetch_stop_uses_injected_session() -> None:
    """One GET uses the stop path and the JSON accept header."""
    session = _Session(_load_text("stop_20112_has_249.json"))
    client = CurlbusClient(session, base_url=_BASE_URL)
    snapshot = await client.async_get_stop("20112")

    assert session.calls == [
        (f"{_BASE_URL}/20112", {"Accept": "application/json"}),
    ]
    assert snapshot.stop_code == "20112"
    assert snapshot.stop_name == "מחלף גלילות/דרך נמיר"
    assert any(
        item.route_id == "10119"
        and item.operator_id == "15"
        and item.line_name == "249"
        for item in snapshot.arrivals
    )

    broken = CurlbusClient(_Session("not-json"), base_url=_BASE_URL)
    with pytest.raises(BadResponseError):
        await broken.async_get_stop("20112")


async def test_metropoline_line_lookup() -> None:
    """Operator 15 matches route_alternatives short_name and ignores other agencies."""
    body = _load_text("metropoline_249_routes.json")
    session = _Session(body)
    client = CurlbusClient(session, base_url=_BASE_URL)
    assert await client.async_operator_serves_line("15", "249") is True
    assert session.calls == [
        (f"{_BASE_URL}/metropoline/249", {"Accept": "application/json"}),
    ]

    missing = json.loads(body)
    for item in missing["route_alternatives"]:
        item["short_name"] = "5"
    negative = _Session(json.dumps(missing))
    negative_client = CurlbusClient(negative, base_url=_BASE_URL)
    assert await negative_client.async_operator_serves_line("15", "249") is False
    assert negative.calls[0][0] == f"{_BASE_URL}/metropoline/249"

    other = _Session(body)
    other_client = CurlbusClient(other, base_url=_BASE_URL)
    assert await other_client.async_operator_serves_line("3", "249") is False
    assert other.calls == []
