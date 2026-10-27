"""Sensor tests. Time is frozen and the arrival source is a fake."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.public_transport_il.const import (
    CONF_LINE_NUMBER,
    CONF_OPERATOR_ID,
    CONF_ROUTE_ID,
    CONF_STOP_CODE,
    CONF_STOP_NAME,
    DOMAIN,
    arrival_unique_id,
)
from custom_components.public_transport_il.parser import parse_stop_payload
from custom_components.public_transport_il.source import (
    Arrival,
    SourceUnavailableError,
    StopSnapshot,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
pytestmark = pytest.mark.usefixtures("enable_custom_integrations")
_SOURCE = "custom_components.public_transport_il.source.async_get_source"
_OFFSET = timezone(timedelta(hours=2))
_RECORDED_NOW = datetime.fromisoformat("2026-10-27T19:20:04+00:00")


def _load(name: str) -> dict[str, object]:
    """Return one JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _snapshot(name: str, stop_code: str) -> StopSnapshot:
    """Parse a fixture into a snapshot."""
    return parse_stop_payload(_load(name), stop_code=stop_code)


def _arrival(**overrides: object) -> Arrival:
    """Build one arrival."""
    values: dict[str, object] = {
        "route_id": "10119",
        "line_name": "249",
        "operator_id": "15",
        "operator_name": "Metropoline",
        "headsign": "מסוף כרמלית",
        "eta": datetime(2026, 10, 27, 21, 5, tzinfo=_OFFSET),
        "live": True,
        "destination_stop_code": "25354",
    }
    values.update(overrides)
    return Arrival(**values)  # type: ignore[arg-type]


class FakeSource:
    """Arrival source whose result can change between polls."""

    def __init__(
        self,
        snapshot: StopSnapshot | None = None,
        error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls: list[str] = []

    async def async_get_stop(self, stop_code: str) -> StopSnapshot:
        """Return the current snapshot or raise a fresh copy of the error."""
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


async def _setup(
    hass: HomeAssistant,
    source: FakeSource,
    *,
    stop_code: str,
    line_number: str,
    operator_id: str,
    route_id: str,
    stop_name: str,
) -> tuple[MockConfigEntry, str]:
    """Set up one entry against the fake and return the entry and entity id."""
    unique_id = arrival_unique_id(stop_code, line_number, operator_id)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        title=f"{line_number} {stop_name} ({stop_code})",
        data={
            CONF_STOP_CODE: stop_code,
            CONF_LINE_NUMBER: line_number,
            CONF_OPERATOR_ID: operator_id,
            CONF_ROUTE_ID: route_id,
            CONF_STOP_NAME: stop_name,
        },
    )
    entry.add_to_hass(hass)
    with patch(_SOURCE, return_value=source):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entry, entity_id


