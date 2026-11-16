# Niimbot B1 Pro – macOS CUPS Driver

Inoffizieller macOS-Treiber für den **Niimbot B1 Pro** Etikettendrucker. Macht den
Drucker, der per USB nur ein proprietäres Protokoll spricht, als ganz normalen
Drucker unter **Systemeinstellungen → Drucker & Scanner** verfügbar – ohne die
offizielle Niimbot-App.

Nicht von Niimbot/Jiangsu Jingcheng autorisiert oder unterstützt. Nutzung auf
eigene Verantwortung.

## Wie es funktioniert

```
App druckt PDF
   -> CUPS
   -> Backend (scripts/niimbot_backend.py, als /usr/libexec/cups/backend/niimbot installiert)
        -> pdftoppm (Poppler) rastert jede Seite zu PNG bei 300dpi
        -> PIL lädt das Bild
        -> niimbot_protocol.py schickt es über das reverse-engineerte
           Niimbot-Protokoll via USB-Serial (/dev/cu.usbmodemXXX) an den Drucker
```

Der Drucker meldet sich über USB als virtueller CDC-ACM-Seriell-Port (nicht als
USB-Druckerklasse). Das Protokoll (Paket-Framing, Druckbefehle, `GET_INFO`,
`GET_RFID`) ist textuell dokumentiert, nicht verschlüsselt.

## Installation

1. Neuestes `.pkg` aus [Releases](../../releases) laden (oder selbst bauen,
   siehe unten) und installieren (Doppelklick → Administratorpasswort).
   - Da das Paket nicht signiert ist, meldet macOS beim ersten Mal eventuell
     "nicht verifizierter Entwickler" – dann Rechtsklick → **Öffnen**.
2. Abhängigkeit: [`poppler`](https://poppler.freedesktop.org/) (für
   `pdftoppm`). Das Installationsskript prüft das automatisch und zeigt einen
   Hinweis, falls es fehlt:
   ```
   brew install poppler
   ```
   (falls auch Homebrew fehlt: zuerst <https://brew.sh> installieren)
3. Drucker per USB-Kabel anschließen. Er taucht danach unter
   **Systemeinstellungen → Drucker & Scanner** als "Niimbot B1 Pro" auf.

## Selbst bauen

```bash
./scripts/build_pkg.sh            # baut dist/NiimbotB1ProDriver.pkg
```

## Bekannte Einschränkungen

- Nur über **USB-Kabel** getestet, nicht über Bluetooth.
- Der Geräte-Port wird per `DEVICE_URI` konfiguriert (Standard
  `/dev/cu.usbmodem101`); ist dieser Pfad nicht vorhanden, sucht das Backend
  automatisch nach anderen `/dev/cu.usbmodem*`-Geräten.
- `GET_RFID` liefert `used_count`/`total_count` – das zählt **gedruckte
  Labels**, nicht Millimeter (empirisch verifiziert, nicht offiziell
  dokumentiert).
- Nur gegen Hardware-Version 5.13 / Firmware 5.3 getestet (ein Gerät).
- PPD enthält aktuell nur wenige Standard-Labelgrößen (30x20, 40x30, 50x30mm)
  plus freie Größe; weitere Größen lassen sich einfach in der `.ppd` ergänzen.

## Danke an

- [niimprint](https://github.com/AndBondStyle/niimprint) (MIT) – Grundlage für
  das Verständnis des Paket-Formats und der Druckbefehle
- [niim.blue](https://printers.niim.blue/) – Community-Wiki mit
  Protokoll-/Hardware-Dokumentation

## Lizenz

MIT, siehe [LICENSE](LICENSE).
