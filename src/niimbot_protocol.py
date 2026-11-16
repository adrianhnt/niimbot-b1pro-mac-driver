"""Minimal Niimbot packet protocol, adapted from the open-source niimprint
project (AndBondStyle/niimprint, MIT licensed): packet.py + printer.py.
Only the pieces needed for read-only queries and basic printing are kept.
"""
import math
import struct
import time

import serial


class NiimbotPacket:
    def __init__(self, type_: int, data: bytes):
        self.type = type_
        self.data = data

    @classmethod
    def from_bytes(cls, buf: bytes):
        assert buf[0:2] == b"\x55\x55"
        assert buf[-2:] == b"\xaa\xaa"
        type_ = buf[2]
        length = buf[3]
        data = buf[4 : 4 + length]
        checksum = type_ ^ length
        for b in data:
            checksum ^= b
        assert checksum == buf[4 + length]
        return cls(type_, data)

    def to_bytes(self) -> bytes:
        length = len(self.data)
        checksum = self.type ^ length
        for b in self.data:
            checksum ^= b
        return bytes([0x55, 0x55, self.type, length]) + self.data + bytes([checksum, 0xAA, 0xAA])


GET_INFO = 0x40
GET_RFID = 0x1A
HEARTBEAT = 0xDC
SET_LABEL_TYPE = 0x23
SET_LABEL_DENSITY = 0x21
START_PRINT = 0x01
END_PRINT = 0xF3
START_PAGE_PRINT = 0x03
END_PAGE_PRINT = 0xE3
ALLOW_PRINT_CLEAR = 0x20
SET_DIMENSION = 0x13
SET_QUANTITY = 0x15
GET_PRINT_STATUS = 0xA3


class PrinterClient:
    def __init__(self, port: str):
        self._ser = serial.Serial(port=port, baudrate=115200, timeout=0.5)
        self._buf = bytearray()

    def close(self):
        self._ser.close()

    def _send(self, pkt: NiimbotPacket):
        self._ser.write(pkt.to_bytes())

    def _recv(self):
        packets = []
        self._buf.extend(self._ser.read(1024))
        while len(self._buf) > 4:
            pkt_len = self._buf[3] + 7
            if len(self._buf) >= pkt_len:
                packets.append(NiimbotPacket.from_bytes(bytes(self._buf[:pkt_len])))
                del self._buf[:pkt_len]
            else:
                break
        return packets

    def _transceive(self, reqcode, data, respoffset=1, tries=6):
        respcode = respoffset + reqcode
        self._send(NiimbotPacket(reqcode, data))
        for _ in range(tries):
            for pkt in self._recv():
                if pkt.type == respcode:
                    return pkt
            time.sleep(0.1)
        return None

    def get_rfid(self):
        packet = self._transceive(GET_RFID, b"\x01")
        if packet is None:
            return "keine Antwort (Timeout)"
        data = packet.data
        if len(data) == 0 or data[0] == 0:
            return None  # kein RFID-Tag gelesen / keine Rolle erkannt
        uuid = data[0:8].hex()
        idx = 8
        barcode_len = data[idx]
        idx += 1
        barcode = data[idx : idx + barcode_len].decode(errors="replace")
        idx += barcode_len
        serial_len = data[idx]
        idx += 1
        serial_ = data[idx : idx + serial_len].decode(errors="replace")
        idx += serial_len
        total_count, used_count, type_ = struct.unpack(">HHB", data[idx : idx + 5])
        return {
            "uuid": uuid,
            "barcode": barcode,
            "serial": serial_,
            # Empirisch bestaetigt: zaehlt gedruckte Labels, nicht mm (89 -> 95 nach
            # genau 6 Druckauftraegen, unabhaengig von der jeweiligen Labelhoehe).
            "used_count": used_count,
            "total_count": total_count,
            "label_type": type_,
        }

    def heartbeat(self):
        packet = self._transceive(HEARTBEAT, b"\x01")
        if packet is None:
            return None
        d = packet.data
        result = {"closingstate": None, "powerlevel": None, "paperstate": None, "rfidreadstate": None}
        if len(d) == 20:
            result["paperstate"] = d[18]
            result["rfidreadstate"] = d[19]
        elif len(d) == 13:
            result["closingstate"], result["powerlevel"], result["paperstate"], result["rfidreadstate"] = (
                d[9], d[10], d[11], d[12],
            )
        elif len(d) == 19:
            result["closingstate"], result["powerlevel"], result["paperstate"], result["rfidreadstate"] = (
                d[15], d[16], d[17], d[18],
            )
        return result

    def set_label_density(self, n):
        pkt = self._transceive(SET_LABEL_DENSITY, bytes((n,)), 16)
        return pkt is not None and bool(pkt.data[0])

    def set_label_type(self, n):
        pkt = self._transceive(SET_LABEL_TYPE, bytes((n,)), 16)
        return pkt is not None and bool(pkt.data[0])

    def start_print(self):
        pkt = self._transceive(START_PRINT, b"\x01")
        return pkt is not None and bool(pkt.data[0])

    def end_print(self):
        pkt = self._transceive(END_PRINT, b"\x01")
        return pkt is not None and bool(pkt.data[0])

    def start_page_print(self):
        pkt = self._transceive(START_PAGE_PRINT, b"\x01")
        return pkt is not None and bool(pkt.data[0])

    def end_page_print(self):
        pkt = self._transceive(END_PAGE_PRINT, b"\x01")
        return pkt is not None and bool(pkt.data[0])

    def set_dimension(self, h, w):
        pkt = self._transceive(SET_DIMENSION, struct.pack(">HH", h, w))
        return pkt is not None and bool(pkt.data[0])

    def set_quantity(self, n):
        pkt = self._transceive(SET_QUANTITY, struct.pack(">H", n))
        return pkt is not None and bool(pkt.data[0])

    def _encode_image(self, image):
        from PIL import ImageOps

        img = ImageOps.invert(image.convert("L")).convert("1")
        for y in range(img.height):
            row = [img.getpixel((x, y)) for x in range(img.width)]
            bits = "".join("0" if p == 0 else "1" for p in row)
            line_data = int(bits, 2).to_bytes(math.ceil(img.width / 8), "big")
            header = struct.pack(">H3BB", y, 0, 0, 0, 1)
            yield NiimbotPacket(0x85, header + line_data)

    def print_image(self, image, density=3, label_type=1, quantity=1):
        self.set_label_density(density)
        self.set_label_type(label_type)
        self.start_print()
        self.start_page_print()
        self.set_dimension(image.height, image.width)
        for pkt in self._encode_image(image):
            self._send(pkt)
        self.end_page_print()
        time.sleep(0.3)
        for _ in range(50):
            if self.end_print():
                return True
            time.sleep(0.1)
        return False
