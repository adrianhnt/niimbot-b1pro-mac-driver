# Handoff: Niimbot B1 Pro macOS CUPS Driver

Written at the end of a long session to let a fresh Claude Code session
pick this up with zero re-discovery. Repo:
https://github.com/adrianhnt/niimbot-b1pro-mac-driver (public, MIT).
Everything described here is already committed and pushed to `master`;
latest tag/release is **v1.4**.

## What this project is

An unofficial macOS CUPS driver for the Niimbot B1 Pro label printer
(reverse-engineered proprietary USB-serial protocol), so it shows up as a
normal printer in System Settings → Printers & Scanners / any app's Print
dialog, without the official Niimbot app. See `README.md` for the full
feature list and architecture diagram — don't duplicate that here, just
read it first.

## Current status: UNVERIFIED, this is the immediate next step

v1.4 (latest commit `9c7b118`, tag `v1.4`, release asset built) fixes a
real root-cause bug (see below) but **the user has not yet installed or
tested it**. They explicitly said so when requesting this handoff. The
very first thing to do in the new session:

1. Ask the user to run (from a local clone of this repo):
   ```bash
   sudo ./scripts/uninstall.sh
   ```
   (optional — installing the v1.4 `.pkg` directly also self-cleans the old
   venv in postinstall — but a clean uninstall first removes doubt.)
2. Have them install the v1.4 `.pkg` (from
   https://github.com/adrianhnt/niimbot-b1pro-mac-driver/releases/tag/v1.4,
   or build fresh with `./scripts/build_pkg.sh 1.4`).
   - It is **unsigned/unnotarized**. Gatekeeper will likely block it with a
     dialog that has no "Open anyway" option. Two documented workarounds in
     the README's Installation section: System Settings → Privacy &
     Security → "Open Anyway", or `xattr -d com.apple.quarantine <path>`.
3. Have them print a test page from Preview (Vorschau) → printer
   "NiimbotB1Pro".
4. If it still fails, **do not re-guess** — go straight to the diagnostic
   method below, it works and is fast.

## The actual root-cause bug v1.4 fixes (read this before debugging further)

Printing via the installed CUPS driver hung/failed silently for several
iterations. The investigation went through two *wrong* theories before
finding the real one — documented here so the new session doesn't redo
that work:

- **Wrong theory 1: SIP blocking `/usr/libexec/cups/backend/`.** Ruled out —
  the backend file installs there fine; `cp`/`chown`/`chmod` all succeed as
  root during `postinstall`.
- **Wrong theory 2: CUPS runs 755 backends as the unprivileged `_lp` user,
  needs 700 to run as root.** Changed permissions to 700, no effect. Red
  herring — the actual failure happens *before* privilege level matters.
