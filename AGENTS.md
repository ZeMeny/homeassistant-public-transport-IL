# AGENTS.md

## Project overview
Home Assistant custom integration showing real-time arrivals for an Israeli public-transport bus line at a given stop. Status: early prototype - a standalone script works; the HA integration is an empty skeleton.

## Build & test
```bash
pip install -r requirements_test.txt
ruff check .
ruff format --check .
pytest
```

## Repo layout (current)
- `custom_components/public_transport_il/` - Home Assistant integration package. Domain `public_transport_il`. Modules: `__init__.py` (`async_setup` returns true; no config flow yet), `const.py`, `manifest.json`, `source.py` (arrival-source interface), `parser.py`, `curlbus.py`, and `coordinator.py` (one 60 s coordinator per stop).
- `hacs.json` (repo root) - HACS metadata: `name`, `render_readme`, and `homeassistant`.
- `tests/` - pytest suite (`test_init.py`, `test_manifest.py`, `test_parser.py`, `test_client.py`, `test_coordinator.py`). Parser, client, and coordinator tests read `tests/fixtures/` and do not call the network.
- `.github/workflows/ci.yml` - hassfest, HACS validation, ruff, and pytest.
- `requirements_test.txt` and `pyproject.toml` - test and lint toolchain.

## Known issues
- No config flow or sensor yet. The coordinator is not wired into setup until the config flow exists.

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
