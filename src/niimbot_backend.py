#!/usr/local/niimbot-cups/venv/bin/python3
"""CUPS backend for Niimbot B1 Pro label printers.
Device URI scheme: niimbot:/dev/cu.usbmodemXXX
Receives a filtered PDF job (PPD declares native format = application/pdf),
rasterizes each page with pdftoppm at 300dpi and sends it via the
reverse-engineered Niimbot serial protocol (niimbot_protocol.py).
"""
import glob
import os
import shlex
import subprocess
import sys
import tempfile

sys.path.insert(0, "/usr/local/niimbot-cups")

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

    from PIL import Image
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
                [pdftoppm, "-r", str(DPI), "-png", pdf_path, out_prefix],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            log("ERROR", f"pdftoppm fehlgeschlagen: {e.stderr.decode(errors='replace')}")
            return 1

        pages = sorted(glob.glob(out_prefix + "*.png"))
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
                    img = Image.open(page_path)
                    log("INFO", f"drucke Seite {page_path} ({img.size}), Kopie {copy_idx + 1}/{copies}")
                    ok = printer.print_image(img, density=density, label_type=1)
                    if not ok:
                        log("ERROR", "Druckauftrag vom Drucker nicht bestaetigt")
                        return 1
        finally:
            printer.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
