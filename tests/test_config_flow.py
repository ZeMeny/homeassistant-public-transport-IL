"""Config and options flow tests. The arrival source is a fake."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import voluptuous as vol
import voluptuous_serialize
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

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
    BadResponseError,
    SourceUnavailableError,
    StopNotFoundError,
    StopSnapshot,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
pytestmark = pytest.mark.usefixtures("enable_custom_integrations")
_SOURCE = "custom_components.public_transport_il.source.async_get_source"


def _load(name: str) -> dict[str, object]:
    """Return one JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _snapshot(name: str, stop_code: str) -> StopSnapshot:
    """Parse a fixture into a snapshot."""
    return parse_stop_payload(_load(name), stop_code=stop_code)


class FakeSource:
    """Arrival source that serves canned snapshots and line lookups."""

    def __init__(
        self,
        snapshots: dict[str, StopSnapshot | Exception],
        *,
        served: set[tuple[str, str]] | None = None,
    ) -> None:
        self.snapshots = snapshots
        self.served = served or set()
        self.stop_calls: list[str] = []
        self.line_calls: list[tuple[str, str]] = []

    async def async_get_stop(self, stop_code: str) -> StopSnapshot:
        """Return the canned snapshot or raise a fresh copy of the canned error."""
        self.stop_calls.append(stop_code)
        result = self.snapshots[stop_code]
        if isinstance(result, Exception):
            raise type(result)(str(result))
        return result

    async def async_operator_serves_line(
        self, operator_id: str, line_number: str
    ) -> bool:
        """Return whether this pair was marked as served."""
        self.line_calls.append((operator_id, line_number))
        return (operator_id, line_number) in self.served


def _patch(source: FakeSource):
    """Patch the factory so the flow and setup share one fake."""
    return patch(_SOURCE, return_value=source)


async def _submit(
    hass: HomeAssistant,
    flow_id: str,
    stop_code: str,
    line_number: str,
    *,
    options: bool = False,
) -> dict[str, object]:
    """Submit one user or options step."""
    manager = hass.config_entries.options if options else hass.config_entries.flow
    return await manager.async_configure(
        flow_id,
        {CONF_STOP_CODE: stop_code, CONF_LINE_NUMBER: line_number},
    )


def _assert_form_schema_serializes(result: dict[str, object]) -> None:
    """Serialize a shown form the way the frontend loader does.

    ``helpers/data_entry_flow.py`` converts ``data_schema`` with
    ``voluptuous_serialize.convert(..., custom_serializer=cv.custom_serializer)``
    before the form is sent. A bare validator such as ``_digits`` raises here,
    which is the add-integration 500.
    """
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    try:
        serialized = voluptuous_serialize.convert(
            schema, custom_serializer=cv.custom_serializer
        )
    except (TypeError, ValueError) as err:
        pytest.fail(
            "form data_schema is not serializable "
            f"({type(err).__name__}: {err}); schema={schema.schema}"
        )
    assert isinstance(serialized, list)
    assert {field["name"] for field in serialized} == {
        CONF_STOP_CODE,
        CONF_LINE_NUMBER,
    }
    for field in serialized:
        assert field["required"] is True
        assert field["selector"]["text"]["type"] == "text"


def _schema_defaults(schema: vol.Schema) -> dict[str, object]:
    """Return default values declared on a flow schema."""
    defaults: dict[str, object] = {}
    for marker in schema.schema:
        if not isinstance(marker, vol.Marker):
            continue
        factory = getattr(marker, "default", None)
        if not callable(factory):
            continue
        value = factory()
        if value is vol.UNDEFINED:
            continue
        defaults[str(marker.schema)] = value
    return defaults


async def _create_entry(
    hass: HomeAssistant, source: FakeSource, stop_code: str, line_number: str
):
    """Run the user flow and return the created config entry."""
    start = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert start["type"] is FlowResultType.FORM
    result = await _submit(hass, start["flow_id"], stop_code, line_number)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def test_user_flow_stop_and_line_creates_one_device_per_stop(
    hass: HomeAssistant,
) -> None:
    """Two stops and line 249 create one device identifier per stop."""
    source = FakeSource(
        {
            "25629": _snapshot("stop_25629_no_249.json", "25629"),
            "20112": _snapshot("stop_20112_has_249.json", "20112"),
        },
        served={("15", "249")},
    )

    with _patch(source):
        gan_hair = await _create_entry(hass, source, "25629", "249")
        glilot = await _create_entry(hass, source, "20112", "249")

    assert gan_hair.data == {
        CONF_STOP_CODE: "25629",
        CONF_LINE_NUMBER: "249",
        CONF_OPERATOR_ID: "15",
        CONF_ROUTE_ID: "",
        CONF_STOP_NAME: "כיכר רבין/מלכי ישראל",
    }
    assert glilot.data == {
        CONF_STOP_CODE: "20112",
        CONF_LINE_NUMBER: "249",
        CONF_OPERATOR_ID: "15",
        CONF_ROUTE_ID: "10119",
        CONF_STOP_NAME: "מחלף גלילות/דרך נמיר",
    }
    assert gan_hair.unique_id == "25629_249_15"
    assert glilot.unique_id == "20112_249_15"
    assert gan_hair.title == "249 כיכר רבין/מלכי ישראל (25629)"
    assert glilot.title == "249 מחלף גלילות/דרך נמיר (20112)"
    # Validation fetch plus one coordinator refresh, and no second refresh.
    assert source.stop_calls == ["25629", "25629", "20112", "20112"]
    # 20112 already has a visit, so only the empty window asks Metropoline.
    assert source.line_calls == [("15", "249")]
    assert hass.data[DOMAIN]["coordinators"]["25629"].subscribers == 1
    assert hass.data[DOMAIN]["coordinators"]["20112"].subscribers == 1

    device_registry = dr.async_get(hass)
    identifiers = set()
    for entry in (gan_hair, glilot):
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        assert len(devices) == 1
        identifiers.add(next(iter(devices[0].identifiers)))
    assert identifiers == {(DOMAIN, "25629"), (DOMAIN, "20112")}


