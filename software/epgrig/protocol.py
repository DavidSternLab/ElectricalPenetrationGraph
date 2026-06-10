"""EPG rig device<->host protocol codec (draft v0.1).

Pure standard library (no numpy) so it is always importable and testable.
Implements COBS framing, CRC-16/CCITT, and encode/decode of the typed messages
defined in docs/protocol-and-data-format.md.

Wire frame (pre-COBS): type(1) | flags(1) | payload(N) | crc16(2)
then COBS-encoded with a trailing 0x00 delimiter. Little-endian throughout.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

PROTO_VERSION = 1

# ---- message type codes ---------------------------------------------------
# device -> host
T_INFO = 0x01
T_SAMPLES = 0x02
T_EVENT = 0x03
T_ACK = 0x04
T_NACK = 0x05
T_STATUS = 0x06
# host -> device
T_GET_INFO = 0x80
T_CONFIGURE = 0x81
T_START = 0x82
T_STOP = 0x83
T_SET_VS = 0x84
T_SET_RI = 0x85
T_CAL_PULSE = 0x86
T_SERVO = 0x87
T_PING = 0x88

# ---- event type codes -----------------------------------------------------
EV_VS_CHANGE = 1
EV_RI_CHANGE = 2
EV_CAL_PULSE = 3
EV_CLIP = 4
EV_SERVO_STATE = 5
EV_COMMENT = 6
EV_MODE_MARK = 7
EV_ERROR = 8

EVENT_NAMES = {
    EV_VS_CHANGE: "VS_CHANGE", EV_RI_CHANGE: "RI_CHANGE", EV_CAL_PULSE: "CAL_PULSE",
    EV_CLIP: "CLIP", EV_SERVO_STATE: "SERVO_STATE", EV_COMMENT: "COMMENT",
    EV_MODE_MARK: "MODE_MARK", EV_ERROR: "ERROR",
}

# servo modes
SERVO_OFF, SERVO_ACQUIRE, SERVO_TRACK = 0, 1, 2
# Ri modes
RI_1G, RI_10T = 0, 1

CHAN_DEVICE = 0xFF  # event channel value meaning "device-wide"


# ---------------------------------------------------------------------------
# CRC-16/CCITT (XModem): poly 0x1021, init 0x0000
# ---------------------------------------------------------------------------
def crc16(data: bytes) -> int:
    crc = 0x0000
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if (crc & 0x8000) else (crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# COBS encode/decode (https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing)
# ---------------------------------------------------------------------------
def cobs_encode(data: bytes) -> bytes:
    out = bytearray()
    code_idx = len(out)
    out.append(0)        # placeholder for the group's code byte
    code = 1
    for b in data:
        if b == 0:
            out[code_idx] = code
            code_idx = len(out)
            out.append(0)
            code = 1
        else:
            out.append(b)
            code += 1
            if code == 0xFF:  # maximal group (254 data bytes, no implicit zero)
                out[code_idx] = code
                code_idx = len(out)
                out.append(0)
                code = 1
    out[code_idx] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    out = bytearray()
    idx = 0
    n = len(data)
    while idx < n:
        code = data[idx]
        idx += 1
        if code == 0:
            raise ValueError("unexpected zero in COBS data")
        length = code - 1
        if idx + length > n:
            raise ValueError("COBS overrun")
        out += data[idx:idx + length]
        idx += length
        if code != 0xFF and idx < n:
            out.append(0)
    return bytes(out)


# ---------------------------------------------------------------------------
# Frame (de)serialization with CRC + COBS, delimited by 0x00
# ---------------------------------------------------------------------------
def encode_frame(mtype: int, payload: bytes = b"", flags: int = 0) -> bytes:
    body = bytes([mtype & 0xFF, flags & 0xFF]) + payload
    body += struct.pack("<H", crc16(body))
    return cobs_encode(body) + b"\x00"


def decode_frame(frame_bytes: bytes) -> Tuple[int, int, bytes]:
    """Decode one COBS frame (without the trailing delimiter). Returns (type, flags, payload)."""
    body = cobs_decode(frame_bytes)
    if len(body) < 4:
        raise ValueError("frame too short")
    got = struct.unpack("<H", body[-2:])[0]
    want = crc16(body[:-2])
    if got != want:
        raise ValueError(f"CRC mismatch: got {got:#06x} want {want:#06x}")
    return body[0], body[1], body[2:-2]


class FrameParser:
    """Incremental, byte-loss tolerant parser. Feed bytes, get back (type, flags, payload)."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.crc_errors = 0
        self.cobs_errors = 0

    def feed(self, chunk: bytes) -> Iterator[Tuple[int, int, bytes]]:
        self._buf += chunk
        while True:
            i = self._buf.find(b"\x00")
            if i == -1:
                break
            frame = bytes(self._buf[:i])
            del self._buf[:i + 1]
            if not frame:
                continue
            try:
                yield decode_frame(frame)
            except ValueError as e:
                if "CRC" in str(e):
                    self.crc_errors += 1
                else:
                    self.cobs_errors += 1
                # drop and resync on next delimiter
                continue


