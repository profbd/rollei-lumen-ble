# Contributing

Run `python -m unittest discover -s tests -v` before proposing a change. Keep Bluetooth access behind explicit commands; imports and dry runs must not contact a device.

For hardware reports, include the exact model/revision if known, OS, Python and Bleak versions, the command sent, physical switch position and the observed display/light response. Distinguish a successful host write from confirmed hardware behavior. Do not upload raw Bluetooth captures or local device identifiers without reviewing them first.

Use synthetic packet fixtures for parser tests. Do not claim support for a new model solely because it advertises a similar name or UUID. Document protocol uncertainties and preserve evidence when an assumption changes.
