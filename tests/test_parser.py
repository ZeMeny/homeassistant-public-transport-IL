"""Parser tests. Every case reads a local fixture and does not use the network."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.public_transport_il.parser import parse_stop_payload
from custom_components.public_transport_il.source import (
    BadResponseError,
    StopNotFoundError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_JERUSALEM = ZoneInfo("Asia/Jerusalem")


def _load(name: str) -> dict[str, object]:
    """Return one JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_eta_timezone_offsets_and_naive_israel_local() -> None:
    """Explicit offsets stay as recorded, and a naive ETA is Israel local time."""
    recorded = parse_stop_payload(_load("stop_20112_has_249.json"), stop_code="20112")
    recorded_249 = next(item for item in recorded.arrivals if item.line_name == "249")
    assert recorded_249.route_id == "10119"
    assert recorded_249.operator_id == "15"
    assert recorded_249.operator_name == "Metropoline"
    assert recorded_249.headsign == "תל אביב יפו_מסוף כרמלית"
    assert recorded_249.destination_stop_code == "25354"
    assert recorded_249.live is True
    assert recorded_249.eta == datetime.fromisoformat("2026-10-27 21:48:00+02:00")
    assert recorded_249.eta.utcoffset() == timedelta(hours=2)
    assert recorded_249.eta.tzinfo == timezone(timedelta(hours=2))
    assert recorded.timestamp == datetime.fromisoformat("2026-10-27T21:20:04+02:00")

    mixed = parse_stop_payload(_load("naive_eta.json"), stop_code="90001")
    by_route = {item.route_id: item for item in mixed.arrivals}
    assert set(by_route) == {"naive", "plus03"}

    naive = by_route["naive"]
    assert naive.eta.tzinfo == _JERUSALEM
    assert naive.eta.replace(tzinfo=None) == datetime(2026, 10, 27, 21, 48, 0)
    # 27 Oct 2026 is after Israel's last-Sunday-of-October DST change.
    assert naive.eta.utcoffset() == timedelta(hours=2)

    plus_three = by_route["plus03"]
    assert plus_three.eta == datetime.fromisoformat("2026-07-01 12:00:00+03:00")
    assert plus_three.eta.tzinfo == timezone(timedelta(hours=3))
    assert plus_three.eta.utcoffset() == timedelta(hours=3)


def test_missing_line_249_is_empty_success() -> None:
    """A real stop payload without line 249 parses and simply lacks that line.

    The live 25629 response on 2026-10-27 also contained Metropoline 249
    (route 10120). That one visit is removed in the fixture; the stop name,
    timestamp, and the other visits are the recorded public payload.
    """
    snapshot = parse_stop_payload(_load("stop_25629_no_249.json"), stop_code="25629")

    assert snapshot.stop_code == "25629"
    assert snapshot.stop_name == "כיכר רבין/מלכי ישראל"
    assert snapshot.arrivals
    assert all(item.line_name != "249" for item in snapshot.arrivals)
    assert all(item.route_id != "10120" for item in snapshot.arrivals)


def test_live_flag_follows_producer() -> None:
    """SIRI and GTFS-RT are live. Any other producer is scheduled."""
    recorded = parse_stop_payload(_load("stop_20112_has_249.json"), stop_code="20112")
    assert recorded.arrivals
    assert all(item.live for item in recorded.arrivals)

    scheduled = parse_stop_payload(_load("scheduled_producer.json"), stop_code="90003")
    by_route = {item.route_id: item for item in scheduled.arrivals}
    assert by_route["rt-live"].live is True
    assert by_route["rt-live"].headsign == "חי"
    assert by_route["scheduled"].live is False
    assert by_route["scheduled"].headsign == "English Headsign"
    assert by_route["scheduled"].operator_name == "Other Agency"
    assert scheduled.stop_name == "English Stop"


def test_invalid_stop_errors_raise() -> None:
    """A curlbus errors list is a stop-not-found error, not a snapshot."""
    with pytest.raises(StopNotFoundError, match="Invalid stop code 99999999"):
        parse_stop_payload(_load("invalid_stop.json"))

    with pytest.raises(BadResponseError):
        parse_stop_payload(["not", "an", "object"])
