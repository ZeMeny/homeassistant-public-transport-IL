"""Sensor for the minutes until the next arrival of one line at one stop."""

import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import PublicTransportConfigEntry
from .const import (
    CONF_LINE_NUMBER,
    CONF_OPERATOR_ID,
    CONF_ROUTE_ID,
    CONF_STOP_CODE,
    CONF_STOP_NAME,
    DOMAIN,
    arrival_unique_id,
)
from .coordinator import PublicTransportCoordinator, select_arrivals
from .source import Arrival

# Visits older than this are no longer "the next bus".
_STALE_AFTER = timedelta(seconds=30)
_ATTRIBUTE_LIMIT = 3


def _minutes_until(eta: datetime, now: datetime) -> int | None:
    """Return whole minutes until ``eta``, or None when it is too far past.

    The value is the floor of the remaining seconds divided by 60, so a bus
    due in 50 seconds is 0. A visit more than 30 seconds in the past is dropped.
    """
    remaining = (eta - now).total_seconds()
    if remaining < -_STALE_AFTER.total_seconds():
        return None
    return math.floor(remaining / 60)


def _async_retarget_unique_id(
    hass: HomeAssistant, entry: PublicTransportConfigEntry
) -> None:
    """Keep the existing entity when Configure changes its unique id."""
    new_unique_id = arrival_unique_id(
        entry.data[CONF_STOP_CODE],
        entry.data[CONF_LINE_NUMBER],
        entry.data[CONF_OPERATOR_ID],
    )
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.unique_id == new_unique_id:
            continue
        registry.async_update_entity(
            entity_entry.entity_id, new_unique_id=new_unique_id
        )


def _async_drop_stale_stop_devices(
    hass: HomeAssistant, entry: PublicTransportConfigEntry
) -> None:
    """Drop devices for a stop this entry no longer uses.

    Two lines at one stop share a device, so only this entry is detached.
    A device that no longer has an entry is removed.
    """
    current = {(DOMAIN, str(entry.data[CONF_STOP_CODE]))}
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if current.issubset(device.identifiers):
            continue
        device_registry.async_update_device(
            device.id, remove_config_entry_id=entry.entry_id
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PublicTransportConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensor for this entry, retargeting its unique id first."""
    _async_retarget_unique_id(hass, entry)
    async_add_entities([NextBusSensor(entry.runtime_data, entry)])


class NextBusSensor(CoordinatorEntity[PublicTransportCoordinator], SensorEntity):
    """Minutes until the next selected arrival."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:bus"

    def __init__(
        self,
        coordinator: PublicTransportCoordinator,
        entry: PublicTransportConfigEntry,
    ) -> None:
        """Attach one config entry to the shared stop coordinator."""
        super().__init__(coordinator)
        self._entry = entry
        data = entry.data
        stop_code = str(data[CONF_STOP_CODE])
        self._line_number = str(data[CONF_LINE_NUMBER])
        self._operator_id = str(data[CONF_OPERATOR_ID])
        self._route_id = str(data[CONF_ROUTE_ID])
        self._attr_unique_id = arrival_unique_id(
            stop_code, self._line_number, self._operator_id
        )
        # The device is the stop. The entity name is the line number there.
        self._attr_name = self._line_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_code)},
            name=str(data[CONF_STOP_NAME]),
        )

    async def async_added_to_hass(self) -> None:
        """Detach a device left behind when the stop code changed."""
        await super().async_added_to_hass()
        _async_drop_stale_stop_devices(self.hass, self._entry)

    @property
    def native_value(self) -> int | None:
        """Return minutes until the next arrival, or None when none is listed."""
        upcoming = self._upcoming()
        if not upcoming:
            return None
        return upcoming[0][0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the next arrivals plus route, operator, and snapshot time."""
        snapshot = self.coordinator.data
        upcoming = self._upcoming()
        if upcoming:
            route_id = upcoming[0][1].route_id
            operator = upcoming[0][1].operator_name
        else:
            route_id = self._route_id
            operator = self._operator_id
        last_update = None
        if snapshot is not None:
            last_update = snapshot.timestamp.isoformat()
        return {
            "arrivals": [
                {
                    "eta": arrival.eta.isoformat(),
                    "minutes": minutes,
                    "headsign": arrival.headsign,
                    "live": arrival.live,
                }
                for minutes, arrival in upcoming[:_ATTRIBUTE_LIMIT]
            ],
            "route_id": route_id,
            "operator": operator,
            "last_update": last_update,
        }

    def _upcoming(self) -> list[tuple[int, Arrival]]:
        """Return upcoming visits as ``(minutes, arrival)``, soonest first."""
        snapshot = self.coordinator.data
        if snapshot is None:
            return []
        selected = select_arrivals(
            snapshot,
            self._line_number,
            self._operator_id,
            self._route_id or None,
        )
        now = dt_util.utcnow()
        ranked: list[tuple[datetime, int, Arrival]] = []
        for arrival in selected:
            minutes = _minutes_until(arrival.eta, now)
            if minutes is None:
                continue
            ranked.append((arrival.eta, minutes, arrival))
        ranked.sort(key=lambda item: item[0])
        return [(minutes, arrival) for _, minutes, arrival in ranked]
