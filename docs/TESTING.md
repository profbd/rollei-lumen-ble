# Evidence and testing

## Physical-device observations

Tests were performed on 2026-10-24 with three Rollei Lumen Pocket Bi-Color V2 lights, a Mac reporting macOS 26.6.2, Python 3.13, Bleak 3.0.2 and PyObjC 12.2.2. The owner identified all three lights as V2. Firmware versions, finer hardware revisions and measurement-based light output were not recorded.

| Observation | Evidence type | Coverage |
| --- | --- | --- |
| 4000 K / 20% accepted and displayed | Python command and human observation | First light |
| 10 / 60 / 10 / 60 / 20% at 4000 K | Python sequence and human observation | Two additional lights |
| Brightness 0, then 20 after five seconds | Python sequence and human observation | First light, physical switch ON |
| Physical OFF still permits BLE connection and display updates, but no light | Python command and human observation | First light |
| 5500 / 4500 / 3200 K presets sent with 100% | iPad capture analysis | First light; not separately replay-verified |
| Matching FFC1/FFC2 services | BLE enumeration | All three lights |

Original device identifiers, raw recordings and local experiment logs remain private. The first recording contained 8,407 PacketLogger records, 600 ATT packets and 565 outgoing writes, including 560 matching light-setting frames. These counts can be reproduced locally with the analyzer and the original recording; they are not independently reproducible from the public source alone. Synthetic fixtures in the test suite contain no captured user data.

## Software validation

UTF-8 persistence and CLI aliases are regression-tested under a simulated Windows cp1252 default, including accents, symbols and Japanese scene names. This is an encoding simulation, not Windows hardware execution.

Offline tests also cover eight-channel transition interpolation, repeat/bounce/endpoint holds, preset/scene round trips, rejection of malformed/unknown-version stores, master/blackout base-level preservation and preview connection lifecycle. `tools/gui_smoke.py` exercises the real Tk callbacks in preview mode (requires a graphical desktop). The new worker successfully held connections to all three real lights at once, without sending setting commands. On 2026-10-26, the owner reported that the project and app had proved useful in practical use and approved preparing publication. This is an application-level user acceptance report, not a measured timing or per-feature test record.

Offline tests cover recorded command vectors, invalid values, configuration selection, duplicate identities, notifications before writes, UUID-based routing, disconnect on failure, no writes during inspection, fail-fast group behavior, and PacketLogger parsing/truncation. They do not prove physical device compatibility.

The current public CLI reuses the confirmed frame format and connection sequence. Packaging, scan selection and group handling are additional software behavior tested offline. A fresh physical run of the packaged CLI is separate from the original experiment; the public tests and the original observations above are separate evidence sources.

The included CI workflow runs the offline suite on Python 3.10 and 3.13 on Linux, macOS and Windows. A configured workflow is not evidence that a remote CI run has passed. Linux/Windows hardware operation remains untested.

## Rebuild from a clean environment

1. Extract the public archive or clone its future repository.
2. Create a new virtual environment with Python >=3.10.
3. Run `python -m pip install .` using PyPI for dependencies.
4. Run `python -m unittest discover -s tests -v`.
5. Run `rollei-lumen set --name Magic-EXAMPLE --kelvin 4000 --brightness 20 --dry-run`.
6. With your own compatible light, enable Bluetooth permission, disconnect other clients, scan, inspect, then send one moderate setting and visually confirm it.

The public project contains all sources needed for a new hardware test. Reproducing the historical capture analysis additionally requires the private original recording; a new capture is a new experiment, not reproduction of that historical trace.
