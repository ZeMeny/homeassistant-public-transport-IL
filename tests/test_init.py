"""Test component setup."""

import pytest
from homeassistant.setup import async_setup_component

from custom_components.public_transport_il.const import DOMAIN


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
