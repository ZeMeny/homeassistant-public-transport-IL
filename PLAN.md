# PLAN: Next-bus sensors for line 249

Status: DRAFT, awaiting human approval (Gate B). No production code until this plan is approved.

Spec: [SPEC.md](SPEC.md) (approved for planning by the planning request; the status line inside SPEC.md still says DRAFT and is left unchanged by this plan).

## Summary

Turn the prototype and the empty Home Assistant skeleton into a HACS-installable custom integration, domain `public_transport_il`, that shows minutes until the next arrival of a configured bus line at a configured stop. The first real setup is Metropoline line 249 at the two stops in the spec (Gan HaIr / Rabin Square stop 25629 toward Glilot, and Glilot stop 20112 toward Gan HaIr). Stop code and line number come from the UI, so other stops and lines can be added later without code changes.

Live data for v1 comes from curlbus.app, polled at most once every 60 seconds per stop, through aiohttp on Home Assistant's shared session. Parsing, the coordinator, the config flow, and the sensors talk to a small arrival-source interface. A later Ministry of Transport SIRI client can replace the curlbus client behind that interface.

This document is the implementation plan. It adds no production code.

## Current code the work starts from

- Root [`__init__.py`](__init__.py) is a standalone script. It calls `requests.get` against `https://curlbus.app/{stop_id}`, imports AppDaemon `hassapi` (unusable in an integration), strips the timezone off each ETA, and matches a line with `str(number) in item`, which also matches other line numbers that contain those digits. For every arrival it issues another HTTP call to resolve the destination stop name. That extra fan-out is not ported.
- [`public_transport_IL/custom_components/public_transport_IL/`](public_transport_IL/custom_components/public_transport_IL/) is a scaffold: `async_setup` returns true, `DOMAIN = "public_transport_IL"`, `config_flow` is false, and `iot_class` is `calculated`. [`public_transport_IL/hacs.json`](public_transport_IL/hacs.json) sits in a subfolder, so HACS cannot use this repository. [`public_transport_IL/requirements.test.txt`](public_transport_IL/requirements.test.txt) contains a stray JSON line and is not a valid requirements file. The pre-commit config targets Python 3.7, Black, and flake8.

curlbus shape, checked once on 2026-10-27 while writing this plan (do not re-fetch from tests):

- `GET https://curlbus.app/{stop_code}` with `Accept: application/json`.
- An unknown stop is HTTP 200 with a body like `{"errors": ["Invalid stop code 99999999\n"]}`. A usable stop has `errors: null`, an offset timestamp, `visits` keyed by the stop code, and `stop_info.name` in HE / EN / AR.
- Each visit carries `line_name`, `route_id`, `operator_id`, `direction_id`, `eta`, `producer`, and `static_info.route` (agency name and headsign). On that date, line 249 at stop 20112 was `operator_id` `"15"` (Metropoline), `route_id` `"10119"`, `producer` `"SIRI"`, headsign Hebrew text under `static_info.route.headsign.HE`. `route_id` is the SIRI `LineRef`, which curlbus treats as the GTFS route id. Stop 25629's payload at the same time had no line 249 at all.
- ETA strings look like `2026-10-27 20:31:00+02:00` (space between date and time, numeric offset). Weekend municipal buses are emitted by curlbus as `producer` `"GTFS-RT"`.
- `GET /metropoline/249` returns `route_alternatives` with `short_name` `"249"` and does not list stops or route ids.
- `direction_id` on this feed is `"1"` or `"2"`. GTFS direction ids for the same routes are `0` / `1`. Matching ignores `direction_id`.

## Approach

One config entry is one stop code plus one line number. Setup creates one sensor for that pair and attaches it to a device identified by the stop code, so two lines at the same stop share a device. All entries for a stop share one `DataUpdateCoordinator` and therefore one HTTP call per 60 seconds.

Matching, in order:

