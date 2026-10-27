# Public Transport IL

Home Assistant integration that shows, in minutes, when the next bus of a chosen line arrives at a chosen stop. The first setup is Metropoline line 249 between Gan HaIr and Glilot. Any other stop code and line number can be added from the UI.

## Install

1. In HACS, open Integrations and choose Custom repositories.
2. Add `https://github.com/ZeMeny/homeassistant-public-transport-IL` as an Integration.
3. Download **Public Transport IL** from HACS.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration**, and choose **Public Transport IL**.

Add the integration once for each stop and line. Change either value later from **Configure** on that entry. Configure checks the new stop and line before it saves them, and the existing sensor follows the new pair.

## Example stops

Add the integration twice for line 249:

| Stop code | Line | Where you board | Direction | GTFS route |
| --- | --- | --- | --- | --- |
| 25629 | 249 | Gan HaIr / Rabin Square, Malkhei Israel | toward Glilot | 10120 |
| 20112 | 249 | Glilot interchange / Derech Namir | toward Gan HaIr | 10119 |

## Sensor

The state is the number of minutes until the next arrival. It is an integer, with device class duration and unit minutes. The state is unknown when curlbus lists no arrival for that line. The state is unavailable when curlbus cannot be reached, and it becomes available again on the next successful poll.

The attributes include the next three arrivals (timezone-aware ETA, minutes, headsign, and whether that time is live), plus `route_id`, the operator, and the last update time.

Each stop is one device. Lines at the same stop share that device and one poll.

## Data source

curlbus.app is an unofficial single-maintainer service. It needs no API key. It can disappear or change its JSON. This integration polls it at most every 60 seconds, once per stop. It is not the Ministry of Transport feed.

Three operators use the number 249. Matching uses the route id, or Metropoline agency 15, together with the stop code. Direction numbers are ignored, because GTFS and the live feed do not number directions the same way.
