"""Coordinator tests. The source is a fake, so nothing connects to curlbus."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.public_transport_il.const import DOMAIN
from custom_components.public_transport_il.coordinator import (
    async_subscribe_stop,
    async_unsubscribe_stop,
    select_arrivals,
)
from custom_components.public_transport_il.parser import parse_stop_payload
from custom_components.public_transport_il.source import (
    Arrival,
    SourceUnavailableError,
    StopSnapshot,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
_OFFSET = timezone(timedelta(hours=2))


def _load(name: str) -> dict[str, object]:
    """Return one JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _snapshot(name: str, stop_code: str) -> StopSnapshot:
    """Parse a fixture into a snapshot."""
    return parse_stop_payload(_load(name), stop_code=stop_code)


def _arrival(**overrides: object) -> Arrival:
    """Build one arrival for selector cases."""
    values: dict[str, object] = {
        "route_id": "10119",
        "line_name": "249",
        "operator_id": "15",
        "operator_name": "Metropoline",
        "headsign": "headsign",
        "eta": datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET),
        "live": True,
        "destination_stop_code": "25354",
    }
    values.update(overrides)
    return Arrival(**values)  # type: ignore[arg-type]


class _CountingSource:
    """Arrival source that counts ``async_get_stop`` calls."""

    def __init__(
        self,
        snapshot: StopSnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls: list[str] = []

    async def async_get_stop(self, stop_code: str) -> StopSnapshot:
        """Return the canned snapshot or raise a fresh copy of the canned error."""
        self.calls.append(stop_code)
        if self.error is not None:
            raise type(self.error)(str(self.error))
        assert self.snapshot is not None
        return self.snapshot

    async def async_operator_serves_line(
        self, operator_id: str, line_number: str
    ) -> bool:
        """Unused by the coordinator."""
        return False


async def test_coordinator_publishes_snapshot(hass: HomeAssistant) -> None:
    """The first refresh stores the stop snapshot from the source."""
    snapshot = _snapshot("stop_20112_has_249.json", "20112")
    source = _CountingSource(snapshot)

    coordinator = await async_subscribe_stop(hass, "20112", source)

    assert coordinator.data is snapshot
    assert coordinator.data.stop_code == "20112"
    assert coordinator.data.stop_name == "מחלף גלילות/דרך נמיר"
    assert any(item.route_id == "10119" for item in coordinator.data.arrivals)
    assert coordinator.last_update_success is True
    assert coordinator.update_interval == timedelta(seconds=60)
    assert source.calls == ["20112"]
    await async_unsubscribe_stop(hass, "20112")


async def test_unreachable_marks_update_failed(hass: HomeAssistant) -> None:
    """A source outage is UpdateFailed and the coordinator is not successful."""
    source = _CountingSource(error=SourceUnavailableError("curlbus down"))

    coordinator = await async_subscribe_stop(hass, "20112", source)

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert source.calls == ["20112"]
    await async_unsubscribe_stop(hass, "20112")


async def test_one_poll_per_60s_shared_by_stop(hass: HomeAssistant) -> None:
    """Two subscribers share one coordinator and one extra fetch per 60 seconds."""
    snapshot = _snapshot("stop_20112_has_249.json", "20112")
    source = _CountingSource(snapshot)

    first = await async_subscribe_stop(hass, "20112", source)
    second = await async_subscribe_stop(hass, "20112", source)

    assert first is second
    assert source.calls == ["20112"]
    assert hass.data[DOMAIN]["coordinators"]["20112"].subscribers == 2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert source.calls == ["20112", "20112"]

    await async_unsubscribe_stop(hass, "20112")
    assert hass.data[DOMAIN]["coordinators"]["20112"].subscribers == 1
    await async_unsubscribe_stop(hass, "20112")
    assert "20112" not in hass.data[DOMAIN]["coordinators"]

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert source.calls == ["20112", "20112"]


async def test_missing_line_is_successful_empty_update(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A payload without line 249 succeeds, selects nothing, and logs no error."""
    snapshot = _snapshot("stop_25629_no_249.json", "25629")
    source = _CountingSource(snapshot)

    with caplog.at_level(logging.ERROR):
        coordinator = await async_subscribe_stop(hass, "25629", source)
        await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data.stop_code == "25629"
    assert select_arrivals(coordinator.data, "249", "15", "10119") == ()
    assert select_arrivals(coordinator.data, "249", "15", "") == ()
    assert source.calls == ["25629", "25629"]
    assert not [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR
        and record.name.startswith("custom_components.public_transport_il")
    ]
    await async_unsubscribe_stop(hass, "25629")


def test_select_arrivals_match_order() -> None:
    """Route id wins, a single replacement route is adopted, ambiguity is empty."""
    ambiguous = _snapshot("ambiguous_line_249.json", "90002")
    assert select_arrivals(ambiguous, "249", None, None) == ()
    operator_3 = select_arrivals(ambiguous, "249", "3", None)
    assert [item.route_id for item in operator_3] == ["3001"]
    by_route = select_arrivals(ambiguous, "249", None, "5001")
    assert [item.route_id for item in by_route] == ["5001"]

    prefer_metropoline = StopSnapshot(
        stop_code="1",
        stop_name="stop",
        timestamp=datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET),
        arrivals=(
            _arrival(route_id="3001", operator_id="3", operator_name="Egged"),
            _arrival(route_id="10119", operator_id="15"),
        ),
    )
    preferred = select_arrivals(prefer_metropoline, "249", None, None)
    assert [item.operator_id for item in preferred] == ["15"]

    only_other = StopSnapshot(
        stop_code="1",
        stop_name="stop",
        timestamp=datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET),
        arrivals=(_arrival(route_id="42", operator_id="25", line_name="5"),),
    )
    assert [item.route_id for item in select_arrivals(only_other, "5", None, None)] == [
        "42"
    ]

    adopted = StopSnapshot(
        stop_code="1",
        stop_name="stop",
        timestamp=datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET),
        arrivals=(_arrival(route_id="99999"),),
    )
    adopted_ids = [
        item.route_id for item in select_arrivals(adopted, "249", "15", "10119")
    ]
    assert adopted_ids == ["99999"]

    ambiguous_routes = StopSnapshot(
        stop_code="1",
        stop_name="stop",
        timestamp=datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET),
        arrivals=(
            _arrival(route_id="10001"),
            _arrival(route_id="10002"),
        ),
    )
    assert select_arrivals(ambiguous_routes, "249", "15", "10119") == ()

    stored_route = select_arrivals(ambiguous_routes, "249", "15", "10002")
    assert [item.route_id for item in stored_route] == ["10002"]