async def test_config_flow_rejects_unknown_stop(hass: HomeAssistant) -> None:
    """A curlbus errors list is the invalid_stop form error."""
    source = FakeSource({"99999999": StopNotFoundError("Invalid stop code 99999999")})

    with _patch(source):
        start = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await _submit(hass, start["flow_id"], "99999999", "249")
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_stop"}
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert source.stop_calls == ["99999999"]
    assert source.line_calls == []


@pytest.mark.parametrize(
    "error",
    [SourceUnavailableError("curlbus down"), BadResponseError("not json")],
)
async def test_config_flow_reports_cannot_connect(
    hass: HomeAssistant, error: Exception
) -> None:
    """Connection failures and bad bodies are cannot_connect."""
    source = FakeSource({"20112": error})

    with _patch(source):
        start = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await _submit(hass, start["flow_id"], "20112", "249")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_config_flow_accepts_metropoline_line_when_no_visit(
    hass: HomeAssistant,
) -> None:
    """A Metropoline line with no current visit is stored with an empty route."""
    source = FakeSource(
        {"25629": _snapshot("stop_25629_no_249.json", "25629")},
        served={("15", "249")},
    )

    with _patch(source):
        entry = await _create_entry(hass, source, "25629", "249")

    assert entry.data[CONF_OPERATOR_ID] == "15"
    assert entry.data[CONF_ROUTE_ID] == ""
    assert entry.data[CONF_LINE_NUMBER] == "249"
    assert source.line_calls == [("15", "249")]


async def test_config_flow_rejects_line_not_found(hass: HomeAssistant) -> None:
    """A line neither visiting nor published by Metropoline is rejected."""
    source = FakeSource({"25629": _snapshot("stop_25629_no_249.json", "25629")})

    with _patch(source):
        start = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await _submit(hass, start["flow_id"], "25629", "249")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "line_not_found"}
    assert source.line_calls == [("15", "249")]
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_config_flow_rejects_ambiguous_line(hass: HomeAssistant) -> None:
    """Several operators and no Metropoline stop the flow."""
    source = FakeSource(
        {"90002": _snapshot("ambiguous_line_249.json", "90002")},
        served={("15", "249")},
    )

    with _patch(source):
        start = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await _submit(hass, start["flow_id"], "90002", "249")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "ambiguous_line"}
    assert source.line_calls == []
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_config_flow_aborts_when_already_configured(
    hass: HomeAssistant,
) -> None:
    """A second entry for the same stop, line, and operator aborts."""
    source = FakeSource(
        {"20112": _snapshot("stop_20112_has_249.json", "20112")},
    )

    with _patch(source):
        first = await _create_entry(hass, source, "20112", "249")
        start = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await _submit(hass, start["flow_id"], "20112", "249")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [first]


