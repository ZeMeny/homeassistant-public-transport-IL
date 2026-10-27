"""One 60-second coordinator per stop, shared by every line at that stop."""

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .source import (
    Arrival,
    ArrivalSource,
    BadResponseError,
    SourceUnavailableError,
    StopNotFoundError,
    StopSnapshot,
)

_LOGGER = logging.getLogger(__name__)
UPDATE_INTERVAL = timedelta(seconds=60)
_METROPOLINE_OPERATOR = "15"


class PublicTransportCoordinator(DataUpdateCoordinator[StopSnapshot]):
    """Poll one stop at most once per minute."""

    def __init__(
        self,
        hass: HomeAssistant,
        source: ArrivalSource,
        stop_code: str,
    ) -> None:
        """Initialize a coordinator for ``stop_code``."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=f"{DOMAIN} {stop_code}",
            update_interval=UPDATE_INTERVAL,
        )
        self.source = source
        self.stop_code = stop_code

    async def _async_update_data(self) -> StopSnapshot:
        """Fetch the stop snapshot.

        A source outage, a bad body, and a curlbus ``errors`` list become
        ``UpdateFailed``. A payload that simply lacks the configured line is
        still a successful snapshot.
        """
        try:
            return await self.source.async_get_stop(self.stop_code)
        except (SourceUnavailableError, BadResponseError, StopNotFoundError) as err:
            raise UpdateFailed(str(err)) from err


@dataclass
class _StopEntry:
    """Coordinator plus the number of entries sharing that stop."""

    coordinator: PublicTransportCoordinator
    subscribers: int
    listener_removals: list[CALLBACK_TYPE]


def _registry(hass: HomeAssistant) -> dict[str, _StopEntry]:
    """Return the per-stop coordinator registry stored on ``hass.data``."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault("coordinators", {})


@callback
def _ignore_update() -> None:
    """Keep the coordinator scheduled for as long as a subscriber exists."""


async def async_subscribe_stop(
    hass: HomeAssistant,
    stop_code: str,
    source: ArrivalSource,
) -> PublicTransportCoordinator:
    """Return the shared coordinator for ``stop_code``.

    The first subscriber creates it and refreshes once. Another subscriber for
    the same stop reuses it and does not refresh again.
    """
    registry = _registry(hass)
    entry = registry.get(stop_code)
    if entry is None:
        coordinator = PublicTransportCoordinator(hass, source, stop_code)
        await coordinator.async_register_shutdown()
        entry = _StopEntry(
            coordinator=coordinator,
            subscribers=0,
            listener_removals=[],
        )
        registry[stop_code] = entry
        await coordinator.async_refresh()
    else:
        coordinator = entry.coordinator

    entry.subscribers += 1
    entry.listener_removals.append(coordinator.async_add_listener(_ignore_update))
    return coordinator


async def async_unsubscribe_stop(hass: HomeAssistant, stop_code: str) -> None:
    """Release one subscriber. Drop the registry entry when none remain."""
    registry = _registry(hass)
    entry = registry[stop_code]
    entry.listener_removals.pop()()
    entry.subscribers -= 1
    if entry.subscribers > 0:
        return
    await entry.coordinator.async_shutdown()
    del registry[stop_code]


def select_arrivals(
    snapshot: StopSnapshot,
    line_number: str,
    operator_id: str | None,
    route_id: str | None,
) -> tuple[Arrival, ...]:
    """Return the visits that belong to one configured line.

    Match stored route id first when that route is in the payload. Otherwise
    match the stored operator plus the line name, and adopt a single replacement
    route id. With no stored operator, prefer operator 15; if it is absent and
    exactly one other operator publishes the line, use that operator. Several
    other operators, or several route ids for the chosen operator, publish
    nothing until the data is unambiguous.

    An empty tuple is a successful selection. This function does not log.
    """
    line = str(line_number)
    if route_id:
        by_route = tuple(
            item for item in snapshot.arrivals if item.route_id == route_id
        )
        if by_route:
            return by_route

    if operator_id:
        return _single_route(
            tuple(
                item
                for item in snapshot.arrivals
                if item.operator_id == operator_id and item.line_name == line
            )
        )

    by_line = tuple(item for item in snapshot.arrivals if item.line_name == line)
    operators = {item.operator_id for item in by_line}
    if not operators:
        return ()
    if _METROPOLINE_OPERATOR in operators:
        chosen = _METROPOLINE_OPERATOR
    elif len(operators) == 1:
        chosen = next(iter(operators))
    else:
        return ()
    return _single_route(tuple(item for item in by_line if item.operator_id == chosen))


def _single_route(arrivals: tuple[Arrival, ...]) -> tuple[Arrival, ...]:
    """Return ``arrivals`` when they share one route id, otherwise nothing."""
    if len({item.route_id for item in arrivals}) == 1:
        return arrivals
    return ()
