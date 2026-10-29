# Lumen Studio

An English desktop lighting desk using Tk/ttk, with no browser or cloud service. The UI supports a scrollable four-column layout and at least eight configured light channels. Eight virtual channels are exercised in tests; three real lights were used for hardware tests. The GUI worker connected to all three real lights concurrently.

## Launch

After installing the source project:

```sh
lumen-studio --config lamps.json --store studio.json
```

For standard Python installation and activation, follow the [README installation steps](../README.md#install-once). The macOS convenience starter is an [optional alternative](DEVELOPMENT.md#optional-macos-starter).

For development, without reinstalling:

```sh
python src/studio_gui.py --config lamps.json --store studio.json
```

Python must include Tk. Check with `python -m tkinter`. Some Linux distributions package it separately as `python3-tk`. Python.org macOS installers normally include it. BLE control still needs the permissions described in the main README.

Preview mode does not import or access Bluetooth and uses eight virtual lights:

```sh
lumen-studio --preview
```

It defaults to `preview-studio.json`, separately from the real desk's `studio.json`.

## Lights and connections

Load the same `lamps.json` used by the CLI. **Connect all** establishes persistent connections, but does not send the draft slider values. Use **Apply selected** deliberately after checking the setpoints. Startup values are drafts (4000 K / 20%), not device readback.

Use **Add light…** to scan for `Magic-*` advertisements and enter a unique local label. Adding a light updates the local config without changing advertised BLE names. There is no fixed eight-light limit in the data model. More channels use additional scrollable rows. The eight-light preview provides a hardware-free way to try the layout.

Each light has brightness and temperature sliders, numeric spinboxes (press Enter after typing), five preset buttons, a direct Light off/on button, selection and a connection/write status. Light on restores the last positive base brightness used in the current session. Temperatures are quantized to 100 K, brightness to 1%. Keep physical power switches ON. Another connected app may prevent connections.

The worker coalesces slider changes, retains the newest pending value per light and attempts at most approximately five updates per second per light. Writes to different connected lights may run concurrently. Updates are best effort, not frame-synchronized. Connection failures are shown per channel. Reconnection is explicit and does not replay offline draft values automatically.

Disconnect and window close leave lights at their last received settings. Closing stops transitions and attempts to release connections; it does not black out the set.

## Five saved presets

Defaults: 3200, 4000, 4500, 5000 and 5500 K. **Edit 5 presets…** changes each name, temperature and optional brightness. A blank brightness preserves that light's base brightness. Changes are saved atomically to the studio file and survive restarts. A preset applies to the card where it is clicked.

## Master and blackout

Master scales every configured light's base brightness. It does not overwrite those base levels, so relative levels remain recoverable (subject to 1% rounding). **BLACKOUT** stops a running transition and requests zero brightness for all connected configured lights. **RESTORE LIGHT** reapplies the current base levels through the current master value. Blackout and master changes do not alter saved scene data.

Blackout is a software command, not a physical emergency cutoff. A disconnected or failed light cannot receive it. Already transmitted packets cannot be recalled.

## Scenes

A scene stores a name and individual base temperature/brightness for all configured lights. **Save new…** creates a scene; each saved scene is directly callable. Replacement and deletion are available under **Manage scenes…**. Every saved scene has its own button: click the name to recall it immediately, without a dropdown or confirmation. Click the adjacent **Fade** button for a timed transition. **Manage scenes…** contains replacement and deletion actions. Scene recall does not depend on the current light selection. Lights present in the scene but absent from the current config are reported and skipped; newly added lights absent from a scene are unchanged. Master and blackout are deliberately not included in a scene. Clicking a scene clears blackout automatically, using the current master setting. A scene fade from blackout starts from zero base brightness for its target lights.

Scene values are saved drafts, not measured output. A fade begins from the desk's current base values, which may differ from hardware if another controller or a failed connection changed a light. Apply known values before recording a take.

## Transitions

Effects apply to selected cards:

- **Linear fade:** interpolate both brightness and temperature between entered start/end values.
- **Fade in:** zero to each selected light's current base brightness, preserving its temperature.
- **Fade out:** each selected light's current base brightness to zero, preserving its temperature.
- **Breathing:** linear forward and return between entered endpoints, without strobing.

Set seconds per leg, endpoint hold, cycle count and optionally return to start. A cycle includes a forward leg and its hold; with return enabled it also includes the reverse leg and hold. Zero cycles means continuous repetition until stopped. A nonreturning repeated fade jumps back to its start at each cycle boundary. Use return/breathing for a smooth back-and-forth motion.

Clicking an effect button immediately requests its start levels and begins the timeline, using the displayed timing and endpoint values. There is no effect dropdown followed by a separate START step. **STOP** or Escape cancels the timeline and drops pending transition writes; current base levels remain. Manual changes and presets also stop the current transition. Stopping does not undo already received commands. Transition timings use a monotonic clock, but the hardware output is quantized and Bluetooth delivery is not exact.

A scene fade uses current base values to the selected scene's per-light values, once. It uses the shared **Fade duration** field and starts with the scene’s adjacent **Fade** button.

## Persistence and compatibility

`studio.json` schema version 1 contains exactly five presets and a list of scenes. Each scene maps exact advertised light names to integer `kelvin` and `brightness` values. Unknown versions and malformed files are rejected rather than overwritten. Valid updates are written to a temporary file and atomically replace the previous file. Configured lamp identities stay in `lamps.json`; do not rename device identifiers when moving scenes between systems without explicitly remapping them.

Local studio files, configs and preview files are excluded from the public export. Keep backups of your own setup. Effect timelines are session state; their duration/repeat controls are not currently stored as part of a scene.

