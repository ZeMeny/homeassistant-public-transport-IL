"""Pure parser from a curlbus JSON object to a stop snapshot."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .source import Arrival, BadResponseError, StopNotFoundError, StopSnapshot

_JERUSALEM = ZoneInfo("Asia/Jerusalem")
_LIVE_PRODUCERS = frozenset({"SIRI", "GTFS-RT"})


def parse_stop_payload(payload: Any, *, stop_code: str | None = None) -> StopSnapshot:
    """Parse one curlbus stop response.

    An explicit ETA offset is kept as-is. A naive ETA is interpreted as
    Asia/Jerusalem. A visit with an unparseable ETA is skipped. A payload
    that is not a JSON object raises ``BadResponseError``. A non-empty
    ``errors`` list raises ``StopNotFoundError``.
    """
    if not isinstance(payload, dict):
        raise BadResponseError("curlbus payload is not a JSON object")

    _raise_for_errors(payload)
    timestamp = _require_timestamp(payload.get("timestamp"))
    resolved_stop, visits = _visits_for_stop(payload.get("visits"), stop_code)
    arrivals = tuple(
        arrival
        for visit in visits
        if isinstance(visit, dict) and (arrival := _parse_visit(visit)) is not None
    )
    return StopSnapshot(
        stop_code=resolved_stop,
        stop_name=_stop_name(payload.get("stop_info")),
        timestamp=timestamp,
        arrivals=arrivals,
    )


def _raise_for_errors(payload: dict[str, Any]) -> None:
    """Raise when curlbus reported an errors list or other error value."""
    errors = payload.get("errors")
    if not errors:
        return
    if isinstance(errors, list):
        message = "; ".join(str(item).strip() for item in errors if str(item).strip())
    else:
        message = str(errors).strip()
    raise StopNotFoundError(message or "curlbus reported an error for this stop")


def _require_timestamp(value: Any) -> datetime:
    """Return the response timestamp, which is always timezone-aware."""
    parsed = _parse_datetime(value)
    if parsed is None:
        raise BadResponseError("curlbus timestamp is missing or invalid")
    return parsed


def _visits_for_stop(visits: Any, stop_code: str | None) -> tuple[str, list[Any]]:
    """Return the stop code and the visit list for that stop."""
    if not isinstance(visits, dict):
        raise BadResponseError("curlbus visits field is missing")

    resolved = stop_code
    if resolved is None:
        if len(visits) != 1:
            raise BadResponseError("curlbus payload did not identify a stop")
        resolved = str(next(iter(visits)))

    visit_list = visits.get(resolved, [])
    if not isinstance(visit_list, list):
        raise BadResponseError("curlbus visits for the stop are not a list")
    return resolved, visit_list


def _parse_visit(visit: dict[str, Any]) -> Arrival | None:
    """Parse one visit, or return None when its ETA cannot be used."""
    eta = _parse_datetime(visit.get("eta"))
    if eta is None:
        return None

    operator_id = _as_text(visit.get("operator_id"))
    # English agency name only; the operator id is the fallback below.
    operator_name = _localized(
        _dig(visit, "static_info", "route", "agency", "name"), "EN"
    )
    headsign = _localized(_dig(visit, "static_info", "route", "headsign"), "HE", "EN")
    return Arrival(
        route_id=_as_text(visit.get("route_id")),
        line_name=_as_text(visit.get("line_name")),
        operator_id=operator_id,
        operator_name=operator_name or operator_id,
        headsign=headsign or "",
        eta=eta,
        live=_as_text(visit.get("producer")) in _LIVE_PRODUCERS,
        destination_stop_code=_as_text(visit.get("destination_id")),
    )


def _stop_name(stop_info: Any) -> str:
    """Return the Hebrew stop name, falling back to English."""
    if not isinstance(stop_info, dict):
        return ""
    return _localized(stop_info.get("name"), "HE", "EN") or ""


def _parse_datetime(value: Any) -> datetime | None:
    """Parse a curlbus datetime, treating a naive value as Asia/Jerusalem."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=_JERUSALEM)
    return parsed


def _localized(names: Any, *keys: str) -> str | None:
    """Return the first non-empty string among the requested languages."""
    if not isinstance(names, dict):
        return None
    for key in keys:
        value = names.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _dig(obj: Any, *keys: str) -> Any:
    """Walk nested mappings, returning None when a step is missing."""
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_text(value: Any) -> str:
    """Return a field as text, or an empty string when it is missing."""
    if value is None:
        return ""
    return str(value)
