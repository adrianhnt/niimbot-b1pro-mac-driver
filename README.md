# Niimbot B1 Pro – macOS CUPS Driver

[![Latest release](https://img.shields.io/github/v/release/adrianhnt/niimbot-b1pro-mac-driver)](../../releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Unofficial macOS driver for the **Niimbot B1 Pro** label printer. It makes the
printer — which only speaks a proprietary protocol over USB — show up as a
normal printer under **System Settings → Printers & Scanners**, usable from
any app's print dialog, without the official Niimbot app.

> **⚠️ This project is "vibecoded."** Essentially all of the protocol
> reverse-engineering, driver code, and packaging here was produced through
> an AI coding assistant (Claude) in conversation with the maintainer. The
> maintainer reviewed the approach and verified real-world printing behavior
> against one physical unit, but did not hand-write or formally audit the
> low-level protocol and CUPS plumbing line by line. It works for the
> hardware it was built and tested against — that's not the same guarantee
> you'd get from a driver written and reviewed by hand. **Read the code
> yourself before relying on it for anything that matters**, especially
> before building on top of it or deploying it beyond your own desk.

## Download

Get the latest `.pkg` installer from the **[Releases page](../../releases/latest)**.

## Features

- Adds a real, native macOS printer queue for the Niimbot B1 Pro (USB) —
  print from any app via *File → Print*, no Niimbot app required
- Automatic PDF rasterization (via Poppler's `pdftoppm`) at 300dpi, matching
  the printer's native resolution
- Drives the full print lifecycle (start/end print, page dimensions, bitmap
  rows) over the reverse-engineered serial protocol
- Auto-recovers the device path: if the configured `/dev/cu.usbmodemXXX` port
  is gone (e.g. after unplug/replug), it falls back to scanning for other
  USB-modem devices
- Configurable print density (1–5) and a handful of common label sizes
  (30×20mm, 40×30mm, 50×30mm) plus a free custom page size
- One-click `.pkg` installer: creates a dedicated Python venv, installs the
  CUPS backend with correct ownership/permissions, registers the PPD and
  printer queue automatically
- Install-time *and* print-time dependency checks for Homebrew/Poppler, with
  a native macOS alert dialog if something's missing
- Standalone `niimbot_protocol.py` module (just `pyserial`, nothing printer-
  specific) that also exposes read-only `GET_INFO` / `GET_RFID` / heartbeat
  queries — useful on its own for scripting or automation, independent of
  CUPS

## Approach

The B1 Pro only speaks a small, proprietary binary protocol (packet framing:
`0x55 0x55` header, type, length, payload, XOR checksum, `0xAA 0xAA` footer)
over what macOS sees as a plain USB CDC-ACM virtual serial port
(`/dev/cu.usbmodemXXX`) — not a standard USB printer class. It also has no
Wi-Fi or other network hardware at all, so there is no way to make the device
AirPrint-capable by itself, no matter what runs on it.

Instead, this project builds a **CUPS driver** that makes the rest of macOS
believe the B1 Pro is an ordinary printer:

```
App prints a PDF
  -> macOS/CUPS filter chain (hands the backend a ready PDF)
  -> niimbot_backend.py   (installed as /usr/libexec/cups/backend/niimbot)
       -> pdftoppm (Poppler) rasterizes each page to PNG at 300dpi
       -> Pillow loads the PNG
       -> niimbot_protocol.py encodes it into the printer's native bitmap
          commands and sends it over the USB-serial connection
```

The protocol itself was reconstructed primarily from the open-source
[niimprint](https://github.com/AndBondStyle/niimprint) project and the
[niim.blue](https://printers.niim.blue/) community wiki, then verified
against a real B1 Pro — reading `GET_INFO`/`GET_RFID` and printing real test
labels — rather than taken on faith.

## Installation

1. Download the `.pkg` from [Releases](../../releases/latest) and install it
   (double-click, enter your admin password).
   - The package is unsigned/un-notarized. If Gatekeeper complains about an
     "unidentified developer", right-click → **Open** instead of
     double-clicking.
2. Dependency: [Poppler](https://poppler.freedesktop.org/) (for `pdftoppm`).
   The installer checks for this automatically and shows a native alert if
   it's missing:
   ```bash
   brew install poppler
   ```
   (if Homebrew itself is missing, install it from <https://brew.sh> first)
3. Plug in the printer via USB. It should then appear as "Niimbot B1 Pro"
   under **System Settings → Printers & Scanners**.

## Building from source

```bash
./scripts/build_pkg.sh            # builds dist/NiimbotB1ProDriver.pkg
```

## Known limitations

- Only tested over **USB cable**, not Bluetooth.
- Only tested against one physical unit: hardware version 5.13 / firmware
  5.3.
- Device port is configured via `DEVICE_URI` (default
  `/dev/cu.usbmodem101`); falls back to scanning `/dev/cu.usbmodem*` if that
  exact path is gone.
- `GET_RFID`'s `used_count`/`total_count` fields count **printed labels**,
  not millimeters of tape — confirmed empirically against real hardware, not
  from official documentation.
- The PPD currently lists only a few common label sizes (30×20mm, 40×30mm,
  50×30mm) plus a free custom size; adding more is a small edit to
  `NiimbotB1Pro.ppd`.

## Credits

- [niimprint](https://github.com/AndBondStyle/niimprint) (MIT) — protocol
  groundwork
- [niim.blue](https://printers.niim.blue/) — community hardware/protocol wiki

## Disclaimer

Not affiliated with, authorized by, or supported by Niimbot / Jiangsu
Jingchen. This talks to your printer over a reverse-engineered protocol that
the manufacturer has never reviewed or sanctioned — use at your own risk, and
see the vibecoding note above.

## License

MIT, see [LICENSE](LICENSE).