1. If the entry has a stored `route_id` and the payload contains that route id at this stop, use those visits.
2. Otherwise keep visits whose `operator_id` equals the stored operator and whose `line_name` equals the configured line. When that set contains a single `route_id`, adopt it (this is how a GTFS renumber is picked up). When it contains several route ids, keep the stored route id and publish no arrivals until the data is unambiguous.
3. When several operators publish the same line number, prefer operator `15` (Metropoline). When operator 15 is absent and exactly one other operator is present, use that operator so other lines still work. When operator 15 is absent and more than one operator is present, the config and options flows stop with `ambiguous_line`.

A payload that simply does not contain the line is a successful update with an empty arrival list. The sensor state is unknown. The coordinator logs nothing at error level for that case.

A transport failure, a non-JSON body, or a curlbus `errors` list is `UpdateFailed`. Coordinator entities become unavailable and the next successful poll makes them available again. The interval stays 60 seconds.

Minutes are computed in the sensor from timezone-aware ETAs and `homeassistant.util.dt.utcnow`. Visits more than 30 seconds in the past are dropped. The state is the floor of the remaining seconds divided by 60 (so a bus due in 50 seconds is `0`). An empty list after that filter is unknown (`None`), which Home Assistant displays as unknown. The state is an integer, device class duration, unit minutes.

`live` is true when `producer` is `SIRI` or `GTFS-RT`. Any other producer is reported as scheduled. v1 does not invent a timetable row when curlbus lists no visit.

Headsign and the stop name shown on the device use the Hebrew strings curlbus already returns (`static_info.route.headsign.HE`, `stop_info.name.HE`), falling back to English when Hebrew is missing. The operator attribute uses the English agency name, falling back to `operator_id`.

## Work breakdown

Each step is done on its own branch and pull request, in order. The suggested split is the one below: PR 1 is layout and CI, PR 2 is the client and coordinator, PR 3 is the flows, sensors, and README. Landing all of this in one pull request would mix a tree move, a new client, and UI flows, and a failure in any layer would be hard to revert.

### Prerequisites outside the pull requests

Before the HACS description, topics, and license checks can pass, Meny sets these on the GitHub repository. They are his tasks and are outside PR 1, PR 2, and PR 3:

- A repository description.
- Repository topics.
- A `LICENSE` file on the default branch. GitHub reports the license from that branch, so a license that exists only on a pull-request branch does not satisfy the check.

### PR 1 — Restructure and CI

1. **Move the integration to the HACS path and the lowercase domain.**
   - Create `custom_components/public_transport_il/` with `__init__.py`, `const.py`, and `manifest.json`.
   - `DOMAIN = "public_transport_il"`.
   - Manifest: `domain` `public_transport_il`, `name` `Public Transport IL`, `codeowners` `["@ZeMeny"]`, `config_flow` false (no flow module exists yet), `documentation` and `issue_tracker` pointing at this GitHub repository, `iot_class` `cloud_polling`, `requirements` `[]`, `version` `0.1.0`. Omit `integration_type`. `iot_class` is set only in this manifest. Hassfest requires the keys ordered `domain`, `name`, then alphabetical.
   - `async_setup` still returns true, so the package loads before the config flow exists.
   - Add root [`hacs.json`](hacs.json) with the keys the HACS schema accepts: `name` `Public Transport IL`, `render_readme` true, and `homeassistant` `2025.1.4` (the core version installed by `pytest-homeassistant-custom-component==0.13.205` on Python 3.12). The schema rejects `iot_class`, so that key is not part of `hacs.json`.
   - Verify: `python -c "from custom_components.public_transport_il.const import DOMAIN; assert DOMAIN == 'public_transport_il'"`. hassfest in CI accepts the manifest. HACS validation in CI finds `hacs.json` and `custom_components/public_transport_il/`.