- **Real cause, confirmed directly via the unified log:**
  ```bash
  /usr/bin/log show --last 10m --predicate 'eventMessage contains "niimbot"' --style compact
  ```
  showed:
  ```
  Sandbox: cups-exec(PID) deny(1) file-read-metadata /usr/local/niimbot-cups/venv/bin/python3
  ```
  `cupsd` runs backend processes inside a sandbox ("cups-exec" Seatbelt
  profile) that denies `execve`/metadata access to interpreters and shared
  libraries living outside standard system paths. A backend whose shebang
  pointed at a third-party venv Python under `/usr/local` could never
  actually start when launched by `cupsd` — even though running the exact
  same backend script manually as a normal user worked perfectly every
  time (manual invocation bypasses the sandbox entirely, which is why
  every earlier "run it directly" test looked fine and was misleading).
  The same log window also showed Pillow's compiled `.dylib`/`.so` files
  failing AMFI checks ("adhoc signed or signed by an unknown certificate
  chain") — a second, related problem with shipping any third-party
  compiled extension.

**The fix (already in v1.4, don't re-architect this):**
- Backend shebang is `#!/usr/bin/env python3` (system Python), not a venv.
- No Pillow. `pdftoppm -mono` produces a PBM (P4) file directly — already
  exactly the 1-bit-per-pixel, MSB-first row format the Niimbot protocol
  wants, parsed by a ~20-line pure-stdlib parser in `niimbot_backend.py`
  (`parse_pbm`).
- `pyserial` (pure Python, no compiled parts) is vendored directly into
  `src/vendor/serial/` instead of pip-installed into a venv. No `pip`, no
  `venv`, no network access at install time at all anymore.
- `niimbot_protocol.py` exposes `print_raster(width, height, rows, ...)` as
  the primary, dependency-free print path. `print_image(pil_image, ...)`
  still exists as a thin Pillow-based convenience wrapper for people using
  the module standalone for scripting — it's never called by the backend.
- `postinstall.template` removes any leftover venv from a ≤1.3 install on
  update.

**If v1.4 still fails:** don't start re-theorizing blind. Reproduce with
the same two-step diagnostic that found the real bug last time:
1. `lpstat -p -o` + `cat /var/log/cups/error_log` (world-readable, no sudo
   needed) — look for the backend's own `log("ERROR"/"INFO", ...)` lines
   and for `execv ... failed` / `Backend returned status ...` lines.
2. If that's inconclusive, `/usr/bin/log show --last Nm --predicate
   'eventMessage contains "niimbot"' --style compact` — this is what
   surfaced the Sandbox/AMFI denials that `error_log` didn't show clearly.
Also worth knowing: `cupsctl LogLevel=debug` and `cupsenable`/`cupsaccept`
work for the `adrian` user without `sudo` (member of `_lpadmin`/`admin`
groups) via the local CUPS domain socket — `sudo` itself does **not** work
non-interactively from Claude's Bash tool (no TTY for the password
prompt), so any step that genuinely needs `sudo` (writing into
`/usr/libexec/`, reading root-only files, `kill`ing another user's
process) has to be handed to the user to run themselves, or just ask them
to paste the output back.

## Hardware / environment facts (established, don't re-derive)

- Printer: Niimbot B1 Pro. MCU: SiFli SF32BPRTU36 (SF32LB family, ARM
  Cortex-M33 BLE SoC, has a public SDK — relevant only if firmware
  reverse-engineering ever comes back into scope, see below).
- USB: vendor ID `0x3513` (unregistered), product ID `0x0002`. Enumerates
  as a plain CDC-ACM virtual serial port, e.g. `/dev/cu.usbmodem101` — the
  exact number can change after unplug/replug, which is why the backend
  falls back to scanning `/dev/cu.usbmodem*` if the configured
  `DEVICE_URI` path is gone.
- Bluetooth: the printer **is** classic Bluetooth (BR/EDR, SPP), not
  BLE-only as first suspected from Niimbot's own "don't pair via phone
  settings" app instructions (that turned out to be unrelated
  marketing/UX guidance, not a technical BLE-vs-classic signal — don't
  trust vendor pairing instructions as protocol evidence again). Pairing
  through System Settings → Bluetooth works and creates a real serial port
  (`/dev/cu.B1Pro-<serial>`), and macOS even recognizes a Bluetooth
  "Printer" SDP service and offers to complete setup via Printers &
  Scanners. **However**: read-only commands (`GET_INFO`, `GET_RFID`,
  `HEARTBEAT`) work perfectly over that Bluetooth serial port, but every
  state-changing command (`SET_LABEL_DENSITY`, `START_PRINT`, etc.) gets
  **zero response** — verified at the raw-byte level, ruled out
  AddPrinter.app contention and simultaneous-USB-connection as causes.
  Root cause unresolved; likely the printer exposes multiple
  RFCOMM/Bluetooth channels (one for status, a different one for print
  control) and macOS's auto-created serial port only reaches the status
  channel. Would need direct IOBluetooth-level channel enumeration to dig
  further (pyserial/the `/dev/cu.*` abstraction can't select a specific
  RFCOMM channel). **User explicitly deprioritized this** ("reicht fürs
  Erste, bleiben wir bei USB") — don't pick it back up unless asked.
- The currently-loaded label roll (for reference / test printing): 50×30mm
  die-cut labels with gaps (`label_type=1` = "with gaps" per the
  `GET_RFID` response and matches the physical rolls), barcode `10262260`,
  serial `PZ1I126301000258`, RFID UUID `881de2563a0c1080`. `total_count`
  276 / `used_count` ~98 at last check — **these are label counts, not
  millimeters**, confirmed empirically (count went up by exactly 1 per
  completed print job regardless of image size, independent of the
  official app ever being involved).
- `GET_INFO` key 13 (undocumented in `niimprint`) returns the printer's
  Bluetooth MAC (`fd:32:0a:01:10:a8`) — cross-verified against
  `system_profiler SPBluetoothDataType`. Key 15 returns `28`, meaning
  unknown.

## Firmware reverse-engineering (separate, deprioritized sub-thread)

User expressed interest in dumping/patching the firmware itself (to remove
the RFID consumable lock-in, as a sibling project did for the plain B1
model — see https://github.com/vkolarik/niimbot-b1). Established, not yet
executed:
- Official firmware images are **not** publicly hosted for the B1 Pro's
  main application firmware; `fw.niim.blue`'s `stable/` and `testing/`
  trees for "B1 Pro" only contain font/resource OTA packages, not the main
  firmware (verified by downloading and parsing several of them).
- A documented UART-based flash read/write procedure exists (community
  "unbricking" guide), using a $5 USB-UART adapter (3.3V only!) and
  `sftool`, soldered to 3 pads on the mainboard — cheap, no JTAG/SWD
  needed, but requires physically opening the case, which only the user
  can do (no hands here). Not started. This is a separate, optional,
  explicitly-opt-in project, not blocking anything above.

## Working style notes for the new session

- The user is comfortable with real hardware experiments (soldering,
  physical teardown) but set an explicit test-print budget once ("max 5")
  — ask before burning physical labels on repeated tests; prefer read-only
  protocol queries or bypassing-CUPS direct script tests when possible.
- The user actively double-checks claims (e.g. pushed back on "the vendor
  says don't pair via Bluetooth settings" being treated as technical
  proof) — don't overstate confidence from indirect/marketing evidence,
  prefer direct empirical tests (which this project has repeatedly used to
  overturn earlier, plausible-sounding theories).
- Destructive/system-modifying Bash commands (`kill`, writes under
  `/usr/libexec`, etc.) get blocked by an auto-mode classifier in this
  environment — expect to hand those to the user as copy-pasteable
  commands rather than running them directly.
- Git commits in this repo intentionally use the GitHub no-reply commit
  email (`72196919+adrianhnt@users.noreply.github.com`, already set as the
  repo-local `git config user.email`/`user.name`) instead of the user's
  real email, to avoid exposing it in public commit history.
