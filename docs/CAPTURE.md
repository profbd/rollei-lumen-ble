# Capturing another device or feature

Normal control does not require capture tools. For unknown features, record a working vendor-app connection rather than guessing commands.

## Apple capture route

Apple distributes PacketLogger in [Additional Tools for Xcode](https://developer.apple.com/bluetooth/). Consult the current **Bluetooth for iOS/iPadOS** instructions on [Profiles and Logs](https://developer.apple.com/feedback-assistant/profiles-and-logs/?name=bluetooth). Downloads may require an Apple sign-in.

Install the matching official logging profile on the iPad, follow its restart instructions, connect it to the Mac over USB, trust the computer and start an iOS trace in PacketLogger. Confirm that actual iPad events arrive before opening the vendor app. Apple describes this route in [its Core Bluetooth developer session](https://developer.apple.com/videos/play/wwdc2019/901/).

Use one light. Begin recording before connection. Change one parameter at a time, note actual displayed values and action times, and include repeated known values. Slider motion creates many packets; presets help identify stable frame values. Save the original `.pklg` locally and remove the diagnostic profile after the experiment.

## Offline analyzer

```sh
python src/analyze_capture.py captures/recording.pklg captures/analysis
```

The standalone analyzer uses only the Python standard library. It validates record boundaries and ACL/L2CAP lengths, supports both header byte orders and rejects unsupported fragmentation. It extracts ATT packets into CSV and records source hash/counts in JSON. Nine-byte values matching the recovered frame signature are annotated as candidates regardless of numeric ATT handle. This is pattern matching, not automatic device identification; check connection and service discovery before attributing frames to a light.

Empty captures produce an empty table. Malformed/truncated records raise an error. The tool does not replay commands or contact Bluetooth.

Raw captures may contain unrelated device names and traffic. Keep them private and publish only a deliberately minimized, reviewed extract. The release exporter excludes all captures and local experiment notes.

The PacketLogger record layout was cross-checked against [Wireshark's PacketLogger reader](https://github.com/wireshark/wireshark/blob/master/wiretap/packetlogger.c). The Python analyzer was written for this experiment; no Wireshark source is bundled.