2. **Add the test and lint toolchain, and delete the old tree.**
   - Root `requirements_test.txt` lists `pytest`, `pytest-homeassistant-custom-component==0.13.205`, and `ruff`. That plugin release is the newest one that still supports Python 3.12, and it installs Home Assistant 2025.1.4. Newer releases of the plugin require Python 3.13 or 3.14.
   - Root `pyproject.toml` configures Ruff for Python 3.12 (line length 88, lint rules `E`, `F`, `I`, `UP`, `B`, `SIM`) and pytest `testpaths = ["tests"]`.
   - `.github/workflows/ci.yml` runs four jobs on pull requests and on pushes to `main`: `hassfest` (`home-assistant/actions/hassfest`), `hacs` (`hacs/action` with `category: integration` and `ignore: brands`), `ruff` (`ruff check` and `ruff format --check`), and `pytest` (Python 3.12, install `requirements_test.txt`, run `pytest`). `ignore: brands` is temporary. The description, topics, and license checks pass once the prerequisites above are in place.
   - Move the existing setup test to `tests/test_init.py` importing `custom_components.public_transport_il`.
   - Add `tests/test_manifest.py::test_domain_and_hacs_metadata`.
   - Delete the whole `public_transport_IL/` directory, including its `hacs.json`, broken requirements file, `setup.cfg`, Python 3.7 pre-commit config, and uppercase-domain tests.
   - Extend `.gitignore` with `__pycache__/`, `.pytest_cache/`, and `.ruff_cache/`.
   - Update the layout and known-issues sections of `AGENTS.md` so they describe the new tree. Leave the prototype listed until PR 2 deletes it.
   - Leave root `__init__.py` in place. pytest `testpaths` keeps it out of collection.
   - Verify: `ruff check .`, `ruff format --check .`, and `pytest` pass locally. The four CI jobs pass on the pull request.

Follow-up, not part of PR 1, PR 2, or PR 3: add `custom_components/public_transport_il/brand/icon.png`, then remove `ignore: brands` from the HACS job.

### PR 2 — Async client, parser, and coordinator

3. **[x] Record fixtures and add a pure parser.**
   - Commit trimmed JSON fixtures under `tests/fixtures/` (public curlbus data only; no cookies, tokens, or private hostnames). Include a real stop payload that contains Metropoline 249 (`route_id` `10119`, `operator_id` `15`), a real stop payload with no line 249, the invalid-stop `errors` body, plus small synthetic payloads for an ambiguous line 249, a non-`SIRI`/`GTFS-RT` producer, a `+03:00` offset, and a naive ETA.
   - Add `parser.py` with a pure function from the JSON object to a snapshot dataclass: stop code, Hebrew stop name, response timestamp, and arrivals. Each arrival has `route_id`, `line_name`, `operator_id`, operator display name, headsign, aware `eta`, `live`, and destination stop code.
   - Parse ETA with `datetime.fromisoformat`. Keep an explicit offset as-is. Interpret a naive timestamp as `Asia/Jerusalem` via `zoneinfo`. A visit with an unparseable ETA is skipped. A payload that is not a JSON object, or a non-empty `errors` list, raises a typed source error.
   - Verify: `tests/test_parser.py::test_eta_timezone_offsets_and_naive_israel_local`, `tests/test_parser.py::test_missing_line_249_is_empty_success`, `tests/test_parser.py::test_live_flag_follows_producer`, and `tests/test_parser.py::test_invalid_stop_errors_raise`. All read local files.

4. **[x] Put HTTP behind a swappable source interface.**
   - Add `source.py` with the snapshot dataclasses, an `ArrivalSource` protocol (`async_get_stop(stop_code)`, `async_operator_serves_line(operator_id, line_number)`), and typed errors for "stop not found", "source unavailable", and "bad response".
   - Add `curlbus.py` implementing the protocol with the shared `aiohttp` session from `homeassistant.helpers.aiohttp_client.async_get_clientsession`. Base URL is the public curlbus host, injectable so tests can point at a mock. One `GET /{stop_code}` per call, `Accept: application/json`, then the parser. `async_operator_serves_line` for operator `15` performs `GET /metropoline/{line}` and returns whether `route_alternatives` contains that `short_name`. The sensor module imports dataclasses and the coordinator, and does not import `curlbus`.
   - A single factory, `async_get_source(hass)`, is the only place that constructs `CurlbusClient`. A future SIRI client replaces that factory's return value.
   - Verify: `tests/test_client.py::test_fetch_stop_uses_injected_session` asserts the request path and header against a mocked session and a fixture body. `tests/test_client.py::test_metropoline_line_lookup` covers the route-alternatives check. No test opens a connection to curlbus.

