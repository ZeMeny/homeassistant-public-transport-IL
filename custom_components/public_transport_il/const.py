"""Constants for the Public Transport IL integration."""

DOMAIN = "public_transport_il"

CONF_STOP_CODE = "stop_code"
CONF_LINE_NUMBER = "line_number"
CONF_OPERATOR_ID = "operator_id"
CONF_ROUTE_ID = "route_id"
CONF_STOP_NAME = "stop_name"

# Metropoline agency id on the Israeli GTFS / SIRI feed.
METROPOLINE_OPERATOR_ID = "15"


def arrival_unique_id(stop_code: str, line_number: str, operator_id: str) -> str:
    """Return the id shared by a config entry and its sensor."""
    return f"{stop_code}_{line_number}_{operator_id}"