async def test_options_flow_changes_stop_and_line(hass: HomeAssistant) -> None:
    """Configure validates the new pair, keeps the entry, and retargets the sensor."""
    source = FakeSource(
        {
            "20112": _snapshot("stop_20112_has_249.json", "20112"),
            "25629": _snapshot("stop_25629_no_249.json", "25629"),
        },
        served={("15", "249")},
    )
    old_unique_id = arrival_unique_id("20112", "249", "15")
    new_unique_id = arrival_unique_id("25629", "249", "15")

    with _patch(source):
        entry = await _create_entry(hass, source, "20112", "249")
        calls_before = len(source.stop_calls)
        line_calls_before = len(source.line_calls)

        start = await hass.config_entries.options.async_init(entry.entry_id)
        assert start["type"] is FlowResultType.FORM
        assert start["step_id"] == "init"
        assert _schema_defaults(start["data_schema"]) == {
            CONF_STOP_CODE: "20112",
            CONF_LINE_NUMBER: "249",
        }

        result = await _submit(hass, start["flow_id"], "25629", "249", options=True)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data == {
        CONF_STOP_CODE: "25629",
        CONF_LINE_NUMBER: "249",
        CONF_OPERATOR_ID: "15",
        CONF_ROUTE_ID: "",
        CONF_STOP_NAME: "כיכר רבין/מלכי ישראל",
    }
    assert entry.unique_id == new_unique_id
    assert entry.title == "249 כיכר רבין/מלכי ישראל (25629)"
    # The new stop was fetched for validation and again for the reloaded sensor.
    assert source.stop_calls[calls_before:] == ["25629", "25629"]
    assert source.line_calls[line_calls_before:] == [("15", "249")]
    assert "20112" not in hass.data[DOMAIN]["coordinators"]
    assert hass.data[DOMAIN]["coordinators"]["25629"].subscribers == 1

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert [item.unique_id for item in entities] == [new_unique_id]
    assert registry.async_get_entity_id("sensor", DOMAIN, old_unique_id) is None
    assert registry.async_get_entity_id("sensor", DOMAIN, new_unique_id) is not None

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, "25629")}
    assert devices[0].name == "כיכר רבין/מלכי ישראל"

    state = hass.states.get(entities[0].entity_id)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("stop_code", "line_number"),
    [
        ("abc", "249"),
        ("20112", "24a"),
        ("", "249"),
        ("   ", "249"),
        ("20112", ""),
    ],
)
async def test_config_flow_rejects_non_digits(
    hass: HomeAssistant, stop_code: str, line_number: str
) -> None:
    """Non-digits stay on the form as invalid_format and do not call the source."""
    source = FakeSource({})

    with _patch(source):
        start = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await _submit(hass, start["flow_id"], stop_code, line_number)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_format"}
    assert _schema_defaults(result["data_schema"]) == {
        CONF_STOP_CODE: stop_code.strip(),
        CONF_LINE_NUMBER: line_number.strip(),
    }
    _assert_form_schema_serializes(result)
    assert source.stop_calls == []
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_config_flow_strips_surrounding_spaces(hass: HomeAssistant) -> None:
    """Spaces around a stop code and line number are stored without the spaces."""
    source = FakeSource({"20112": _snapshot("stop_20112_has_249.json", "20112")})

    with _patch(source):
        entry = await _create_entry(hass, source, " 20112 ", " 249 ")

    assert entry.data[CONF_STOP_CODE] == "20112"
    assert entry.data[CONF_LINE_NUMBER] == "249"
    assert entry.unique_id == "20112_249_15"
    assert source.stop_calls == ["20112", "20112"]


async def test_options_flow_rejects_non_digits(hass: HomeAssistant) -> None:
    """Configure rejects a non-digit value and leaves the entry unchanged."""
    source = FakeSource({"20112": _snapshot("stop_20112_has_249.json", "20112")})

    with _patch(source):
        entry = await _create_entry(hass, source, "20112", "249")
        original = dict(entry.data)
        calls_before = list(source.stop_calls)
        start = await hass.config_entries.options.async_init(entry.entry_id)
        result = await _submit(hass, start["flow_id"], " 24a ", "249", options=True)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_format"}
    assert _schema_defaults(result["data_schema"]) == {
        CONF_STOP_CODE: "24a",
        CONF_LINE_NUMBER: "249",
    }
    _assert_form_schema_serializes(result)
    assert dict(entry.data) == original
    assert source.stop_calls == calls_before


async def test_options_flow_strips_surrounding_spaces(hass: HomeAssistant) -> None:
    """Configure stores a stop code and line number without surrounding spaces."""
    source = FakeSource(
        {
            "20112": _snapshot("stop_20112_has_249.json", "20112"),
            "25629": _snapshot("stop_25629_no_249.json", "25629"),
        },
        served={("15", "249")},
    )

    with _patch(source):
        entry = await _create_entry(hass, source, "20112", "249")
        start = await hass.config_entries.options.async_init(entry.entry_id)
        result = await _submit(hass, start["flow_id"], " 25629 ", " 249 ", options=True)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_STOP_CODE] == "25629"
    assert entry.data[CONF_LINE_NUMBER] == "249"
    assert entry.unique_id == arrival_unique_id("25629", "249", "15")


async def test_every_shown_form_schema_serializes(hass: HomeAssistant) -> None:
    """User and options forms, including a redisplay, must serialize."""
    source = FakeSource(
        {
            "20112": _snapshot("stop_20112_has_249.json", "20112"),
            "99999999": StopNotFoundError("Invalid stop code 99999999"),
        }
    )

    with _patch(source):
        user = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        _assert_form_schema_serializes(user)

        rejected = await _submit(hass, user["flow_id"], "99999999", "249")
        _assert_form_schema_serializes(rejected)

        entry = await _create_entry(hass, source, "20112", "249")
        options = await hass.config_entries.options.async_init(entry.entry_id)
        _assert_form_schema_serializes(options)

        options_rejected = await _submit(
            hass, options["flow_id"], "99999999", "249", options=True
        )
        _assert_form_schema_serializes(options_rejected)


def test_config_flow_and_sensor_do_not_import_curlbus() -> None:
    """Sensors and the config flow call the factory without importing curlbus."""
    root = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "public_transport_il"
    )
    for name in ("config_flow.py", "sensor.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "import curlbus" not in text
        assert "from .curlbus" not in text
