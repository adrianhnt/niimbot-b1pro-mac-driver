#!/usr/bin/env python3
"""CUPS backend for Niimbot B1 Pro label printers.
Device URI scheme: niimbot:/dev/cu.usbmodemXXX
Receives a filtered PDF job (PPD declares native format = application/pdf),
rasterizes each page with pdftoppm -mono (PBM/P4, 1 bit per pixel - no
Pillow needed) and sends it via the reverse-engineered Niimbot serial
protocol (niimbot_protocol.py).

Deliberately uses only the system python3 and stdlib plus the vendored
pyserial under vendor/ - no venv, no pip, no compiled dependencies. cupsd
runs backends inside a sandbox ("cups-exec") that denies exec/metadata
access to interpreters and shared libraries outside standard system
locations, which rules out a third-party venv interpreter or Pillow's
compiled extensions here.
"""
import glob
import os
import re
import shlex
import subprocess
import sys
import tempfile

_ROOT = "/usr/local/niimbot-cups"
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "vendor"))

DPI = 300


def find_pdftoppm():
    import shutil

    for candidate in (
        "/opt/homebrew/bin/pdftoppm",
        "/usr/local/bin/pdftoppm",
        "/opt/local/bin/pdftoppm",
        shutil.which("pdftoppm"),
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def log(level, msg):
    sys.stderr.write(f"{level}: niimbot backend: {msg}\n")
    sys.stderr.flush()


def discover():
    print('niimbot niimbot:/dev/cu.usbmodem101 "Niimbot B1 Pro" "Niimbot B1 Pro (USB)" ""')


def parse_options(opt_string):
    opts = {}
    for tok in shlex.split(opt_string or ""):
        if "=" in tok:
            k, v = tok.split("=", 1)
            opts[k] = v
    return opts


def parse_pbm(path):
    """Parse a binary PBM (P4) file: returns (width, height, rows), where
    rows is a list of height byte-strings, each ceil(width/8) bytes, MSB
    first, 1 = black/ink - exactly the layout the Niimbot protocol wants.
    """
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"P4"):
        raise ValueError(f"{path}: kein P4-PBM")

    pos = 2
    values = []
    while len(values) < 2:
        while data[pos : pos + 1].isspace():
            pos += 1
        if data[pos : pos + 1] == b"#":
            while data[pos : pos + 1] not in (b"\n", b""):
                pos += 1
            continue
        start = pos
        while not data[pos : pos + 1].isspace():
            pos += 1
        values.append(int(data[start:pos]))
    width, height = values
    pos += 1  # single whitespace byte separating header from raster data

    row_bytes = (width + 7) // 8
    raster = data[pos : pos + row_bytes * height]
    rows = [raster[i * row_bytes : (i + 1) * row_bytes] for i in range(height)]
    return width, height, rows


def main():
    if len(sys.argv) == 1:
        discover()
        return 0

    if len(sys.argv) < 6:
        log("ERROR", f"unerwartete Argumentanzahl: {sys.argv!r}")
        return 1

    job_id, user, title, copies_s, options_s = sys.argv[1:6]
    infile = sys.argv[6] if len(sys.argv) > 6 else None
    opts = parse_options(options_s)

    try:
        copies = max(1, int(copies_s))
    except ValueError:
        copies = 1

    try:
        density = max(1, min(5, int(opts.get("niimDensity", "3"))))
    except ValueError:
        density = 3

    device_uri = os.environ.get("DEVICE_URI", "niimbot:/dev/cu.usbmodem101")
    port = device_uri.split(":", 1)[1] if ":" in device_uri else device_uri
    if not port.startswith("/"):
        port = "/" + port
    if not os.path.exists(port):
        candidates = sorted(glob.glob("/dev/cu.usbmodem*"))
        if len(candidates) == 1:
            log("INFO", f"{port} nicht gefunden, verwende statt dessen {candidates[0]}")
            port = candidates[0]
        elif len(candidates) > 1:
            log("ERROR", f"{port} nicht gefunden, mehrere Kandidaten: {candidates}")
            return 1
        else:
            log("ERROR", f"{port} nicht gefunden, kein USB-Modem-Geraet angeschlossen")
            return 1

    from niimbot_protocol import PrinterClient

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = infile
        if pdf_path is None:
            pdf_path = os.path.join(tmpdir, "job.pdf")
            with open(pdf_path, "wb") as f:
                f.write(sys.stdin.buffer.read())

        pdftoppm = find_pdftoppm()
        if pdftoppm is None:
            import shutil as _shutil

            if _shutil.which("brew") or os.path.exists("/opt/homebrew/bin/brew") or os.path.exists("/usr/local/bin/brew"):
                log("ERROR", "pdftoppm (Poppler) fehlt. Bitte im Terminal ausfuehren: brew install poppler")
            else:
                log("ERROR", "pdftoppm (Poppler) fehlt, und Homebrew ist nicht installiert. "
                              "Zuerst https://brew.sh installieren, danach: brew install poppler")
            return 1

        out_prefix = os.path.join(tmpdir, "page")
        try:
            subprocess.run(
                [pdftoppm, "-r", str(DPI), "-mono", pdf_path, out_prefix],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            log("ERROR", f"pdftoppm fehlgeschlagen: {e.stderr.decode(errors='replace')}")
            return 1

        def page_number(path):
            m = re.search(r"-(\d+)\.pbm$", path)
            return int(m.group(1)) if m else 0

        # Numerisch statt alphabetisch sortieren: pdftoppm benennt Seiten je
        # nach Version ohne führende Nullen (page-1, page-2, ..., page-10),
        # was alphabetisch die Reihenfolge ab 10 Seiten durcheinanderbringt.
        pages = sorted(glob.glob(out_prefix + "*.pbm"), key=page_number)
        if not pages:
            log("ERROR", "keine Seiten gerendert")
            return 1

        try:
            printer = PrinterClient(port)
        except Exception as e:
            log("ERROR", f"konnte {port} nicht oeffnen: {e}")
            return 1

        try:
            for copy_idx in range(copies):
                for page_path in pages:
                    width, height, rows = parse_pbm(page_path)
                    log("INFO", f"drucke Seite {page_path} ({width}x{height}), Kopie {copy_idx + 1}/{copies}")
                    ok = printer.print_raster(width, height, rows, density=density, label_type=1)
                    if not ok:
                        log("ERROR", "Druckauftrag vom Drucker nicht bestaetigt")
                        return 1
        finally:
            printer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
