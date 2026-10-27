"""Arrival-source interface shared by the parser, client, and coordinator.

Sensors and the config flow depend on these types and on ``async_get_source``.
They do not import the curlbus module.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from homeassistant.core import HomeAssistant


class SourceError(Exception):
    """Base class for arrival-source failures."""


class StopNotFoundError(SourceError):
    """The stop code is unknown, or curlbus returned an errors list."""


class SourceUnavailableError(SourceError):
    """The source could not be reached."""


class BadResponseError(SourceError):
    """The source returned a body that is not a usable stop payload."""


@dataclass(frozen=True, slots=True)
class Arrival:
    """One visit at a stop."""

    route_id: str
    line_name: str
    operator_id: str
    operator_name: str
    headsign: str
    eta: datetime
    live: bool
    destination_stop_code: str


@dataclass(frozen=True, slots=True)
class StopSnapshot:
    """Arrivals for one stop from a single successful poll."""

    stop_code: str
    stop_name: str
    timestamp: datetime
    arrivals: tuple[Arrival, ...]


class ArrivalSource(Protocol):
    """Swappable source of stop arrivals.

    ``async_get_source`` delegates to the only constructor of the concrete
    client. A future SIRI client replaces that factory's return value.
    """

    async def async_get_stop(self, stop_code: str) -> StopSnapshot:
        """Return the current snapshot for ``stop_code``."""

    async def async_operator_serves_line(
        self, operator_id: str, line_number: str
    ) -> bool:
        """Return whether ``operator_id`` publishes ``line_number``."""


def async_get_source(hass: HomeAssistant) -> ArrivalSource:
    """Return the arrival source used by setup and the config flow.

    The curlbus module remains the only place that constructs the concrete
    client. This wrapper exists so callers do not import that module.
    """
    from .curlbus import async_get_source as curlbus_async_get_source

    return curlbus_async_get_source(hass)