5. **Add the 60-second coordinator, shared per stop.**
   - Add `coordinator.py`. `PublicTransportCoordinator` is a `DataUpdateCoordinator` with `update_interval = timedelta(seconds=60)`. `_async_update_data` calls `async_get_stop`. Source-unavailable and bad-response errors become `UpdateFailed`. A stop that previously worked and later returns curlbus `errors` is also `UpdateFailed`.
   - A registry in `hass.data[DOMAIN]["coordinators"]`, keyed by stop code, holds one coordinator plus a subscriber count. The first subscriber creates it and performs the initial refresh. Another subscriber for the same stop reuses it and does not refresh again. The last unsubscribe drops the registry entry so an unused stop is not polled.
   - `select_arrivals(snapshot, line_number, operator_id, route_id)` implements the match order from the Approach section. An empty selection returns an empty tuple and does not log an error.
   - Verify: `tests/test_coordinator.py::test_coordinator_publishes_snapshot`, `tests/test_coordinator.py::test_unreachable_marks_update_failed`, `tests/test_coordinator.py::test_one_poll_per_60s_shared_by_stop` (two subscribers, a counting fake source, `async_fire_time_changed` by 60 seconds, exactly one extra fetch), and `tests/test_coordinator.py::test_missing_line_is_successful_empty_update`.

6. **Delete the prototype once the fixtures and parser cover it.**
   - Delete root `__init__.py`.
   - Remove the prototype from the layout section of `AGENTS.md`.
   - Verify: `pytest` still passes, `rg "hassapi|import requests" custom_components tests` finds nothing, and CI is green.

### PR 3 — Config flow, options flow, sensors, README

7. **Add the config flow.**
   - Add `config_flow.py` and `strings.json` / `translations/en.json`. The user step asks for `stop_code` and `line_number`. Both must be digits.
   - Validation calls the source, not `requests`: the stop must return a snapshot (curlbus `errors` becomes form error `invalid_stop`; connection and bad-body failures become `cannot_connect`). The line is accepted when the snapshot contains it, or when it does not and `async_operator_serves_line("15", line)` is true (the line exists for Metropoline but no vehicle is in the current window). Otherwise the form error is `line_not_found`. Ambiguous multi-operator lines use `ambiguous_line` as described above.
   - The entry stores `stop_code`, `line_number`, `operator_id`, `route_id` (empty string when the live window did not reveal one), and the stop name. The title is the line, the stop name, and the stop code. A second entry with the same stop, line, and operator aborts with `already_configured`.
   - `async_setup_entry` gets the shared coordinator, forwards the sensor platform, and creates no extra polls. `async_unload_entry` unloads the platform and releases the coordinator subscriber.
   - Set manifest `config_flow` to true.
   - Verify: `tests/test_config_flow.py::test_user_flow_stop_and_line_creates_one_device_per_stop` (two entries, stops 25629 and 20112, line 249, one device identifier per stop). Also `test_config_flow_rejects_unknown_stop`, `test_config_flow_accepts_metropoline_line_when_no_visit`, and `test_config_flow_rejects_ambiguous_line`. The flow tests patch `async_get_source` with a fake.

8. **Add the options flow.**
   - `async_get_options_flow` returns a flow with the same two fields, prefilled from the entry. Validation is the same function as the user step.
   - On submit, `async_update_entry` replaces `stop_code`, `line_number`, `operator_id`, `route_id`, and the stop name, then `async_reload` runs. The entry is not removed.
   - The sensor unique id is `{stop_code}_{line_number}_{operator_id}`. Before creating entities, update the entity-registry unique id when the reloaded entry's key changed, so the previous entity is kept and retargeted.
   - Verify: `tests/test_config_flow.py::test_options_flow_changes_stop_and_line` submits a new stop and line, asserts they were validated through the fake source, asserts the entry data and the sensor follow the new pair, and asserts the old unique id is no longer a separate entity.

