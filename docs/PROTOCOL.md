# Recovered BLE protocol

Status: experimentally recovered on 2026-10-24 from a working iPad connection to a Rollei Lumen Pocket Bi-Color V2, followed by Python tests on three lights. This is an observation report, not a manufacturer specification.

## GATT interface

| Purpose | UUID | Property observed |
| --- | --- | --- |
| Control service | `0000ffc0-0000-1000-8000-00805f9b34fb` | Service |
| Command characteristic | `0000ffc1-0000-1000-8000-00805f9b34fb` | Write without response |
| Notification characteristic | `0000ffc2-0000-1000-8000-00805f9b34fb` | Notify |

Identify characteristics by UUID. Numeric handles from PacketLogger and the macOS API differed and must not be used as portable identifiers. The observed advertised names used the `Magic-` prefix followed by twelve hexadecimal characters. The tested advertisements exposed the FEE7 service rather than FFC0; discovery must not require an advertised FFC0 UUID.

## Light-setting frame

Send this nine-byte value to FFC1 using write without response:

```text
28 00 00 00 TT BB 00 0F 29
```

| Byte offset | Meaning |
| --- | --- |
| 0–3 | Constant `28 00 00 00` in the captured light-setting frames |
| 4 | Temperature divided by 100 K, one byte |
| 5 | Brightness percent, one byte |
| 6–8 | Constant `00 0F 29` in the captured light-setting frames |

Examples:

| Setting | Value |
| --- | --- |
| 4000 K / 20% | `280000002814000f29` |
| 4000 K / 0% | `280000002800000f29` |
| 5500 K / 100% | `280000003764000f29` |
| 4500 K / 100% | `280000002d64000f29` |
| 3200 K / 100% | `280000002064000f29` |
| iPad OFF after 3200 K | `280000002000000f29` |

The app produced many frames while its sliders moved. All 560 matching frames in the first recording shared this layout; the three selected presets transmitted brightness 100. A varying checksum was not observed in these frames. Constant-byte meanings remain unknown.

## Connection sequence used successfully

1. Discover the exact advertised device name.
2. Connect and resolve services.
3. Subscribe to FFC2 notifications.
4. Write the light-setting frame to FFC1 without response.
5. Allow time for delivery, then unsubscribe and disconnect.

The Python tests used the sequence above, without replaying the original app’s additional initialization messages.

## Power and identity

With physical ON, brightness zero extinguished the light, and brightness 20 restored it. With physical OFF, a 4000 K / 20% setting appeared on the display but did not illuminate the LEDs. No separate remote power-enable or persistent rename command is known.

Local labels are stored in the application configuration; they do not change the advertised BLE device name.

## Scope

The observed frame format and physical-device evidence concern Pocket Bi-Color V2. The application accepts 3200–5500 K in 100 K steps and 0–100% brightness. The constants above describe the recorded light-setting frames.
