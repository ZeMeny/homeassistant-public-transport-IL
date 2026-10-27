---
name: ha-custom-integration
description: Checklist for building or reviewing a Home Assistant custom integration (custom component) that is HACS-installable. Use when creating, restructuring, or debugging files under custom_components/.
---
# Home Assistant custom integration checklist

## Layout (HACS)
```
hacs.json                         # repo root: {"name": "...", "render_readme": true}
custom_components/<domain>/
  __init__.py  manifest.json  config_flow.py  const.py
  coordinator.py  sensor.py  strings.json  translations/en.json
tests/
```
Exactly one integration folder under `custom_components/`.

## Rules
- `domain`: lowercase, underscores only; must equal the folder name and `manifest.json` `domain`.
- `manifest.json` needs: domain, name, version (custom integrations), codeowners, config_flow: true, documentation, issue_tracker, iot_class (e.g. `cloud_polling`), requirements.
- Config via UI: `config_flow.py` with `ConfigFlow`, validate input by calling the API, set a unique_id to prevent duplicates. No YAML-only setup.
- `__init__.py`: `async_setup_entry` creates the coordinator, calls `async_config_entry_first_refresh()`, forwards platforms; implement `async_unload_entry`.
- Polling via `DataUpdateCoordinator` with an explicit `update_interval`; raise `UpdateFailed` on errors.
- All I/O async: use `aiohttp` through `async_get_clientsession(hass)`; never `requests` or blocking calls in the event loop (wrap unavoidable ones in `hass.async_add_executor_job`).
- Entities: subclass `CoordinatorEntity` + `SensorEntity`, set `unique_id`, `_attr_has_entity_name = True`, device_class/unit where applicable; extra data in `extra_state_attributes`.
- Never import AppDaemon `hassapi` in an integration.

## Tests
- `pytest-homeassistant-custom-component`; test config flow (success, invalid input, duplicate) and coordinator/sensor with mocked API responses.
- CI: `hassfest` and `hacs/action` validation workflows.