9. **Add the sensor.**
   - Add `sensor.py`. One `CoordinatorEntity` per config entry. Device identifier `(DOMAIN, stop_code)`, device name from the Hebrew stop name. Entity name is the line number at that stop. Unique id as above.
   - `native_value` is the integer minutes until the next selected arrival, or `None` when the selection is empty. `device_class` is `SensorDeviceClass.DURATION`. `native_unit_of_measurement` is `UnitOfTime.MINUTES`. `available` follows the coordinator, so a failed update shows unavailable.
   - Attributes: `arrivals` (at most three objects with `eta` as an ISO timestamp that includes the offset, `minutes`, `headsign`, and `live`), `route_id`, `operator`, and `last_update` (the snapshot timestamp).
   - Icon `mdi:bus`.
   - Verify: `tests/test_sensor.py::test_state_is_minutes_until_next_arrival`, `tests/test_sensor.py::test_state_unknown_when_no_arrival`, `tests/test_sensor.py::test_attributes_include_next_three_arrivals`, `tests/test_sensor.py::test_missing_line_is_unknown_without_error_log` (caplog has no ERROR records across two coordinator cycles), and `tests/test_sensor.py::test_unavailable_until_next_success`.

10. **Document install and the two example stops.**
    - Rewrite root `README.md`: what the integration does; HACS custom-repository install of this GitHub URL, then restart and Add Integration; add it twice, once for stop `25629` line `249` (Gan HaIr / Rabin Square, Malkhei Israel, toward Glilot, GTFS route `10120`) and once for stop `20112` line `249` (Glilot interchange / Derech Namir, toward Gan HaIr, GTFS route `10119`); change either value later from Configure; the state is minutes, unknown when curlbus lists no arrival, unavailable when curlbus cannot be reached.
    - Data-source caveat in the same README: curlbus.app is an unofficial single-maintainer service, it needs no API key, it can disappear or change its JSON, the integration polls it at most every 60 seconds, and it is not the Ministry of Transport feed. Say that three operators use the number 249 and that matching uses route id or Metropoline agency 15 together with the stop code.
    - Verify: `tests/test_readme.py::test_readme_documents_install_examples_and_caveat` asserts the README contains `25629`, `20112`, `249`, HACS, and curlbus. Then read the rendered sections once. Full CI (`hassfest`, `hacs`, `ruff`, `pytest`) is green.

## Acceptance criteria and the test that proves each one

| # | Acceptance criterion (from SPEC.md) | Proof |
| --- | --- | --- |
| 1 | The repo installs as a HACS custom repository, and hassfest and HACS validation pass in CI. | CI jobs `hassfest` and `hacs` (`hacs/action` with `ignore: brands` until the brand-icon follow-up) in `.github/workflows/ci.yml`. Supporting test: `tests/test_manifest.py::test_domain_and_hacs_metadata`. |
| 2 | The UI asks for a stop code and a line number, validates them against curlbus, and creates one device per stop. | `tests/test_config_flow.py::test_user_flow_stop_and_line_creates_one_device_per_stop` |
| 3 | Each stop and line has a sensor whose state is integer minutes until the next arrival, device class duration, unit min; unknown when no arrival is listed. | `tests/test_sensor.py::test_state_is_minutes_until_next_arrival` and `tests/test_sensor.py::test_state_unknown_when_no_arrival` |
| 4 | Attributes include the next 3 arrivals (timezone-aware ETA, minutes, headsign, live or scheduled), route_id, operator, and last update time. | `tests/test_sensor.py::test_attributes_include_next_three_arrivals` |
| 5 | A curlbus response without line 249 shows unknown, and the integration does not crash or log an error on every poll. | `tests/test_parser.py::test_missing_line_249_is_empty_success` and `tests/test_sensor.py::test_missing_line_is_unknown_without_error_log` |
| 6 | If curlbus is unreachable or returns an error, entities become unavailable and recover on the next successful poll. | `tests/test_coordinator.py::test_unreachable_marks_update_failed` and `tests/test_sensor.py::test_unavailable_until_next_success` |
| 7 | Polling happens at most once per 60 s per stop, shared by all sensors of that stop. | `tests/test_coordinator.py::test_one_poll_per_60s_shared_by_stop` |
| 8 | Unit tests cover parsing (time zones and a missing line), the coordinator, and the config flow, using recorded fixtures and no network calls. | `tests/test_parser.py::test_eta_timezone_offsets_and_naive_israel_local`, `tests/test_parser.py::test_missing_line_249_is_empty_success`, `tests/test_coordinator.py::test_coordinator_publishes_snapshot`, `tests/test_config_flow.py::test_user_flow_stop_and_line_creates_one_device_per_stop`, `tests/test_client.py::test_fetch_stop_uses_injected_session` |
| 9 | README documents install, setup with the two example stops, and the data-source caveat. | `tests/test_readme.py::test_readme_documents_install_examples_and_caveat` |
| 10 | Configure / the options flow can change the stop code and line number of an existing entry; the new values are validated against curlbus and the sensors update. | `tests/test_config_flow.py::test_options_flow_changes_stop_and_line` |

