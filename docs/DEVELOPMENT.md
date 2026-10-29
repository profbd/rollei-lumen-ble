# Developer guide

Start with the [user README](../README.md) for installation and the [studio guide](STUDIO.md) for the interface.

## Studio interaction principle

Common studio actions must be directly accessible or require as few clicks as possible. This is an owner-approved project requirement. Applying a scene uses one direct scene button; frequent controls must not introduce a selection-plus-confirmation workflow. Keep management actions separate, and retain confirmations for deleting or replacing saved data.

## Project layout

- `src/studio_gui.py`: Tk/ttk desk and user actions.
- `src/studio_model.py`: levels, linear transitions, scene/preset validation and atomic storage.
- `src/studio_ble.py`: worker thread, persistent BLE clients and coalesced writes.
- `src/rollei_lumen.py`: recovered frame encoder and command-line controls.
- `src/analyze_capture.py`: offline PacketLogger analyzer.
- `tests/`: synthetic protocol, transport and storage tests.

## Standard package installation

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install .
lumen-studio
```

## Windows installation

In Command Prompt in the source folder:

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install .
lumen-studio
```

Bleak selects its WinRT dependencies on Windows; do not install the macOS lock file there. The GUI runs BLE on a separate asyncio worker thread. The existing CI configuration includes Windows for offline tests and installation; a configured workflow is not a completed Windows hardware test.

References: [Python on Windows](https://docs.python.org/3.13/using/windows.html), [venv](https://docs.python.org/3.13/library/venv.html), [Bleak platform support](https://bleak.readthedocs.io/en/latest/).

## Optional macOS starter

`Start Studio.command` is a convenience wrapper, not the primary installation mechanism. From the extracted project folder, `bash "Start Studio.command"` automates the standard environment setup and opens the GUI. It selects Python 3.13 when available, verifies Tk before creating `.venv`, and uses a hash of `pyproject.toml` to recognize installed dependencies. If the dependency definition changes, it reinstalls the local package. `LUMEN_SETUP_ONLY=1` installs without opening a window; `LUMEN_PYTHON` can specify an interpreter for isolated installer testing.

## CLI

```sh
rollei-lumen scan
rollei-lumen inspect --name Magic-EXAMPLE
rollei-lumen set --name Magic-EXAMPLE --kelvin 4000 --brightness 20 --dry-run
rollei-lumen set --name Magic-EXAMPLE --kelvin 4000 --brightness 20
```

Use your actual advertised name. The CLI accepts 3200–5500 K in 100 K steps and brightness 0–100%. `--dry-run` uses no Bluetooth. Brightness zero switches off the light output. Each command sets both fields.

For aliases, copy `examples/lamps.example.json` to `lamps.json` and replace the example names. Use `--label left --config lamps.json`, or `--all --config lamps.json` for sequential configured-group updates. Duplicate names are rejected. Group updates stop on the first error; previous writes remain applied.

## Storage and outputs

`lamps.json` contains local device names and labels. All JSON configuration and studio files are read and written as UTF-8, including on Windows. This makes non-ASCII labels, preset names and scene names portable; the schema version stays unchanged. Existing UTF-8 files keep their format. Non-UTF-8 input is rejected rather than silently reinterpreted. `studio.json` schema version 1 stores five presets and named per-device scene levels. Master and blackout are separate runtime state. Invalid or unsupported studio files are rejected without replacing the original. Valid saves use atomic file replacement. Existing lamp configuration fields are preserved when adding a light.

The GUI labels its values as setpoints. Successful BLE writes describe host-side transmission. The interface does not read measured light output. Timing uses a monotonic clock, with updates coalesced to approximately five writes per second per connected light. See [the studio guide](STUDIO.md) for transition and STOP behavior.

## Tests

```sh
python -m unittest discover -s tests -v
python tools/gui_smoke.py
```

The first command is hardware-independent; the Tk smoke test needs a desktop and uses only virtual lights. [Test evidence](TESTING.md) records the original physical observations. The GitHub workflow runs offline checks and package installation; Bluetooth hardware is exercised locally.

## Technical references

- [Recovered BLE protocol](PROTOCOL.md)
- [Optional reverse-engineering capture workflow](CAPTURE.md)
- [Source release export](RELEASING.md)
- [Contributing](../CONTRIBUTING.md)

PacketLogger and Apple's logging tools are documented only in the capture workflow because they help contributors investigate additional commands. They are not part of the application or installer.
