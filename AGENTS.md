# AGENTS.md

## Project overview
Home Assistant custom integration showing real-time arrivals for an Israeli public-transport bus line at a given stop. Status: early prototype - a standalone script works; the HA integration is an empty skeleton.

## Build & test
No build or tests yet. Planned:
```bash
pip install -r requirements_test.txt   # pytest-homeassistant-custom-component
pytest
```

## Repo layout (current)
- `__init__.py` (repo root) - prototype script; fetches arrivals from `https://curlbus.app/{stop_id}`.
- `public_transport_IL/custom_components/public_transport_IL/` - HA integration skeleton (not wired up).

## Known issues
- Prototype uses blocking `requests`; HA requires async I/O.
- Imports AppDaemon `hassapi`; not valid in an HA integration.
- Domain/manifest name must be lowercase (e.g. `public_transport_il`).
- Not HACS-installable: needs `custom_components/<domain>/` and `hacs.json` at repo root.
- No config flow, coordinator, or sensor.

## Plan
1. Restructure to `custom_components/public_transport_il/` + root `hacs.json`.
2. Async curlbus client (aiohttp) with a 60 s `DataUpdateCoordinator`.
3. Config flow: stop code + line number.
4. Sensor: minutes to next bus; upcoming arrivals as attributes.

## Data sources
- curlbus.app: live, no key, but a one-person hobby service - may disappear; keep the client swappable.
- Official MOT SIRI feed: requires approval and a fixed IP.
- Open Bus Stride: lags ~25 min; not suitable for live arrivals.

## Code style
Python 3.12+, HA conventions, type hints, `ruff` for lint/format.

## PR workflow
Branch per task, small commits, open a PR to `main`; never push to `main`. CI (hassfest, HACS validation, pytest) must pass.

## Definition of done
- [ ] Acceptance criteria met; tests pass; hassfest + HACS validation clean
- [ ] README updated if behavior/config changed

## Do not
- Use blocking I/O or `hassapi`
- Commit tokens, HA credentials, or server addresses
- Hammer curlbus: poll no faster than 60 s

## Requests and bug reports (issue flow)
Work can start two ways that feed the same loop:

- (a) The human opens a GitHub issue using the Feature request or Bug report form and assigns it to `meny-bot`. The assignment is what starts the agent. The labels `feature-request` and `bug` are only for sorting.
- (b) The human asks the assistant in chat, which opens the issue itself and then continues the same flow.

Every request must have an issue so work is tracked.

Features: the designer drafts `SPEC.md` as a PR that links the issue with `Refs #N`. The human approves the spec (gate A), then the plan (gate B, no code before this), then implementation, independent review, and human merge.

Bugs: reproduce first and add a failing test. Write a short plan in the issue or PR for human approval when the fix is non-trivial, then fix, independent review, and human merge. Skip the SPEC unless the bug reveals a behavior change.

Each stage is recorded as a comment on the issue. Agents never merge and never push to main.

The labels `feature-request` and `bug` must exist in the repo.