## Files

### Create

- `custom_components/public_transport_il/__init__.py`
- `custom_components/public_transport_il/const.py`
- `custom_components/public_transport_il/manifest.json`
- `custom_components/public_transport_il/source.py`
- `custom_components/public_transport_il/parser.py`
- `custom_components/public_transport_il/curlbus.py`
- `custom_components/public_transport_il/coordinator.py`
- `custom_components/public_transport_il/config_flow.py`
- `custom_components/public_transport_il/sensor.py`
- `custom_components/public_transport_il/strings.json`
- `custom_components/public_transport_il/translations/en.json`
- `hacs.json`
- `requirements_test.txt`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `tests/test_init.py` (replaces the nested test)
- `tests/test_manifest.py`
- `tests/test_parser.py`
- `tests/test_client.py`
- `tests/test_coordinator.py`
- `tests/test_config_flow.py`
- `tests/test_sensor.py`
- `tests/test_readme.py`
- `tests/fixtures/stop_20112_has_249.json`
- `tests/fixtures/stop_25629_no_249.json`
- `tests/fixtures/invalid_stop.json`
- `tests/fixtures/ambiguous_line_249.json`
- `tests/fixtures/scheduled_producer.json`
- `tests/fixtures/naive_eta.json`
- `tests/fixtures/metropoline_249_routes.json`

### Change

- `README.md` (PR 3)
- `AGENTS.md` (layout and known issues in PR 1; drop the prototype in PR 2)
- `.gitignore` (PR 1, cache directories)

### Delete

- `public_transport_IL/` in full (PR 1), including `custom_components/public_transport_IL/`, `hacs.json`, `requirements.test.txt`, `setup.cfg`, `.pre-commit-config.yaml`, and `tests/`
- Root `__init__.py` prototype (PR 2, after the parser and fixtures cover the useful behavior)

`SPEC.md` stays as approved. This plan does not edit it.

## Dependencies

- Runtime: none added to `manifest.json` `requirements`. HTTP uses Home Assistant's shared aiohttp session. The standard library `zoneinfo` handles `Asia/Jerusalem`. Blocked imports: `requests`, `hassapi`, and any new third-party package.
- Tests: `pytest` and `pytest-homeassistant-custom-component==0.13.205` on Python 3.12 (provides the `hass` fixture, `async_fire_time_changed`, and the recorder/time freezers the sensor tests need). That release installs Home Assistant 2025.1.4, which is the `hacs.json` `homeassistant` value. Newer plugin releases require Python 3.13 or 3.14.
- Lint: `ruff`, installed from `requirements_test.txt` and run in CI.
- CI actions: `actions/checkout`, `actions/setup-python`, `home-assistant/actions/hassfest`, `hacs/action` (`category: integration`, `ignore: brands` until `custom_components/public_transport_il/brand/icon.png` exists).
- Interpreter: Python 3.12.

