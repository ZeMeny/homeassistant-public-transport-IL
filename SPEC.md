# SPEC: Next-bus sensors for line 249 (Gan HaIr <-> Glilot)

Status: DRAFT, awaiting human approval (Gate A). No code until the plan is also approved (Gate B).

## Goal
A Home Assistant custom integration that shows, in real time, when the next Metropoline line 249 buses arrive at the user's two stops: from Gan HaIr (Rabin Square) toward Glilot, and from Glilot toward Gan HaIr. First version covers just these two stop/line pairs but the setup is configurable so other stops and lines can be added later without code changes.

## Constraints
- Domain `public_transport_il`; repo must be installable via HACS (`custom_components/public_transport_il/` and `hacs.json` at repo root).
- Data source for v1: curlbus.app (live, no API key). Poll no faster than every 60 s. All I/O async (aiohttp via HA's shared session).
- Data access sits behind a small client interface so curlbus can later be replaced by the Ministry of Transport SIRI feed without touching sensors or the config flow.
- Match arrivals by route_id (or operator Metropoline, agency 15) plus stop code, not by line number alone: three operators have a line 249.
- Do not rely on direction numbers (GTFS uses 0/1, curlbus/SIRI uses 1/2).
- No secrets, HA credentials or server addresses in the repo.
- Python 3.12+, type hints, ruff, tests with pytest-homeassistant-custom-component.

## Reference data (verified 2026-10-27 from MOT GTFS and curlbus)
| Leg | route_id | Board stop | Alight stop | Scheduled ride |
|---|---|---|---|---|
| Gan HaIr -> Glilot (toward Kfar Saba) | 10120 | 25629 (Rabin Sq/Malkhei Israel) | 21425 (Glilot interchange/Route 5) | ~18 min |
| Glilot -> Gan HaIr (toward Tel Aviv, Carmelit) | 10119 | 20112 (Glilot interchange/Derech Namir) | 21520 (Rabin Sq/Malkhei Israel) | ~17 min |

Alternative stops nearby: 25634 (Ibn Gvirol/Mane, next stop after 25629), 20105 and 20096 (Levinsky College).

## Acceptance criteria
- [ ] The repo installs as a custom repository in HACS, and `hassfest` and HACS validation pass in CI.
- [ ] Adding the integration through the UI asks for a stop code and a line number (config flow), validates them against curlbus, and creates one device per stop.
- [ ] For each configured stop and line there is a sensor whose state is the minutes until the next arrival (integer, device class duration, unit min); "unknown" when no arrival is listed.
- [ ] The sensor attributes include the next 3 arrivals (ETA as a timezone-aware timestamp, minutes, headsign, whether the time is live or scheduled), route_id, operator and last update time.
- [ ] Given a curlbus response without line 249, the sensor shows unknown and the integration does not crash or log errors on every poll.
- [ ] If curlbus is unreachable or returns an error, the entities become unavailable and recover automatically on the next successful poll.
- [ ] Polling happens at most once per 60 s per stop, shared by all sensors of that stop.
- [ ] Unit tests cover parsing (including time zones and a missing line), the coordinator, and the config flow, using recorded curlbus fixtures; no network calls in tests.
- [ ] README documents install, setup with the two example stops, and the data-source caveat.

## Out of scope (v1)
- Official Ministry of Transport SIRI integration, fixed-IP setup, or API keys.
- Map or vehicle-position display, alerts, notifications, dashboards or custom Lovelace cards.
- Journey planning or stop search by name (the user enters stop codes).
- Multiple lines per sensor, and operators other than the ones returned by the stop.

## Open questions for the human
1. Is Rabin Square (25629 / 21520) the right Gan HaIr stop, or do you board at Ibn Gvirol/Mane (25634)?
2. Do you want the arrival stop (for example 21425) shown as a second piece of information, such as expected arrival time at your destination from the schedule, or only the departure stop?
3. Repo structure: restructure the existing repo in place (move the skeleton to `custom_components/public_transport_il/` at the root and replace the prototype script) or start clean on a new branch while keeping the prototype in git history? Recommendation: restructure in place on a feature branch.
4. Should the prototype `__init__.py` at the repo root be deleted? Recommendation: yes, once its logic is ported.
