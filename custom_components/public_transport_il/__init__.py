"""The Public Transport IL integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import source as arrival_source
from .const import CONF_STOP_CODE, DOMAIN
from .coordinator import (
    PublicTransportCoordinator,
    async_subscribe_stop,
    async_unsubscribe_stop,
)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [Platform.SENSOR]

type PublicTransportConfigEntry = ConfigEntry[PublicTransportCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Public Transport IL component."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: PublicTransportConfigEntry
) -> bool:
    """Subscribe to the shared stop coordinator and forward the sensor.

    The subscription refreshes once for the first entry at this stop and does
    not refresh again when another line at the same stop is added.
    """
    stop_code = str(entry.data[CONF_STOP_CODE])
    coordinator = await async_subscribe_stop(
        hass,
        stop_code,
        arrival_source.async_get_source(hass),
    )
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await async_unsubscribe_stop(hass, coordinator.stop_code)
        raise
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PublicTransportConfigEntry
) -> bool:
    """Unload the sensor and release this entry's coordinator subscription.

    The coordinator object still carries the stop code it was created for, so
    a reload that already replaced ``entry.data`` unsubscribes the old stop.
    """
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await async_unsubscribe_stop(hass, entry.runtime_data.stop_code)
    return True