## Risks

- **curlbus availability.** The service is one person's project. If it is down, slow, or withdrawn, every entity goes unavailable and recovers only when a poll succeeds. The `ArrivalSource` factory is the swap point for a future SIRI client. v1 does not call the Ministry feed and does not add an API key. Polling stays at 60 seconds per stop, one unfiltered request, so several lines at one stop do not multiply traffic. Tests never call the network.
- **Response format changes.** The parser depends on `visits`, `stop_info.name`, `line_name`, `route_id`, `operator_id`, `eta`, `producer`, and `static_info.route`. A renamed field becomes a bad-response error and the entities go unavailable, which is the failure mode in acceptance criterion 6, and it will show up as a failing fixture test once a new recording is saved. Invalid stops are HTTP 200 with an `errors` array; treating any HTTP 200 as success would create a device for a bad stop code.
- **Direction numbering.** GTFS uses directions `0` and `1`. curlbus and SIRI use `1` and `2`. The same physical direction does not share a number across those systems. Match keys are route id, or operator id plus line name, plus the stop code. `direction_id` is not stored on the config entry and is not read by the selector or the sensor.
- **route_id changes after a GTFS update.** `10120` and `10119` were the Metropoline 249 route ids on 2026-10-27. A feed update can assign new route ids while the line number and agency stay the same. The selector falls back to operator `15` plus line name plus stop, and adopts the new route id when that pair identifies exactly one route. When the same operator and line suddenly appear under several route ids at one stop, the sensor goes unknown until the stored route id is seen again or the user re-saves the entry. Config validation via `/metropoline/{line}` proves the line exists for that operator and does not prove the stop lies on the route.

## Rollback

Nothing in the repository has been released, and the current scaffold has `config_flow: false`, so there are no existing `public_transport_IL` config entries to migrate.

- Revert the pull requests in reverse order (PR 3, then PR 2, then PR 1). Each one is limited to its own layer.
- Reverting PR 1 restores the nested scaffold. The repository is again not installable as a HACS custom repo, which is the current behavior.
- Reverting PR 2 removes the client and restores no runtime behavior, because PR 2 is not wired to a config flow.
- Reverting PR 3 after someone has already added the integration leaves config entries that fail to set up until that person deletes them. The entries hold a stop code and a line number, not credentials, so there is nothing to rotate.
- A curlbus outage is not a reason to revert. Entities become unavailable at the 60-second interval and return on the next good poll.

## Suggested pull-request split

One pull request would be too large: it would combine a repository move, CI, a new HTTP client, coordinator lifetime, two UI flows, and the sensor. Use three pull requests, each based on the previous one, each green on hassfest, HACS validation, ruff, and pytest before merge.

| PR | Contents | Done when |
| --- | --- | --- |
| PR 1 | Restructure to `custom_components/public_transport_il/`, root `hacs.json`, lowercase domain, CI (hassfest, HACS, ruff, pytest), delete `public_transport_IL/` | CI green; domain test and manifest test pass; prototype still present |
| PR 2 | `ArrivalSource`, curlbus client, parser, 60 s shared coordinator, fixtures and unit tests; delete root `__init__.py` | Parser, client, and coordinator tests pass with no network |
| PR 3 | Config flow, options flow, sensors, strings, README, `config_flow: true` | Every test named in the acceptance table passes; README covers install, stops 25629 and 20112, and the curlbus caveat |

## Decisions