async def test_state_is_minutes_until_next_arrival(
    hass: HomeAssistant, freezer
) -> None:
    """The state is the floor of the remaining minutes, including a 50 second bus."""
    freezer.move_to(_RECORDED_NOW)
    snapshot = _snapshot("stop_20112_has_249.json", "20112")
    source = FakeSource(snapshot)
    _entry, entity_id = await _setup(
        hass,
        source,
        stop_code="20112",
        line_number="249",
        operator_id="15",
        route_id="10119",
        stop_name=snapshot.stop_name,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    # 21:48:00+02 minus 21:20:04+02 is 27 minutes and 56 seconds.
    assert state.state == "27"
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["unit_of_measurement"] == "min"
    assert state.attributes["icon"] == "mdi:bus"
    assert state.attributes["friendly_name"].endswith("249")

    # Fifty seconds before the same ETA floors to 0.
    freezer.move_to(datetime.fromisoformat("2026-10-27T19:47:10+00:00"))
    await _entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "0"


async def test_recent_past_eta_clamps_minutes_to_zero(
    hass: HomeAssistant, freezer
) -> None:
    """A visit 20 seconds ago is 0 minutes and stays ahead of a later bus."""
    now = datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET)
    freezer.move_to(now)
    just_left = now - timedelta(seconds=20)
    later = now + timedelta(minutes=8)
    snapshot = StopSnapshot(
        stop_code="20112",
        stop_name="מחלף גלילות/דרך נמיר",
        timestamp=now,
        arrivals=(
            _arrival(eta=later, headsign="מאוחר"),
            _arrival(eta=just_left, headsign="יצא"),
        ),
    )
    source = FakeSource(snapshot)
    _entry, entity_id = await _setup(
        hass,
        source,
        stop_code="20112",
        line_number="249",
        operator_id="15",
        route_id="10119",
        stop_name=snapshot.stop_name,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"
    assert state.attributes["arrivals"] == [
        {
            "eta": just_left.isoformat(),
            "minutes": 0,
            "headsign": "יצא",
            "live": True,
        },
        {
            "eta": later.isoformat(),
            "minutes": 8,
            "headsign": "מאוחר",
            "live": True,
        },
    ]


async def test_state_unknown_when_no_arrival(hass: HomeAssistant, freezer) -> None:
    """No selected arrival is unknown, and the entity stays available."""
    freezer.move_to(_RECORDED_NOW)
    snapshot = _snapshot("stop_25629_no_249.json", "25629")
    source = FakeSource(snapshot)
    _entry, entity_id = await _setup(
        hass,
        source,
        stop_code="25629",
        line_number="249",
        operator_id="15",
        route_id="",
        stop_name=snapshot.stop_name,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes["arrivals"] == []
    assert state.attributes["route_id"] == ""
    assert state.attributes["operator"] == "15"
    assert state.attributes["last_update"] == snapshot.timestamp.isoformat()


async def test_attributes_include_next_three_arrivals(
    hass: HomeAssistant, freezer
) -> None:
    """Attributes keep the next three visits and drop a stale one and a fourth."""
    now = datetime(2026, 10, 27, 21, 0, tzinfo=_OFFSET)
    freezer.move_to(now)
    snapshot = StopSnapshot(
        stop_code="20112",
        stop_name="מחלף גלילות/דרך נמיר",
        timestamp=now,
        arrivals=(
            _arrival(
                eta=now - timedelta(seconds=31),
                headsign="עבר",
                live=False,
            ),
            _arrival(eta=now + timedelta(seconds=50), headsign="עוד רגע", live=True),
            _arrival(
                eta=now + timedelta(minutes=5),
                headsign="חמש",
                live=False,
            ),
            _arrival(
                eta=now + timedelta(minutes=12),
                headsign="שתים עשרה",
                live=True,
            ),
            _arrival(
                eta=now + timedelta(minutes=30),
                headsign="שלושים",
                live=True,
            ),
            _arrival(
                route_id="1",
                line_name="5",
                operator_id="3",
                operator_name="Egged",
                headsign="קו אחר",
                eta=now + timedelta(minutes=1),
            ),
        ),
    )
    source = FakeSource(snapshot)
    _entry, entity_id = await _setup(
        hass,
        source,
        stop_code="20112",
        line_number="249",
        operator_id="15",
        route_id="10119",
        stop_name=snapshot.stop_name,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"
    arrivals = state.attributes["arrivals"]
    assert arrivals == [
        {
            "eta": (now + timedelta(seconds=50)).isoformat(),
            "minutes": 0,
            "headsign": "עוד רגע",
            "live": True,
        },
        {
            "eta": (now + timedelta(minutes=5)).isoformat(),
            "minutes": 5,
            "headsign": "חמש",
            "live": False,
        },
        {
            "eta": (now + timedelta(minutes=12)).isoformat(),
            "minutes": 12,
            "headsign": "שתים עשרה",
            "live": True,
        },
    ]
    assert all("+" in item["eta"] for item in arrivals)
    assert state.attributes["route_id"] == "10119"
    assert state.attributes["operator"] == "Metropoline"
    assert state.attributes["last_update"] == now.isoformat()


async def test_missing_line_is_unknown_without_error_log(
    hass: HomeAssistant, freezer, caplog: pytest.LogCaptureFixture
) -> None:
    """A stop without the line stays unknown and logs no error across two polls."""
    freezer.move_to(_RECORDED_NOW)
    snapshot = _snapshot("stop_25629_no_249.json", "25629")
    source = FakeSource(snapshot)

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        _entry, entity_id = await _setup(
            hass,
            source,
            stop_code="25629",
            line_number="249",
            operator_id="15",
            route_id="10120",
            stop_name=snapshot.stop_name,
        )
        assert hass.states.get(entity_id).state == STATE_UNKNOWN

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert source.calls == ["25629", "25629"]
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


async def test_unavailable_until_next_success(hass: HomeAssistant, freezer) -> None:
    """A failed poll is unavailable and the next success publishes minutes again."""
    freezer.move_to(_RECORDED_NOW)
    snapshot = _snapshot("stop_20112_has_249.json", "20112")
    source = FakeSource(error=SourceUnavailableError("curlbus down"))
    _entry, entity_id = await _setup(
        hass,
        source,
        stop_code="20112",
        line_number="249",
        operator_id="15",
        route_id="10119",
        stop_name="מחלף גלילות/דרך נמיר",
    )

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    source.error = None
    source.snapshot = snapshot
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "27"
    assert source.calls == ["20112", "20112"]
