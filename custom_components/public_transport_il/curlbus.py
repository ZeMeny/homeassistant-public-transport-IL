"""curlbus.app client.

``async_get_source`` is the only place that constructs ``CurlbusClient``.
A future SIRI client replaces that factory's return value.
"""

import json
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .parser import parse_stop_payload
from .source import (
    ArrivalSource,
    BadResponseError,
    SourceUnavailableError,
    StopSnapshot,
)

CURLBUS_BASE_URL = "https://curlbus.app"
# Under the coordinator's 60s interval so a black-holed connection fails
# this refresh instead of keeping the previous snapshot for minutes.
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
_ACCEPT_JSON = {"Accept": "application/json"}
_METROPOLINE_OPERATOR = "15"


class CurlbusClient:
    """Fetch stop snapshots and the Metropoline line check from curlbus."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str = CURLBUS_BASE_URL,
    ) -> None:
        """Initialize the client.

        ``session`` is Home Assistant's shared aiohttp session in production.
        ``base_url`` is injectable so tests can point at a fake host.
        """
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def async_get_stop(self, stop_code: str) -> StopSnapshot:
        """Fetch and parse one stop. Performs a single ``GET /{stop_code}``."""
        payload = await self._async_get_json(str(stop_code))
        return parse_stop_payload(payload, stop_code=str(stop_code))

    async def async_operator_serves_line(
        self, operator_id: str, line_number: str
    ) -> bool:
        """Return whether operator 15 publishes ``line_number``.

        The lookup is ``GET /metropoline/{line}``. It is true when
        ``route_alternatives`` contains that ``short_name``. Other operators
        have no curlbus line endpoint in v1 and return False.
        """
        if str(operator_id) != _METROPOLINE_OPERATOR:
            return False

        payload = await self._async_get_json(f"metropoline/{line_number}")
        if not isinstance(payload, dict):
            raise BadResponseError("curlbus route response is not a JSON object")
        alternatives = payload.get("route_alternatives")
        if not isinstance(alternatives, list):
            raise BadResponseError("curlbus route alternatives are missing")
        wanted = str(line_number)
        return any(
            isinstance(item, dict) and str(item.get("short_name")) == wanted
            for item in alternatives
        )

    async def _async_get_json(self, path: str) -> Any:
        """GET one path and decode the body as JSON."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            async with self._session.get(
                url, headers=_ACCEPT_JSON, timeout=REQUEST_TIMEOUT
            ) as response:
                body = await response.text()
                status = response.status
        except TimeoutError as err:
            raise SourceUnavailableError("curlbus request timed out") from err
        except aiohttp.ClientError as err:
            raise SourceUnavailableError(f"curlbus request failed: {err}") from err

        if status >= 500:
            raise SourceUnavailableError(f"curlbus returned HTTP {status}")
        try:
            return json.loads(body)
        except json.JSONDecodeError as err:
            raise BadResponseError("curlbus response is not JSON") from err


def async_get_source(hass: HomeAssistant) -> ArrivalSource:
    """Return the arrival source used by the integration.

    This is the only place that constructs ``CurlbusClient``.
    """
    return CurlbusClient(async_get_clientsession(hass))