1. The planning request approves SPEC.md for Gate A. SPEC.md's own status line is left as it is. Implementation waits for Gate B approval of this plan.
2. Restructure the existing repository in place. The nested `public_transport_IL/` tree is removed in PR 1. The root prototype is removed in PR 2, after fixtures and parser tests cover the ETA and line-selection behavior worth keeping.
3. Domain is `public_transport_il`. Manifest `iot_class` is `cloud_polling`, and that key is not copied into root `hacs.json` because the HACS schema rejects it. Hassfest requires manifest keys ordered `domain`, `name`, then alphabetical. `integration_type` is omitted. Version for the new manifest is `0.1.0`. Code owners use `@ZeMeny`.
4. `config_flow` stays false in PR 1 and becomes true in PR 3, when `config_flow.py` exists, so hassfest does not see a flag without a flow module.
5. One config entry is one stop plus one line. The device identifier is the stop code. The coordinator registry key is the stop code, with a subscriber count, and `update_interval` is 60 seconds.
6. The only curlbus request per poll is `GET /{stop_code}`. Lines at the same stop share that response. Operator `15` is confirmed with `GET /metropoline/{line}` during config and options validation when the live window has no visit for that line.
7. Match by stored route id when it is present in the payload; otherwise by operator id plus line name plus stop code. Prefer operator `15` when several operators share the line number. Ignore `direction_id`. A single replacement route id is adopted when the stored one disappears.
8. A missing line is a successful empty snapshot. It is not `UpdateFailed` and it is not logged at error. Unreachable curlbus, non-JSON bodies, and curlbus `errors` are `UpdateFailed`, so entities go unavailable and clear on the next success.
9. ETAs keep their offset. Naive timestamps mean `Asia/Jerusalem`. Minutes are the floor of remaining whole minutes after dropping visits more than 30 seconds old. Sensor state `None` is the unknown state. `live` is true only for producers `SIRI` and `GTFS-RT`.
10. Display names and headsigns use the Hebrew curlbus strings, with English as the fallback. The operator attribute prefers the English agency name.
11. Sensors and the config flow depend on `ArrivalSource` and the factory `async_get_source`. They do not import the curlbus module.
12. No runtime third-party dependencies. The prototype's per-destination HTTP lookup and its substring line match are not ported.
13. There is no GitHub issue for this feature yet (`feature-request` is also not created as a label). This plan pull request is the Gate B artifact. A `Refs #N` link can be added when an issue exists.
14. The planner skill repository named in the task (`ZeMeny/meny-ai-skills`, `skills/dev-planner/SKILL.md` and `templates/PLAN.md`) returned 404 from this environment, so this file follows the section list in the planning task and the gate language already used in SPEC.md.

## Open questions

1. Is Rabin Square (board `25629`, alight `21520`) the right Gan HaIr stop, or do you board at Ibn Gvirol/Mane (`25634`)? The README examples use `25629` and `20112`. Either stop code can be entered in the flow without a code change. Non-blocking.
2. Should the alighting stop (for example `21425`) appear as a second fact, such as a scheduled time at the destination? v1 publishes the departure-stop arrival only. Non-blocking.
3. Is Hebrew the right headsign language, with English only as a fallback?
4. When the line is absent from the live window, is a successful `GET /metropoline/{line}` enough to accept setup? This plan says yes for agency 15. It does not check that the stop is actually on that route, because that endpoint does not list stops.
5. When a line number is served by several operators and Metropoline is not one of them, should the flow gain an operator field? This plan blocks that case with `ambiguous_line` and leaves the form as stop code plus line number, which is what the spec requires.
6. Should v1 synthesize a scheduled ETA when curlbus returns no visit? This plan keeps the state unknown in that case.
7. Are English-only config-flow strings enough for v1? Stop names and headsigns are still Hebrew, from the feed.

## Changelog

- 2026-10-27: Meny approved an amendment. Root `hacs.json` keeps `name`, `render_readme`, and `homeassistant` (`2025.1.4`) and omits `iot_class`, which stays `cloud_polling` only in `custom_components/public_transport_il/manifest.json`. The HACS job runs `hacs/action` with `ignore: brands` until `custom_components/public_transport_il/brand/icon.png` is added. Description, topics, and a default-branch `LICENSE` are Meny's tasks outside the PRs. Tests pin `pytest-homeassistant-custom-component==0.13.205` on Python 3.12. Hassfest requires manifest keys ordered `domain`, `name`, then alphabetical.
