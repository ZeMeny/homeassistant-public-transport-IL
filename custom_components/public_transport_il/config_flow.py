"""Config and options flows for a stop code and a line number."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from . import source as arrival_source
from .const import (
    CONF_LINE_NUMBER,
    CONF_OPERATOR_ID,
    CONF_ROUTE_ID,
    CONF_STOP_CODE,
    CONF_STOP_NAME,
    DOMAIN,
    METROPOLINE_OPERATOR_ID,
    arrival_unique_id,
)
from .source import (
    Arrival,
    BadResponseError,
    SourceUnavailableError,
    StopNotFoundError,
    StopSnapshot,
)


class _FormError(Exception):
    """A validation failure the form can show."""

    def __init__(self, key: str) -> None:
        """Store the strings.json error key."""
        super().__init__(key)
        self.key = key


def _digits(value: Any) -> str:
    """Accept a non-empty digit string and reject everything else."""
    if not isinstance(value, str):
        raise vol.Invalid("must be digits")
    text = value.strip()
    if not text.isdigit():
        raise vol.Invalid("must be digits")
    return text


def _schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """Return the stop and line form, prefilled when editing an entry."""
    defaults = defaults or {}

    def _field(key: str) -> vol.Required:
        if key in defaults:
            return vol.Required(key, default=defaults[key])
        return vol.Required(key)

    return vol.Schema(
        {
            _field(CONF_STOP_CODE): _digits,
            _field(CONF_LINE_NUMBER): _digits,
        }
    )


def _title(data: Mapping[str, str]) -> str:
    """Return the entry title: line, stop name, and stop code."""
    return f"{data[CONF_LINE_NUMBER]} {data[CONF_STOP_NAME]} ({data[CONF_STOP_CODE]})"


def _route_id_for(arrivals: tuple[Arrival, ...], operator_id: str) -> str:
    """Return the only route id for this operator, or an empty string."""
    route_ids = {
        item.route_id
        for item in arrivals
        if item.operator_id == operator_id and item.route_id
    }
    if len(route_ids) == 1:
        return next(iter(route_ids))
    return ""


def _choose_operator(arrivals: tuple[Arrival, ...]) -> str | None:
    """Prefer Metropoline. A single other operator is usable. Several are not."""
    operators = {item.operator_id for item in arrivals}
    if METROPOLINE_OPERATOR_ID in operators:
        return METROPOLINE_OPERATOR_ID
    if len(operators) == 1:
        return next(iter(operators))
    return None


async def async_validate_stop_and_line(
    source: arrival_source.ArrivalSource,
    stop_code: str,
    line_number: str,
) -> dict[str, str]:
    """Validate one stop and line and return the data to store on the entry.

    curlbus ``errors`` become ``invalid_stop``. Connection and bad-body
    failures become ``cannot_connect``. A line that is absent, and that
    Metropoline does not publish, is ``line_not_found``. Several operators
    without Metropoline are ``ambiguous_line``.
    """
    if not stop_code.isdigit() or not line_number.isdigit():
        raise _FormError("invalid_format")

    try:
        snapshot = await source.async_get_stop(stop_code)
    except StopNotFoundError as err:
        raise _FormError("invalid_stop") from err
    except (SourceUnavailableError, BadResponseError) as err:
        raise _FormError("cannot_connect") from err

    return await _data_from_snapshot(source, snapshot, stop_code, line_number)


async def _data_from_snapshot(
    source: arrival_source.ArrivalSource,
    snapshot: StopSnapshot,
    stop_code: str,
    line_number: str,
) -> dict[str, str]:
    """Resolve operator and route from one successful snapshot."""
    matched = tuple(item for item in snapshot.arrivals if item.line_name == line_number)
    if not matched:
        operator_id = METROPOLINE_OPERATOR_ID
        route_id = ""
        try:
            serves = await source.async_operator_serves_line(operator_id, line_number)
        except StopNotFoundError as err:
            raise _FormError("line_not_found") from err
        except (SourceUnavailableError, BadResponseError) as err:
            raise _FormError("cannot_connect") from err
        if not serves:
            raise _FormError("line_not_found")
    else:
        operator_id = _choose_operator(matched)
        if operator_id is None:
            raise _FormError("ambiguous_line")
        route_id = _route_id_for(matched, operator_id)

    return {
        CONF_STOP_CODE: stop_code,
        CONF_LINE_NUMBER: line_number,
        CONF_OPERATOR_ID: operator_id,
        CONF_ROUTE_ID: route_id,
        CONF_STOP_NAME: snapshot.stop_name,
    }


class PublicTransportILConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for one stop and one line."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a stop code and a line number."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await async_validate_stop_and_line(
                    arrival_source.async_get_source(self.hass),
                    user_input[CONF_STOP_CODE],
                    user_input[CONF_LINE_NUMBER],
                )
            except _FormError as err:
                errors["base"] = err.key
            else:
                await self.async_set_unique_id(
                    arrival_unique_id(
                        data[CONF_STOP_CODE],
                        data[CONF_LINE_NUMBER],
                        data[CONF_OPERATOR_ID],
                    )
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=_title(data), data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow used by Configure."""
        return PublicTransportILOptionsFlow()


class PublicTransportILOptionsFlow(OptionsFlow):
    """Change the stop code and line number of an existing entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the same two fields, prefilled from the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await async_validate_stop_and_line(
                    arrival_source.async_get_source(self.hass),
                    user_input[CONF_STOP_CODE],
                    user_input[CONF_LINE_NUMBER],
                )
            except _FormError as err:
                errors["base"] = err.key
            else:
                unique_id = arrival_unique_id(
                    data[CONF_STOP_CODE],
                    data[CONF_LINE_NUMBER],
                    data[CONF_OPERATOR_ID],
                )
                existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, unique_id
                )
                if (
                    existing is not None
                    and existing.entry_id != self.config_entry.entry_id
                ):
                    return self.async_abort(reason="already_configured")
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=data,
                    title=_title(data),
                    unique_id=unique_id,
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                # Options-flow completion stores this payload on entry.options.
                # The stop and line live in entry.data, updated above.
                return self.async_create_entry(data={})

        defaults = dict(self.config_entry.data)
        if user_input is not None:
            defaults.update(user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults),
            errors=errors,
        )