# ---------------------------------------------------------------------------
# Sample helpers: pack/unpack signed 24-bit little-endian
# ---------------------------------------------------------------------------
def pack_i24(value: int) -> bytes:
    v = value & 0xFFFFFF
    return bytes((v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))


def unpack_i24(b: bytes) -> int:
    v = b[0] | (b[1] << 8) | (b[2] << 16)
    return v - 0x1000000 if v & 0x800000 else v


def popcount(x: int) -> int:
    return bin(x & 0xFF).count("1")


def active_channels(mask: int) -> List[int]:
    return [c for c in range(8) if mask & (1 << c)]


# ---------------------------------------------------------------------------
# Message dataclasses + (en/de)coders for the ones the pipeline uses
# ---------------------------------------------------------------------------
@dataclass
class Info:
    proto_version: int = PROTO_VERSION
    fw_major: int = 0
    fw_minor: int = 1
    fw_patch: int = 0
    n_channels: int = 8
    supported_rates: Tuple[int, ...] = (250, 500, 1000, 2000, 4000)
    adc_bits: int = 24
    adc_vref_mv: int = 1200
    fixed_gain_x100: int = 800  # 8.00x
    vs_dac_bits: int = 16
    vs_range_mv: int = 1000  # ±500 mV
    serial: str = "EPG-SIM-0001"

    def encode(self) -> bytes:
        rates = self.supported_rates
        p = struct.pack(
            "<BBBBB B HHHB H",
            self.proto_version, self.fw_major, self.fw_minor, self.fw_patch,
            self.n_channels, len(rates),
            self.adc_vref_mv, self.fixed_gain_x100, self.vs_range_mv,
            self.vs_dac_bits, self.adc_bits,
        )
        for r in rates:
            p += struct.pack("<H", r)
        s = self.serial.encode()[:32]
        p += struct.pack("<B", len(s)) + s
        return p

    @classmethod
    def decode(cls, p: bytes) -> "Info":
        (proto, fmaj, fmin, fpatch, nch, nrates,
         vref, gain, vsr, vsbits, adcbits) = struct.unpack("<BBBBB B HHHB H", p[:15])
        off = 15
        rates = []
        for _ in range(nrates):
            rates.append(struct.unpack("<H", p[off:off + 2])[0])
            off += 2
        slen = p[off]; off += 1
        serial = p[off:off + slen].decode(errors="replace")
        return cls(proto, fmaj, fmin, fpatch, nch, tuple(rates),
                   adcbits, vref, gain, vsbits, vsr, serial)

    @property
    def fixed_gain(self) -> float:
        return self.fixed_gain_x100 / 100.0


@dataclass
class SampleBlock:
    block_seq: int
    first_sample_index: int
    rate_code: int
    channel_mask: int
    status: int
    # samples[row][k] = code for k-th active channel
    samples: List[List[int]] = field(default_factory=list)

    def encode(self) -> bytes:
        nch = popcount(self.channel_mask)
        hdr = struct.pack(
            "<IQ BB H B",
            self.block_seq, self.first_sample_index,
            self.rate_code, self.channel_mask, len(self.samples), self.status,
        )
        body = bytearray(hdr)
        for row in self.samples:
            for v in row:
                body += pack_i24(v)
        return bytes(body)

    @classmethod
    def decode(cls, p: bytes) -> "SampleBlock":
        block_seq, first_idx, rate_code, mask, n, status = struct.unpack("<IQ BB H B", p[:17])
        nch = popcount(mask)
        off = 17
        rows = []
        for _ in range(n):
            row = [unpack_i24(p[off + 3 * k:off + 3 * k + 3]) for k in range(nch)]
            off += 3 * nch
            rows.append(row)
        return cls(block_seq, first_idx, rate_code, mask, status, rows)


@dataclass
class Event:
    event_type: int
    channel: int
    sample_index: int
    a: int = 0
    b: int = 0
    text: str = ""

    def encode(self) -> bytes:
        t = self.text.encode()[:255]
        return struct.pack("<BBQ ii B", self.event_type, self.channel,
                           self.sample_index, self.a, self.b, len(t)) + t

    @classmethod
    def decode(cls, p: bytes) -> "Event":
        et, ch, idx, a, b, tlen = struct.unpack("<BBQ ii B", p[:19])
        text = p[19:19 + tlen].decode(errors="replace")
        return cls(et, ch, idx, a, b, text)

    @property
    def type_name(self) -> str:
        return EVENT_NAMES.get(self.event_type, f"EV_{self.event_type}")
